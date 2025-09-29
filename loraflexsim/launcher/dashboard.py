from __future__ import annotations

import os
import sys
import math
import subprocess
import numbers

import panel as pn
import plotly.graph_objects as go
import numpy as np
import time
import threading
import pandas as pd
from collections import deque

# Assurer la résolution correcte des imports quel que soit le répertoire
# depuis lequel ce fichier est exécuté. On ajoute le dossier parent
# (celui contenant le paquet ``launcher``) ainsi que la racine du projet
# au ``sys.path`` s'ils n'y sont pas déjà. Ainsi, ``from launcher.simulator``
# fonctionnera aussi avec la commande ``panel serve dashboard.py`` exécutée
# depuis ce dossier et les modules comme ``traffic`` seront importables.
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
for path in (ROOT_DIR, REPO_ROOT):
    if path not in sys.path:
        sys.path.insert(0, path)

from launcher.simulator import Simulator  # noqa: E402
from launcher.channel import Channel  # noqa: E402
from launcher import (
    adr_standard_1,
    adr_2,
    adr_ml,  # stratégie ADR basée sur le ML
    explora_sf,
    explora_at,
    adr_lite,
    adr_max,
    radr,
    ADR_MODULES,
)  # noqa: E402

# --- Initialisation Panel ---
pn.extension("plotly", raw_css=[
    ".coord-textarea textarea {font-size: 14pt;}",
])
# Définition du titre de la page via le document Bokeh directement
if pn.state.curdoc:
    pn.state.curdoc.title = "Simulateur LoRa"
# Conteneur mutable pour conserver une référence valide à ``pn.state``
_SESSION_STATE: dict[str, object] = {"state": pn.state}

# --- Variables globales ---
sim = None
sim_callback = None
chrono_callback = None
map_anim_callback = None
start_time = None
elapsed_time = 0
max_real_time = None
paused = False
_DEFAULT_ADR_NAME = next(iter(ADR_MODULES))
selected_adr_module = ADR_MODULES[_DEFAULT_ADR_NAME]
total_runs = 1
current_run = 0
runs_events: list[pd.DataFrame] = []
runs_metrics: list[dict] = []
runs_metrics_timeline: list[pd.DataFrame | list[dict] | None] = []
auto_fast_forward = False
timeline_fig = go.Figure()
last_event_index = 0
_TIMELINE_MAX_SEGMENTS = 500
timeline_success_segments: deque[tuple[float, float, int]] = deque()
timeline_failure_segments: deque[tuple[float, float, int]] = deque()
pause_prev_disabled = False
node_paths: dict[int, list[tuple[float, float]]] = {}


def _get_last_metrics_timeline() -> pd.DataFrame | list[dict] | None:
    """Retourne la dernière timeline de métriques disponible parmi les runs."""

    for timeline in reversed(runs_metrics_timeline):
        if timeline is not None:
            return timeline
    return None


def aggregate_run_metrics(metrics_list: list[dict]) -> dict:
    """Agrège les métriques de plusieurs runs en pondérant correctement."""

    if not metrics_list:
        return {}

    total_attempted = 0.0
    total_delivered = 0.0
    total_collisions = 0.0
    total_duplicates = 0.0
    total_retransmissions = 0.0
    total_energy = 0.0
    total_energy_nodes = 0.0
    total_energy_gateways = 0.0
    total_delay_weighted = 0.0
    total_arrival_interval_weighted = 0.0
    total_throughput_weighted_bits = 0.0
    total_simulation_time = 0.0

    energy_class_totals: dict[str, float] = {}

    for metrics in metrics_list:
        attempted = float(metrics.get("tx_attempted", 0.0) or 0.0)
        delivered = float(metrics.get("delivered", 0.0) or 0.0)
        collisions = float(metrics.get("collisions", 0.0) or 0.0)
        duplicates = float(metrics.get("duplicates", 0.0) or 0.0)
        retrans = float(metrics.get("retransmissions", 0.0) or 0.0)
        energy_total = float(metrics.get("energy_J", 0.0) or 0.0)
        energy_nodes = float(metrics.get("energy_nodes_J", 0.0) or 0.0)
        energy_gw = float(metrics.get("energy_gateways_J", 0.0) or 0.0)
        avg_delay = float(metrics.get("avg_delay_s", 0.0) or 0.0)
        avg_arrival_interval = float(metrics.get("avg_arrival_interval_s", 0.0) or 0.0)
        throughput = float(metrics.get("throughput_bps", 0.0) or 0.0)
        sim_time = float(metrics.get("simulation_time_s", 0.0) or 0.0)

        total_attempted += attempted
        total_delivered += delivered
        total_collisions += collisions
        total_duplicates += duplicates
        total_retransmissions += retrans
        total_energy += energy_total
        total_energy_nodes += energy_nodes
        total_energy_gateways += energy_gw
        total_delay_weighted += avg_delay * delivered
        total_arrival_interval_weighted += avg_arrival_interval * attempted
        total_throughput_weighted_bits += throughput * sim_time
        total_simulation_time += sim_time

        for key, value in metrics.items():
            if key.startswith("energy_class_") and key.endswith("_J"):
                energy_class_totals[key] = energy_class_totals.get(key, 0.0) + float(
                    value or 0.0
                )

    aggregated: dict[str, float] = {
        "tx_attempted": total_attempted,
        "delivered": total_delivered,
        "collisions": total_collisions,
        "duplicates": total_duplicates,
        "retransmissions": total_retransmissions,
        "energy_J": total_energy,
        "energy_nodes_J": total_energy_nodes,
        "energy_gateways_J": total_energy_gateways,
        "simulation_time_s": total_simulation_time,
    }

    aggregated.update(energy_class_totals)

    aggregated["PDR"] = (
        total_delivered / total_attempted if total_attempted > 0 else 0.0
    )

    aggregated["avg_delay_s"] = (
        total_delay_weighted / total_delivered if total_delivered > 0 else 0.0
    )

    aggregated["avg_arrival_interval_s"] = (
        total_arrival_interval_weighted / total_attempted
        if total_attempted > 0
        else 0.0
    )

    aggregated["throughput_bps"] = (
        total_throughput_weighted_bits / total_simulation_time
        if total_simulation_time > 0
        else 0.0
    )

    return aggregated

def _get_panel_state() -> object:
    """Return the captured Panel state used across threads."""

    return _SESSION_STATE["state"]


def session_alive(doc=None, state_container=_SESSION_STATE) -> bool:
    """Return True if the Bokeh session is still active."""

    state = state_container["state"]
    if doc is None:
        doc = getattr(state, "curdoc", None)
    sc = getattr(doc, "session_context", None)
    return bool(sc and getattr(sc, "session", None))

def _cleanup_callbacks() -> None:
    """Stop all periodic callbacks safely."""
    global sim_callback, chrono_callback, map_anim_callback
    for cb_name in ("sim_callback", "chrono_callback", "map_anim_callback"):
        cb = globals().get(cb_name)
        if cb is not None:
            try:
                cb.stop()
            except Exception:
                pass
            globals()[cb_name] = None


def _validate_positive_inputs() -> bool:
    """Return False and display a warning if key parameters are not positive."""
    if int(num_nodes_input.value) <= 0:
        export_message.object = "⚠️ Le nombre de nœuds doit être supérieur à 0 !"
        return False
    if float(area_input.value) <= 0:
        export_message.object = "⚠️ La taille de l'aire doit être supérieure à 0 !"
        return False
    if float(interval_input.value) <= 0:
        export_message.object = "⚠️ L'intervalle doit être supérieur à 0 !"
        return False
    return True


# --- Widgets de configuration ---
num_nodes_input = pn.widgets.IntInput(name="Nombre de nœuds", value=2, step=1, start=1)
num_gateways_input = pn.widgets.IntInput(name="Nombre de passerelles", value=1, step=1, start=1)
area_input = pn.widgets.FloatInput(name="Taille de l'aire (m)", value=1000.0, step=100.0, start=100.0)
mode_select = pn.widgets.RadioButtonGroup(
    name="Mode d'émission", options=["Aléatoire", "Périodique"], value="Aléatoire"
)
interval_input = pn.widgets.FloatInput(name="Intervalle moyen (s)", value=100.0, step=1.0, start=0.1)
first_packet_input = pn.widgets.FloatInput(
    name="Intervalle premier paquet (s)",
    value=100.0,
    step=1.0,
    start=0.1,
)
packets_input = pn.widgets.IntInput(
    name="Nombre de paquets par nœud (0=infini)", value=80, step=1, start=0
)
seed_input = pn.widgets.IntInput(
    name="Graine (0 = aléatoire)", value=0, step=1, start=0
)
num_runs_input = pn.widgets.IntInput(name="Nombre de runs", value=1, start=1)
adr_node_checkbox = pn.widgets.Checkbox(name="ADR nœud", value=True)
adr_server_checkbox = pn.widgets.Checkbox(name="ADR serveur", value=True)

# --- Sélecteur du protocole ADR ---
adr_select = pn.widgets.Select(
    name="Protocole ADR",
    options=list(ADR_MODULES.keys()),
    value=_DEFAULT_ADR_NAME,
)

# --- Choix SF et puissance initiaux identiques ---
fixed_sf_checkbox = pn.widgets.Checkbox(name="Choisir SF unique", value=False)
sf_value_input = pn.widgets.IntSlider(name="SF initial", start=7, end=12, value=7, step=1, disabled=True)

fixed_power_checkbox = pn.widgets.Checkbox(name="Choisir puissance unique", value=False)
tx_power_input = pn.widgets.FloatSlider(name="Puissance Tx (dBm)", start=2, end=20, value=14, step=1, disabled=True)

# --- Multi-canaux ---
num_channels_input = pn.widgets.IntInput(name="Nb sous-canaux", value=1, step=1, start=1)
channel_dist_select = pn.widgets.RadioButtonGroup(
    name="Répartition canaux", options=["Round-robin", "Aléatoire"], value="Round-robin"
)

# -- Options de couche physique --
fine_fading_input = pn.widgets.FloatInput(
    name="Fine fading std (dB)", value=0.0, step=0.1, start=0.0
)
noise_std_input = pn.widgets.FloatInput(
    name="Bruit thermique variable (dB)", value=0.0, step=0.1, start=0.0
)

# --- Widget pour activer/désactiver la mobilité des nœuds ---
mobility_checkbox = pn.widgets.Checkbox(name="Activer la mobilité des nœuds", value=False)

# Widgets pour régler la vitesse minimale et maximale des nœuds mobiles
mobility_speed_min_input = pn.widgets.FloatInput(name="Vitesse min (m/s)", value=2.0, step=0.5, start=0.1)
mobility_speed_max_input = pn.widgets.FloatInput(name="Vitesse max (m/s)", value=10.0, step=0.5, start=0.1)
show_paths_checkbox = pn.widgets.Checkbox(name="Afficher les trajectoires", value=False)

# Choix du modèle de mobilité
mobility_model_select = pn.widgets.Select(
    name="Modèle de mobilité",
    options=["Smooth", "RandomWaypoint", "Path"],
    value="Smooth",
)

# --- Durée réelle de simulation et bouton d'accélération ---
sim_duration_input = pn.widgets.FloatInput(
    name="Durée simulée max (s)", value=0.0, step=1.0, start=0.0
)
real_time_duration_input = pn.widgets.FloatInput(name="Durée réelle max (s)", value=86400.0, step=1.0, start=0.0)
fast_forward_button = pn.widgets.Button(
    name="Accélérer jusqu'à la fin", button_type="primary", disabled=True
)
fast_forward_button.disabled = True


def _has_simulation_limit_from_inputs() -> bool:
    return int(packets_input.value) > 0 or float(sim_duration_input.value) > 0.0


def _has_simulation_limit_from_sim() -> bool:
    if sim is None:
        return _has_simulation_limit_from_inputs()
    has_packets = getattr(sim, "packets_to_send", 0) > 0
    sim_duration = getattr(sim, "max_sim_time", getattr(sim, "sim_duration_limit", None))
    return has_packets or (sim_duration is not None and sim_duration > 0.0)


def _refresh_fast_forward_state_from_inputs() -> None:
    fast_forward_button.disabled = not _has_simulation_limit_from_inputs()

# --- Paramètres radio FLoRa ---
flora_mode_toggle = pn.widgets.Toggle(name="Mode FLoRa complet", button_type="primary", value=True)
detection_threshold_input = pn.widgets.FloatInput(
    name="Seuil détection (dBm)", value=-110.0, step=1.0, start=-150.0
)
detection_threshold_input.disabled = True
min_interference_input = pn.widgets.FloatInput(
    name="Interférence minimale (s)", value=5.0, step=0.1, start=0.0
)
# Pas de champ dédié pour le délai minimal avant le premier envoi
min_interference_input.disabled = True
# --- Paramètres supplémentaires ---
battery_capacity_input = pn.widgets.FloatInput(
    name="Capacité batterie (J)", value=0.0, step=10.0, start=0.0
)
payload_size_input = pn.widgets.IntInput(
    name="Taille payload (o)", value=20, step=1, start=1
)
node_class_select = pn.widgets.RadioButtonGroup(
    name="Classe LoRaWAN", options=["A", "B", "C"], value="A"
)
# Lorsque le mode FLoRa est activé, cette valeur est fixée à 5 s

# --- Positions manuelles ---
manual_pos_toggle = pn.widgets.Checkbox(name="Positions manuelles")
position_textarea = pn.widgets.TextAreaInput(
    name="Coordonnées",
    height=100,
    visible=False,
    width=650,
    css_classes=["coord-textarea"],
)


# --- Boutons de contrôle ---
start_button = pn.widgets.Button(name="Lancer la simulation", button_type="success")
stop_button = pn.widgets.Button(name="Arrêter la simulation", button_type="warning", disabled=True)
# Icône ajoutée pour mieux distinguer l'état du bouton Pause/Reprendre
pause_button = pn.widgets.Button(name="⏸ Pause", button_type="primary", disabled=True)

# --- Nouveau bouton d'export et message d'état ---
export_button = pn.widgets.Button(name="Exporter résultats", button_type="primary", disabled=True)
export_message = pn.pane.HTML("Cliquez sur Exporter pour générer le fichier CSV après la simulation.")

# --- Indicateurs de métriques ---
pdr_indicator = pn.indicators.Number(name="PDR", value=0, format="{value:.1%}")
# Display collisions as a float in case multiple runs are averaged
collisions_indicator = pn.indicators.Number(
    name="Collisions", value=0.0, format="{value:.1f}"
)
energy_indicator = pn.indicators.Number(name="Énergie Tx (J)", value=0.0, format="{value:.3f}")
delay_indicator = pn.indicators.Number(name="Délai moyen (s)", value=0.0, format="{value:.3f}")
throughput_indicator = pn.indicators.Number(name="Débit (bps)", value=0.0, format="{value:.2f}")

# Indicateur de retransmissions
# Same for retransmissions which may also be averaged across runs
retrans_indicator = pn.indicators.Number(
    name="Retransmissions", value=0.0, format="{value:.1f}"
)


def _set_metric_indicators(
    metrics: dict | None, snapshot: dict | None = None
) -> None:
    """Met à jour les indicateurs numériques à partir des données disponibles."""

    data = metrics or {}
    snapshot_data = snapshot or {}

    def _pick(key: str, *, prefer_snapshot: bool = True):
        if prefer_snapshot:
            value = snapshot_data.get(key)
            if value is not None:
                return value
        value = data.get(key)
        if value is not None:
            return value
        if not prefer_snapshot:
            fallback = snapshot_data.get(key)
            if fallback is not None:
                return fallback
        return None

    def _assign(indicator, value):
        raw_value = value if value is not None else 0.0
        if isinstance(raw_value, numbers.Real):
            indicator.value = float(raw_value)
            return
        try:
            indicator.value = float(raw_value)
        except (TypeError, ValueError):
            indicator.value = 0.0

    _assign(pdr_indicator, _pick("PDR"))
    _assign(collisions_indicator, _pick("collisions"))
    _assign(energy_indicator, _pick("energy_J"))

    delay_value = _pick("instant_avg_delay_s")
    if delay_value is None:
        delay_value = _pick("avg_delay_s", prefer_snapshot=False)
    _assign(delay_indicator, delay_value)

    throughput_value = _pick("instant_throughput_bps")
    if throughput_value is None:
        throughput_value = _pick("throughput_bps", prefer_snapshot=False)
    _assign(throughput_indicator, throughput_value)

    _assign(retrans_indicator, _pick("retransmissions"))

# Barre de progression pour l'accélération
fast_forward_progress = pn.indicators.Progress(name="Avancement", value=0, width=200, visible=False)

# Les tableaux de PDR détaillés ne sont plus affichés dans le tableau de bord
# mais les données sont conservées pour être exportées en fin de simulation.

# Tableau récapitulatif du PDR par nœud (global et récent)
pdr_table = pn.pane.DataFrame(
    pd.DataFrame(columns=["Node", "PDR", "Recent PDR"]),
    height=200,
    width=220,
)

# --- Chronomètre ---
chrono_indicator = pn.indicators.Number(name="Durée simulation (s)", value=0, format="{value:.1f}")


# --- Pane pour la carte des nœuds/passerelles ---
# Agrandir la surface d'affichage de la carte pour une meilleure lisibilité
map_pane = pn.pane.Plotly(height=600, sizing_mode="stretch_width")

# --- Pane pour l'histogramme multi-métrique (SF ou délais selon hist_metric_select) ---
sf_hist_pane = pn.pane.Plotly(height=250, sizing_mode="stretch_width")
hist_metric_select = pn.widgets.Select(name="Histogramme", options=["SF", "D\u00e9lais"], value="SF")

# --- Timeline des paquets ---
timeline_pane = pn.pane.Plotly(height=250, sizing_mode="stretch_width")

# --- Timeline des métriques cumulées ---
metrics_timeline_pane = pn.pane.Plotly(height=250, sizing_mode="stretch_width")

# Intervalle d'itérations avant de recalculer entièrement la figure Plotly.
METRICS_TIMELINE_FULL_REFRESH_INTERVAL = 20

# Traces suivies sur la timeline des métriques.
_METRICS_TIMELINE_TRACES = [
    ("PDR", "PDR"),
    ("collisions", "Collisions"),
    ("duplicates", "Duplicats"),
    ("packets_lost_no_signal", "Perdus (sans signal)"),
    ("energy_J", "Énergie (J)"),
    ("instant_throughput_bps", "Débit instantané (bps)"),
]

# Taille maximale de la fenêtre envoyée à Plotly pour la timeline des métriques.
METRICS_TIMELINE_WINDOW_SIZE = 500

# Tampon des snapshots complets (utilisé pour l'export) et fenêtre bornée pour l'affichage.
metrics_timeline_buffer: list[dict[str, float | int]] = []
metrics_timeline_window: deque[dict[str, float | int]] = deque(
    maxlen=METRICS_TIMELINE_WINDOW_SIZE
)
metrics_timeline_last_key: (
    tuple[float | int | None, float | int | None, float | int | None] | None
) = None
_metrics_timeline_steps_since_refresh = 0


def _snapshot_signature(
    snapshot: dict[str, float | int]
) -> tuple[float | int | None, float | int | None, float | int | None]:
    """Construit la signature utilisée pour éviter les doublons de timeline."""

    return (
        snapshot.get("time_s"),
        snapshot.get("tx_attempted"),
        snapshot.get("delivered"),
    )

# --- Heatmap de couverture ---
heatmap_button = pn.widgets.Button(name="Afficher la heatmap", button_type="primary")
heatmap_pane = pn.pane.Plotly(height=600, sizing_mode="stretch_width", visible=False)
heatmap_res_slider = pn.widgets.IntSlider(name="Résolution heatmap", start=10, end=100, step=10, value=30)


# --- Mise à jour de la carte ---
def update_map():
    global sim
    if sim is None or not session_alive():
        return
    fig = go.Figure()
    area = area_input.value
    # Add a small extra space on the Y axis so edge nodes remain fully visible
    extra_y = area * 0.125
    display_area_y = area + extra_y
    pixel_to_unit = display_area_y / 600
    node_offset = 16 * pixel_to_unit
    gw_offset = 14 * pixel_to_unit
    for node in sim.nodes:
        node_paths.setdefault(node.id, []).append((node.x, node.y))
        if len(node_paths[node.id]) > 50:
            node_paths[node.id] = node_paths[node.id][-50:]
    x_nodes = [node.x for node in sim.nodes]
    y_nodes = [node.y for node in sim.nodes]
    node_ids = [str(node.id) for node in sim.nodes]
    fig.add_scatter(
        x=x_nodes,
        y=y_nodes,
        mode="markers+text",
        name="Nœuds",
        text=node_ids,
        textposition="middle center",
        marker=dict(symbol="circle", color="blue", size=32),
        textfont=dict(color="white", size=14),
    )
    x_gw = [gw.x for gw in sim.gateways]
    y_gw = [gw.y for gw in sim.gateways]
    gw_ids = [str(gw.id) for gw in sim.gateways]
    fig.add_scatter(
        x=x_gw,
        y=y_gw,
        mode="markers+text",
        name="Passerelles",
        text=gw_ids,
        textposition="middle center",
        marker=dict(symbol="star", color="red", size=28, line=dict(width=1, color="black")),
        textfont=dict(color="white", size=14),
    )

    if show_paths_checkbox.value:
        for path in node_paths.values():
            if len(path) > 1:
                xs_p, ys_p = zip(*path)
                fig.add_scatter(x=xs_p, y=ys_p, mode="lines", line=dict(color="black", width=1), showlegend=False)

    # Dessiner les transmissions récentes
    for ev in sim.events_log[-20:]:
        gw_id = ev.get("gateway_id")
        if gw_id is None:
            continue
        node = next((n for n in sim.nodes if n.id == ev["node_id"]), None)
        gw = next((g for g in sim.gateways if g.id == gw_id), None)
        if not node or not gw:
            continue
        color = "green" if ev.get("result") == "Success" else "red"
        dx = gw.x - node.x
        dy = gw.y - node.y
        dist = math.hypot(dx, dy)
        if dist:
            sx = node.x + dx / dist * node_offset
            sy = node.y + dy / dist * node_offset
            ex = gw.x - dx / dist * gw_offset
            ey = gw.y - dy / dist * gw_offset
        else:
            sx, sy = node.x, node.y
            ex, ey = gw.x, gw.y
        fig.add_scatter(
            x=[sx, ex],
            y=[sy, ey],
            mode="lines",
            line=dict(color=color, width=2),
            showlegend=False,
        )
    fig.update_layout(
        title="Position des nœuds et passerelles",
        xaxis_title="X (m)",
        yaxis_title="Y (m)",
        xaxis_range=[0, area],
        yaxis_range=[-extra_y, display_area_y],
        yaxis=dict(scaleanchor="x", scaleratio=1),
        margin=dict(l=20, r=20, t=40, b=20),
    )
    map_pane.object = fig


def _ensure_timeline_traces() -> tuple[int, int]:
    """Ensure that the timeline figure contains persistent traces."""

    global timeline_fig

    if not isinstance(timeline_fig, go.Figure):
        timeline_fig = go.Figure()

    name_to_index = {trace.name: idx for idx, trace in enumerate(timeline_fig.data)}

    success_idx = name_to_index.get("Succès")
    if success_idx is None:
        timeline_fig.add_trace(
            go.Scattergl(
                name="Succès",
                mode="lines",
                line=dict(color="green"),
                hoverinfo="none",
                x=[],
                y=[],
            )
        )
        success_idx = len(timeline_fig.data) - 1

    failure_idx = name_to_index.get("Échecs")
    if failure_idx is None:
        timeline_fig.add_trace(
            go.Scattergl(
                name="Échecs",
                mode="lines",
                line=dict(color="red"),
                hoverinfo="none",
                x=[],
                y=[],
            )
        )
        failure_idx = len(timeline_fig.data) - 1

    return success_idx, failure_idx


def _segments_to_xy(
    segments: deque[tuple[float, float, int]]
) -> tuple[list[float | None], list[int | None]]:
    """Transforme des segments (start, end, node) en listes Plotly."""

    x_values: list[float | None] = []
    y_values: list[int | None] = []
    for start, end, node in segments:
        x_values.extend((start, end, None))
        y_values.extend((node, node, None))
    return x_values, y_values


def update_timeline():
    """Mise à jour incrémentale de la timeline des paquets."""

    global sim, timeline_fig, last_event_index
    global timeline_success_segments, timeline_failure_segments

    if sim is None or not session_alive():
        timeline_fig = go.Figure()
        last_event_index = 0
        timeline_success_segments.clear()
        timeline_failure_segments.clear()
        timeline_pane.object = timeline_fig
        return

    _ensure_timeline_traces()

    if not sim.events_log:
        timeline_pane.object = timeline_fig
        return

    for ev in sim.events_log[last_event_index:]:
        if ev.get("result") is None:
            continue
        node_id = int(ev["node_id"])
        start = float(ev["start_time"])
        end = float(ev["end_time"])
        segment = (start, end, node_id)
        if ev.get("result") == "Success":
            timeline_success_segments.append(segment)
        else:
            timeline_failure_segments.append(segment)

    last_event_index = len(sim.events_log)

    while len(timeline_success_segments) > _TIMELINE_MAX_SEGMENTS:
        timeline_success_segments.popleft()
    while len(timeline_failure_segments) > _TIMELINE_MAX_SEGMENTS:
        timeline_failure_segments.popleft()

    x_success, y_success = _segments_to_xy(timeline_success_segments)
    x_failure, y_failure = _segments_to_xy(timeline_failure_segments)

    timeline_fig.update_traces(
        dict(x=x_success, y=y_success), selector=dict(name="Succès")
    )
    timeline_fig.update_traces(
        dict(x=x_failure, y=y_failure), selector=dict(name="Échecs")
    )

    timeline_fig.update_layout(
        title="Timeline des paquets",
        xaxis_title="Temps (s)",
        yaxis_title="ID nœud",
        xaxis_range=[0, sim.current_time],
        margin=dict(l=20, r=20, t=40, b=20),
    )
    timeline_pane.object = timeline_fig


def _metrics_timeline_to_dataframe(
    timeline: pd.DataFrame | list[dict] | None,
) -> pd.DataFrame | None:
    """Convertit une timeline quelconque en DataFrame pour faciliter le tracé."""

    if timeline is None:
        return None
    if isinstance(timeline, pd.DataFrame):
        if timeline.empty:
            return None
        return timeline.copy()
    if not timeline:
        return None
    if pd is None:
        return None
    df = pd.DataFrame(list(timeline))
    return df if not df.empty else None


def _timeline_to_records(
    timeline: pd.DataFrame | list[dict] | None,
) -> list[dict[str, float | int]]:
    """Normalise une timeline en liste de snapshots (dict)."""

    if timeline is None:
        return []
    if isinstance(timeline, pd.DataFrame):
        if METRICS_TIMELINE_WINDOW_SIZE > 0 and hasattr(timeline, "tail"):
            limited = timeline.tail(METRICS_TIMELINE_WINDOW_SIZE)
            return limited.to_dict("records")
        return timeline.to_dict("records")
    if isinstance(timeline, list):
        if METRICS_TIMELINE_WINDOW_SIZE > 0:
            return timeline[-METRICS_TIMELINE_WINDOW_SIZE :]
        return timeline
    if METRICS_TIMELINE_WINDOW_SIZE > 0:
        limited_deque: deque[dict[str, float | int]] = deque(
            maxlen=METRICS_TIMELINE_WINDOW_SIZE
        )
        for snapshot in timeline:
            limited_deque.append(snapshot)
        return list(limited_deque)
    return list(timeline)


def _set_metrics_timeline_window(
    timeline: pd.DataFrame | list[dict] | None,
) -> deque[dict[str, float | int]]:
    """Met à jour la fenêtre glissante à partir de la timeline fournie."""

    global metrics_timeline_window
    records = _timeline_to_records(timeline)
    metrics_timeline_window = deque(
        records[-METRICS_TIMELINE_WINDOW_SIZE :],
        maxlen=METRICS_TIMELINE_WINDOW_SIZE,
    )
    return metrics_timeline_window


def _build_metrics_timeline_figure(
    timeline: pd.DataFrame | list[dict] | None,
) -> go.Figure:
    """Construit un graphique Plotly représentant l'évolution des métriques."""

    df = _metrics_timeline_to_dataframe(timeline)
    fig = go.Figure()
    if df is None or "time_s" not in df.columns:
        fig.update_layout(
            title="Évolution des métriques",
            xaxis_title="Temps (s)",
            yaxis_title="Valeur",
            margin=dict(l=20, r=20, t=40, b=20),
            legend_title="Métrique",
        )
        return fig

    time_values = df["time_s"]
    for column, label in _METRICS_TIMELINE_TRACES:
        if column in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=time_values,
                    y=df[column],
                    mode="lines+markers",
                    name=label,
                )
            )

    fig.update_layout(
        title="Évolution des métriques",
        xaxis_title="Temps (s)",
        yaxis_title="Valeur",
        margin=dict(l=20, r=20, t=40, b=20),
        legend_title="Métrique",
    )
    return fig


def _create_empty_metrics_timeline_figure() -> go.Figure:
    """Crée une figure Plotly avec les traces attendues mais sans données."""

    fig = go.Figure()
    for _, label in _METRICS_TIMELINE_TRACES:
        fig.add_scatter(x=[], y=[], mode="lines+markers", name=label)
    fig.update_layout(
        title="Évolution des métriques",
        xaxis_title="Temps (s)",
        yaxis_title="Valeur",
        margin=dict(l=20, r=20, t=40, b=20),
        legend_title="Métrique",
    )
    return fig


def _ensure_metrics_timeline_figure() -> go.Figure:
    """Retourne une figure prête à être mise à jour incrémentalement."""

    expected_names = [label for _, label in _METRICS_TIMELINE_TRACES]
    fig = metrics_timeline_pane.object
    if isinstance(fig, go.Figure):
        current_names = [trace.name for trace in fig.data]
        if current_names == expected_names:
            return fig
    fig = _create_empty_metrics_timeline_figure()
    metrics_timeline_pane.object = fig
    return fig


def _update_metrics_timeline_pane(
    timeline: pd.DataFrame | list[dict] | None,
    latest_snapshot: dict[str, float | int] | None = None,
    *,
    append: bool = False,
    force: bool = False,
) -> None:
    """Actualise le pane Plotly dédié à la timeline des métriques."""

    if not force and not append and latest_snapshot is None:
        return

    fig = _ensure_metrics_timeline_figure()

    if append and latest_snapshot is not None:
        time_value = latest_snapshot.get("time_s")
        if time_value is None:
            return
        window_length = len(timeline) if timeline is not None else None
        for column, label in _METRICS_TIMELINE_TRACES:
            if column not in latest_snapshot:
                continue
            trace = next((tr for tr in fig.data if tr.name == label), None)
            if trace is None:
                continue
            current_x = trace.x if trace.x is not None else ()
            current_y = trace.y if trace.y is not None else ()
            if window_length is not None:
                keep = max(window_length - 1, 0)
                if keep == 0:
                    trimmed_x: tuple | list = []
                    trimmed_y: tuple | list = []
                elif len(current_x) > keep:
                    trimmed_x = current_x[-keep:]
                    trimmed_y = current_y[-keep:]
                else:
                    trimmed_x = current_x
                    trimmed_y = current_y
                if trimmed_x is not current_x or trimmed_y is not current_y:
                    trace.update(x=trimmed_x, y=trimmed_y)
            if trace.x is None:
                trace.x = []
            if trace.y is None:
                trace.y = []
            trace.x += (time_value,)
            trace.y += (latest_snapshot[column],)
        metrics_timeline_pane.object = fig
        return

    df = _metrics_timeline_to_dataframe(timeline)
    if df is None:
        for trace in fig.data:
            trace.update(x=[], y=[])
        metrics_timeline_pane.object = fig
        return

    if hasattr(df, "tail"):
        window_df = df.tail(METRICS_TIMELINE_WINDOW_SIZE)
        if "time_s" not in getattr(window_df, "columns", []):
            for trace in fig.data:
                trace.update(x=[], y=[])
            metrics_timeline_pane.object = fig
            return
        time_values = tuple(window_df["time_s"])  # type: ignore[index]
        for column, label in _METRICS_TIMELINE_TRACES:
            trace = next((tr for tr in fig.data if tr.name == label), None)
            if trace is None:
                continue
            if column in getattr(window_df, "columns", []):
                values = tuple(window_df[column])  # type: ignore[index]
                trace.update(x=time_values, y=values)
            else:
                trace.update(x=time_values, y=(None,) * len(time_values))
        metrics_timeline_pane.object = fig
        return

    records = df.to_dict("records") if hasattr(df, "to_dict") else []
    if METRICS_TIMELINE_WINDOW_SIZE > 0:
        records = records[-METRICS_TIMELINE_WINDOW_SIZE :]
    filtered_records = [rec for rec in records if "time_s" in rec]
    if not filtered_records:
        for trace in fig.data:
            trace.update(x=[], y=[])
        metrics_timeline_pane.object = fig
        return

    time_values = tuple(rec["time_s"] for rec in filtered_records)
    for column, label in _METRICS_TIMELINE_TRACES:
        trace = next((tr for tr in fig.data if tr.name == label), None)
        if trace is None:
            continue
        values = tuple(rec.get(column) for rec in filtered_records)
        trace.update(x=time_values, y=values)
    metrics_timeline_pane.object = fig


def update_histogram(metrics: dict | None = None) -> None:
    """Mettre à jour l'histogramme interactif selon l'option sélectionnée."""
    if sim is None:
        sf_hist_pane.object = go.Figure()
        return
    if metrics is None:
        metrics = sim.get_metrics()
    if hist_metric_select.value == "SF":
        sf_dist = metrics["sf_distribution"]
        fig = go.Figure(data=[go.Bar(x=[f"SF{sf}" for sf in sf_dist.keys()], y=list(sf_dist.values()))])
        fig.update_layout(
            title="Répartition des SF par nœud",
            xaxis_title="SF",
            yaxis_title="Nombre de nœuds",
            yaxis_range=[0, sim.num_nodes],
        )
    else:
        delays = [ev["end_time"] - ev["start_time"] for ev in sim.events_log if ev.get("result")]
        if not delays:
            fig = go.Figure()
        else:
            hist, edges = np.histogram(delays, bins=20)
            centers = 0.5 * (edges[:-1] + edges[1:])
            fig = go.Figure(data=[go.Bar(x=centers, y=hist, width=np.diff(edges))])
            fig.update_layout(
                title="Distribution des délais",
                xaxis_title="Délai (s)",
                yaxis_title="Occurrences",
            )
    sf_hist_pane.object = fig

def update_heatmap(event=None):
    """Mettre à jour la heatmap de couverture."""
    if sim is None:
        return
    area = sim.area_size
    res = int(heatmap_res_slider.value)
    xs = np.linspace(0, area, res)
    ys = np.linspace(0, area, res)
    z = np.zeros((res, res))
    for i, y in enumerate(ys):
        for j, x in enumerate(xs):
            best_rssi = -float("inf")
            for gw in sim.gateways:
                d = math.hypot(x - gw.x, y - gw.y)
                rssi, _ = sim.channel.compute_rssi(14.0, d, sf=7)
                if rssi > best_rssi:
                    best_rssi = rssi
            z[i, j] = best_rssi
    fig = go.Figure()
    fig.add_trace(go.Heatmap(x=xs, y=ys, z=z, colorscale="Viridis"))
    fig.add_scatter(
        x=[gw.x for gw in sim.gateways],
        y=[gw.y for gw in sim.gateways],
        mode="markers",
        marker=dict(symbol="star", color="red", size=28, line=dict(width=1, color="black")),
        name="Passerelles",
    )
    fig.update_layout(
        title="Heatmap couverture (RSSI)",
        xaxis_title="X (m)",
        yaxis_title="Y (m)",
        xaxis_range=[0, area],
        yaxis_range=[0, area],
        yaxis=dict(scaleanchor="x", scaleratio=1),
        margin=dict(l=20, r=20, t=40, b=20),
    )
    heatmap_pane.object = fig


def toggle_heatmap(event=None):
    """Afficher ou masquer la heatmap de couverture."""
    if heatmap_pane.visible:
        heatmap_pane.visible = False
        heatmap_button.name = "Afficher la heatmap"
        return
    update_heatmap()
    heatmap_pane.visible = True
    heatmap_button.name = "Masquer la heatmap"
    heatmap_pane.visible = True
    heatmap_button.name = "Masquer la heatmap"


# --- Callback pour changer le label de l'intervalle selon le mode d'émission ---
def on_mode_change(event):
    if event.new == "Aléatoire":
        interval_input.name = "Intervalle moyen (s)"
    else:
        interval_input.name = "Période (s)"


mode_select.param.watch(on_mode_change, "value")


# --- Synchronisation de l'intervalle du premier paquet ---
first_packet_user_edited = False
_syncing_first_packet = False


def on_interval_update(event):
    global _syncing_first_packet
    if not first_packet_user_edited:
        _syncing_first_packet = True
        first_packet_input.value = event.new
        _syncing_first_packet = False


def on_first_packet_change(event):
    global first_packet_user_edited
    if not _syncing_first_packet:
        first_packet_user_edited = True
        if hasattr(event, "new"):
            # Panel updates the widget value before invoking the callback, but
            # tests and scripted interactions often call the handler directly.
            # Explicitly mirror the requested value so the UI state always
            # reflects the most recent user input.
            first_packet_input.value = event.new


interval_input.param.watch(on_interval_update, "value")
first_packet_input.param.watch(on_first_packet_change, "value")


# --- Sélection du profil ADR ---
def select_adr(module, name: str) -> None:
    global selected_adr_module
    selected_adr_module = module
    adr_node_checkbox.value = True
    adr_server_checkbox.value = True
    if adr_select.value != name:
        adr_select.value = name
    if sim is not None:
        module.apply(sim)

# --- Callback chrono ---
def periodic_chrono_update():
    global chrono_indicator, start_time, elapsed_time, max_real_time
    if not session_alive():
        _cleanup_callbacks()
        return
    if start_time is not None:
        elapsed_time = time.time() - start_time
        chrono_indicator.value = elapsed_time
        if max_real_time is not None and elapsed_time >= max_real_time:
            on_stop(None)


# --- Callback étape de simulation ---
def step_simulation():
    global runs_metrics_timeline, metrics_timeline_buffer, _metrics_timeline_steps_since_refresh
    global metrics_timeline_last_key, metrics_timeline_window
    if sim is None or not session_alive():
        if not session_alive():
            _cleanup_callbacks()
        return

    cont = sim.step()
    latest_snapshot = sim.get_latest_metrics_snapshot()

    if len(runs_metrics_timeline) < max(current_run, 1):
        runs_metrics_timeline.extend(
            [None] * (max(current_run, 1) - len(runs_metrics_timeline))
        )

    run_timeline: list[dict[str, float | int]] | None = None
    buffer_changed = False

    if current_run >= 1:
        stored_timeline = runs_metrics_timeline[current_run - 1]
        if isinstance(stored_timeline, pd.DataFrame):
            run_timeline = stored_timeline.to_dict("records")
            runs_metrics_timeline[current_run - 1] = run_timeline
            buffer_changed = True
        elif isinstance(stored_timeline, list):
            run_timeline = stored_timeline
        elif stored_timeline is None:
            run_timeline = []
            runs_metrics_timeline[current_run - 1] = run_timeline
            buffer_changed = True
        else:
            run_timeline = list(stored_timeline)
            runs_metrics_timeline[current_run - 1] = run_timeline
            buffer_changed = True
    else:
        run_timeline = metrics_timeline_buffer

    if run_timeline is None:
        run_timeline = []
        if current_run >= 1:
            runs_metrics_timeline[current_run - 1] = run_timeline
        buffer_changed = True

    if run_timeline is not metrics_timeline_buffer:
        metrics_timeline_buffer = run_timeline
        buffer_changed = True

    previous_last_key = metrics_timeline_last_key
    if buffer_changed:
        metrics_timeline_window = _set_metrics_timeline_window(run_timeline)
        if run_timeline:
            previous_last_key = _snapshot_signature(run_timeline[-1])
        else:
            previous_last_key = None
        metrics_timeline_last_key = previous_last_key

    signature = (
        _snapshot_signature(latest_snapshot)
        if latest_snapshot is not None
        else None
    )
    has_new_snapshot = (
        latest_snapshot is not None and signature != previous_last_key
    )
    metrics_required = latest_snapshot is None or has_new_snapshot
    metrics = sim.get_metrics() if metrics_required else None

    snapshot_copy = dict(latest_snapshot) if latest_snapshot is not None else None
    _set_metric_indicators(metrics, snapshot_copy)

    if metrics is not None:
        table_df = pd.DataFrame(
            {
                "Node": list(metrics["pdr_by_node"].keys()),
                "PDR": list(metrics["pdr_by_node"].values()),
                "Recent PDR": [
                    metrics["recent_pdr_by_node"][nid]
                    for nid in metrics["pdr_by_node"].keys()
                ],
            }
        )
        pdr_table.object = table_df
        update_histogram(metrics)

    snapshot_added = False
    if has_new_snapshot and snapshot_copy is not None:
        run_timeline.append(snapshot_copy)
        metrics_timeline_window.append(snapshot_copy)
        metrics_timeline_last_key = signature
        snapshot_added = True
        force_full_refresh = not isinstance(metrics_timeline_pane.object, go.Figure)
        _metrics_timeline_steps_since_refresh += 1
        refresh_due = (
            _metrics_timeline_steps_since_refresh
            >= METRICS_TIMELINE_FULL_REFRESH_INTERVAL
        )
        if force_full_refresh or refresh_due:
            _metrics_timeline_steps_since_refresh = 0
            timeline_for_plot: deque[dict] | list[dict] | None = metrics_timeline_window
            _update_metrics_timeline_pane(timeline_for_plot, force=True)
        else:
            _update_metrics_timeline_pane(
                metrics_timeline_window,
                latest_snapshot=snapshot_copy,
                append=True,
            )
    elif buffer_changed:
        _update_metrics_timeline_pane(metrics_timeline_window, force=True)

    if snapshot_added:
        update_map()
        update_timeline()

    if not cont:
        if current_run >= 1:
            runs_metrics_timeline[current_run - 1] = sim.get_metrics_timeline()
        metrics_timeline_buffer = []
        metrics_timeline_window = _set_metrics_timeline_window([])
        metrics_timeline_last_key = None
        _metrics_timeline_steps_since_refresh = 0
        on_stop(None)
        return


# --- Préparation de la simulation ---
def setup_simulation(seed_offset: int = 0):
    """Crée et démarre un simulateur avec les paramètres du tableau de bord."""
    global sim, sim_callback, map_anim_callback, start_time, chrono_callback, elapsed_time, max_real_time, paused
    global timeline_fig, last_event_index, metrics_timeline_buffer, _metrics_timeline_steps_since_refresh
    global timeline_success_segments, timeline_failure_segments
    global metrics_timeline_last_key, metrics_timeline_window

    # Empêcher de relancer si une simulation est déjà en cours
    if sim is not None and getattr(sim, "running", False):
        export_message.object = "⚠️ Simulation déjà en cours !"
        return

    # Valider que des paquets ou une durée réelle sont définis
    if not _has_simulation_limit_from_inputs() and float(real_time_duration_input.value) <= 0:
        export_message.object = (
            "⚠️ Définissez un nombre de paquets, une durée simulée ou une durée réelle supérieurs à 0 !"
        )
        return

    if not _validate_positive_inputs():
        return

    elapsed_time = 0
    metrics_timeline_buffer = []
    metrics_timeline_window = _set_metrics_timeline_window([])
    metrics_timeline_last_key = None
    _metrics_timeline_steps_since_refresh = 0
    if current_run >= 1:
        if len(runs_metrics_timeline) < current_run:
            runs_metrics_timeline.extend([None] * (current_run - len(runs_metrics_timeline)))
        runs_metrics_timeline[current_run - 1] = []

    if sim_callback:
        sim_callback.stop()
        sim_callback = None
    if map_anim_callback:
        map_anim_callback.stop()
        map_anim_callback = None
    if chrono_callback:
        chrono_callback.stop()
        chrono_callback = None

    timeline_fig = go.Figure()
    last_event_index = 0
    timeline_success_segments.clear()
    timeline_failure_segments.clear()
    timeline_pane.object = timeline_fig

    seed_val = int(seed_input.value)
    seed = seed_val + seed_offset if seed_val != 0 else None

    config_path = None
    path_map = None
    terrain_map = None
    dyn_map = None

    # Choisir le modèle de mobilité
    mobility_instance = None
    if mobility_model_select.value == "Path":
        from launcher.path_mobility import PathMobility
        mobility_instance = PathMobility(
            float(area_input.value),
            path_map or [[0]],
            min_speed=float(mobility_speed_min_input.value),
            max_speed=float(mobility_speed_max_input.value),
            dynamic_obstacles=dyn_map,
        )
    elif mobility_model_select.value == "RandomWaypoint":
        from launcher.random_waypoint import RandomWaypoint
        mobility_instance = RandomWaypoint(
            float(area_input.value),
            min_speed=float(mobility_speed_min_input.value),
            max_speed=float(mobility_speed_max_input.value),
            terrain=terrain_map,
        )
    else:
        from launcher.smooth_mobility import SmoothMobility
        mobility_instance = SmoothMobility(
            float(area_input.value),
            float(mobility_speed_min_input.value),
            float(mobility_speed_max_input.value),
        )


    sim_duration_limit = float(sim_duration_input.value)
    flora_mode_enabled = bool(flora_mode_toggle.value)
    phy_model_name = "flora" if flora_mode_enabled else "omnet"

    sim = Simulator(
        num_nodes=int(num_nodes_input.value),
        num_gateways=int(num_gateways_input.value),
        area_size=float(area_input.value),
        transmission_mode="Random" if mode_select.value == "Aléatoire" else "Periodic",
        packet_interval=float(interval_input.value),
        first_packet_interval=float(first_packet_input.value),
        packets_to_send=int(packets_input.value),
        simulation_duration=(
            sim_duration_limit if sim_duration_limit > 0.0 else None
        ),
        max_sim_time=(sim_duration_limit if sim_duration_limit > 0.0 else None),
        adr_node=adr_node_checkbox.value,
        adr_server=adr_server_checkbox.value,
        mobility=mobility_checkbox.value,
        mobility_speed=(float(mobility_speed_min_input.value), float(mobility_speed_max_input.value)),
        channels=[
            Channel(
                frequency_hz=868e6 + i * 200e3,
                fine_fading_std=float(fine_fading_input.value),
                variable_noise_std=float(noise_std_input.value),
                phy_model=phy_model_name,
                use_flora_curves=flora_mode_enabled,
            )
            for i in range(num_channels_input.value)
        ],
        channel_distribution="random" if channel_dist_select.value == "Aléatoire" else "round-robin",
        fixed_sf=int(sf_value_input.value) if fixed_sf_checkbox.value else None,
        fixed_tx_power=float(tx_power_input.value) if fixed_power_checkbox.value else None,
        battery_capacity_j=float(battery_capacity_input.value) if battery_capacity_input.value > 0 else None,
        payload_size_bytes=int(payload_size_input.value),
        node_class=node_class_select.value,
        detection_threshold_dBm=float(detection_threshold_input.value),
        energy_detection_dBm=(
            Channel.FLORA_ENERGY_DETECTION_DBM if flora_mode_enabled else -float("inf")
        ),
        min_interference_time=float(min_interference_input.value),
        flora_mode=flora_mode_enabled,
        flora_timing=flora_mode_enabled,
        config_file=config_path,
        mobility_model=mobility_instance,
        seed=seed,
        phy_model=phy_model_name,
    )


    if config_path:
        try:
            os.unlink(config_path)
        except OSError:
            pass

    if manual_pos_toggle.value:
        for line in position_textarea.value.splitlines():
            parts = [p.strip() for p in line.split(',') if p.strip()]
            if not parts:
                continue
            kind = parts[0]
            kv = {}
            for p in parts[1:]:
                if '=' in p:
                    k, v = p.split('=', 1)
                    kv[k.strip()] = v.strip()
            try:
                idx = int(kv.get('id', ''))
                x = float(kv.get('x', ''))
                y = float(kv.get('y', ''))
            except ValueError:
                continue
            if kind.startswith('node'):
                for n in sim.nodes:
                    if n.id == idx:
                        n.x = x
                        n.y = y
                        break
            elif kind.startswith('gw') or kind.startswith('gateway'):
                for gw in sim.gateways:
                    if gw.id == idx:
                        gw.x = x
                        gw.y = y
                        break

    # Appliquer le profil ADR sélectionné
    if selected_adr_module:
        selected_adr_module.apply(sim)

    # La mobilité est désormais gérée directement par le simulateur
    start_time = time.time()
    max_real_time = real_time_duration_input.value if real_time_duration_input.value > 0 else None
    pdr_table.object = pd.DataFrame(columns=["Node", "PDR", "Recent PDR"])

    chrono_callback = pn.state.add_periodic_callback(periodic_chrono_update, period=100, timeout=None)

    initial_metrics = sim.get_metrics()
    update_map()
    latest_snapshot = sim.get_latest_metrics_snapshot()
    _set_metric_indicators(initial_metrics, latest_snapshot)
    initial_timeline = sim.get_metrics_timeline()
    initial_records = _timeline_to_records(initial_timeline)
    metrics_timeline_buffer = initial_records
    metrics_timeline_window = _set_metrics_timeline_window(initial_timeline)
    if initial_records:
        metrics_timeline_last_key = _snapshot_signature(initial_records[-1])
    else:
        metrics_timeline_last_key = None
    _update_metrics_timeline_pane(metrics_timeline_window, force=True)
    chrono_indicator.value = 0
    global node_paths
    node_paths = {n.id: [(n.x, n.y)] for n in sim.nodes}
    update_histogram(initial_metrics)
    num_nodes_input.disabled = True
    num_gateways_input.disabled = True
    area_input.disabled = True
    mode_select.disabled = True
    interval_input.disabled = True
    packets_input.disabled = True
    adr_node_checkbox.disabled = True
    adr_server_checkbox.disabled = True
    fixed_sf_checkbox.disabled = True
    sf_value_input.disabled = True
    fixed_power_checkbox.disabled = True
    tx_power_input.disabled = True
    num_channels_input.disabled = True
    channel_dist_select.disabled = True
    mobility_checkbox.disabled = True
    mobility_speed_min_input.disabled = True
    mobility_speed_max_input.disabled = True
    flora_mode_toggle.disabled = True
    detection_threshold_input.disabled = True
    fine_fading_input.disabled = True
    noise_std_input.disabled = True
    min_interference_input.disabled = True
    battery_capacity_input.disabled = True
    payload_size_input.disabled = True
    node_class_select.disabled = True
    seed_input.disabled = True
    num_runs_input.disabled = True
    real_time_duration_input.disabled = True
    sim_duration_input.disabled = True
    start_button.disabled = True
    stop_button.disabled = False
    fast_forward_button.disabled = not _has_simulation_limit_from_sim()
    pause_button.disabled = False
    pause_button.name = "⏸ Pause"
    pause_button.button_type = "primary"
    paused = False
    export_button.disabled = True
    export_message.object = "Cliquez sur Exporter pour générer le fichier CSV après la simulation."

    sim.running = True
    sim_callback = pn.state.add_periodic_callback(step_simulation, period=100, timeout=None)
    cleanup_callback = _cleanup_callbacks

    def anim(cleanup=cleanup_callback):
        if not session_alive():
            cleanup()
            return
        update_map()
        update_timeline()
    map_anim_callback = pn.state.add_periodic_callback(anim, period=200, timeout=None)


# --- Bouton "Lancer la simulation" ---
def on_start(event):
    global total_runs, current_run, runs_events, runs_metrics, runs_metrics_timeline

    # Vérifier qu'une simulation n'est pas déjà en cours
    if sim is not None and getattr(sim, "running", False):
        export_message.object = "⚠️ Simulation déjà en cours !"
        return

    # Valider les entrées avant de démarrer
    if not _has_simulation_limit_from_inputs() and float(real_time_duration_input.value) <= 0:
        export_message.object = (
            "⚠️ Définissez un nombre de paquets, une durée simulée ou une durée réelle supérieurs à 0 !"
        )
        return

    if not _validate_positive_inputs():
        return

    total_runs = int(num_runs_input.value)
    current_run = 1
    runs_events.clear()
    runs_metrics.clear()
    runs_metrics_timeline.clear()
    setup_simulation(seed_offset=0)


# --- Bouton "Arrêter la simulation" ---
def on_stop(event):
    global sim, sim_callback, chrono_callback, map_anim_callback, start_time, max_real_time, paused
    global current_run, total_runs, runs_events, auto_fast_forward, runs_metrics_timeline
    # If called programmatically (e.g. after fast_forward), allow cleanup even
    # if the simulation has already stopped.
    if sim is None or (event is not None and not getattr(sim, "running", False)):
        paused = False
        pause_button.name = "⏸ Pause"
        fast_forward_button.disabled = True
        return

    sim.running = False
    if event is not None:
        auto_fast_forward = False
    if sim_callback:
        sim_callback.stop()
        sim_callback = None
    if map_anim_callback:
        map_anim_callback.stop()
        map_anim_callback = None
    if chrono_callback:
        chrono_callback.stop()
        chrono_callback = None

    try:
        df = sim.get_events_dataframe()
        if df is not None:
            runs_events.append(df.assign(run=current_run))
    except Exception:
        pass
    try:
        runs_metrics.append(sim.get_metrics())
    except Exception:
        pass
    timeline = None
    try:
        timeline = sim.get_metrics_timeline()
        if len(runs_metrics_timeline) < max(current_run, 1):
            runs_metrics_timeline.extend(
                [None] * (max(current_run, 1) - len(runs_metrics_timeline))
            )
        if current_run >= 1:
            runs_metrics_timeline[current_run - 1] = timeline
    except Exception:
        timeline = None

    if current_run < total_runs:
        if runs_metrics:
            aggregated = aggregate_run_metrics(runs_metrics)
            _set_metric_indicators(aggregated)
            # PDR détaillés disponibles dans le fichier exporté uniquement
        current_run += 1
        seed_offset = current_run - 1
        if not _validate_positive_inputs():
            return
        setup_simulation(seed_offset=seed_offset)
        if auto_fast_forward:
            fast_forward()
        return

    num_nodes_input.disabled = False
    num_gateways_input.disabled = False
    area_input.disabled = False
    mode_select.disabled = False
    interval_input.disabled = False
    packets_input.disabled = False
    adr_node_checkbox.disabled = False
    adr_server_checkbox.disabled = False
    fixed_sf_checkbox.disabled = False
    sf_value_input.disabled = not fixed_sf_checkbox.value
    fixed_power_checkbox.disabled = False
    tx_power_input.disabled = not fixed_power_checkbox.value
    num_channels_input.disabled = False
    channel_dist_select.disabled = False
    mobility_checkbox.disabled = False
    mobility_speed_min_input.disabled = False
    mobility_speed_max_input.disabled = False
    flora_mode_toggle.disabled = False
    detection_threshold_input.disabled = False
    fine_fading_input.disabled = False
    noise_std_input.disabled = False
    min_interference_input.disabled = False
    battery_capacity_input.disabled = False
    payload_size_input.disabled = False
    node_class_select.disabled = False
    seed_input.disabled = False
    num_runs_input.disabled = False
    real_time_duration_input.disabled = False
    sim_duration_input.disabled = False
    start_button.disabled = False
    stop_button.disabled = True
    fast_forward_button.disabled = True
    pause_button.disabled = True
    pause_button.name = "⏸ Pause"
    pause_button.button_type = "primary"
    paused = False

    start_time = None
    max_real_time = None
    auto_fast_forward = False
    fast_forward_progress.visible = False
    fast_forward_progress.value = 0
    if runs_metrics:
        aggregated = aggregate_run_metrics(runs_metrics)
        _set_metric_indicators(aggregated)
        last = runs_metrics[-1]
        table_df = pd.DataFrame(
            {
                "Node": list(last["pdr_by_node"].keys()),
                "PDR": list(last["pdr_by_node"].values()),
                "Recent PDR": [
                    last["recent_pdr_by_node"][nid]
                    for nid in last["pdr_by_node"].keys()
                ],
            }
        )
        pdr_table.object = table_df
        # Les tableaux détaillés ne sont plus mis à jour ici
    export_message.object = "✅ Simulation terminée. Tu peux exporter les résultats."
    export_button.disabled = False
    global pause_prev_disabled
    pause_button.disabled = pause_prev_disabled

    _update_metrics_timeline_pane(
        _set_metrics_timeline_window(_get_last_metrics_timeline()),
        force=True,
    )


# --- Export CSV local : Méthode universelle ---
def exporter_csv(event=None):
    """Export simulation results as CSV files in the current directory."""
    dest_dir = os.getcwd()
    global runs_events, runs_metrics, runs_metrics_timeline

    if not runs_events:
        export_message.object = "⚠️ Lance la simulation d'abord !"
        return

    try:
        df = pd.concat(runs_events, ignore_index=True)
        if df.empty:
            export_message.object = "⚠️ Aucune donnée à exporter !"
            return

        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        chemin = os.path.join(dest_dir, f"resultats_simulation_{timestamp}.csv")
        df.to_csv(chemin, index=False, encoding="utf-8")

        metrics_path = os.path.join(dest_dir, f"metrics_{timestamp}.csv")
        timeline_path = os.path.join(dest_dir, f"metrics_timeline_{timestamp}.csv")
        required_instant_cols = (
            "instant_throughput_bps",
            "instant_avg_delay_s",
            "recent_losses",
        )
        if runs_metrics:
            metrics_df = pd.json_normalize(runs_metrics)
            if hasattr(metrics_df, "columns"):
                for column in required_instant_cols:
                    if column not in list(metrics_df.columns):
                        metrics_df[column] = float("nan")
            metrics_df.to_csv(metrics_path, index=False, encoding="utf-8")
        timeline_frames: list[pd.DataFrame] = []
        if runs_metrics_timeline:
            for run_index, timeline in enumerate(runs_metrics_timeline, start=1):
                if timeline is None:
                    continue
                if isinstance(timeline, pd.DataFrame):
                    timeline_df = timeline.copy()
                else:
                    timeline_df = pd.DataFrame(list(timeline))
                if timeline_df.empty:
                    continue
                if hasattr(timeline_df, "columns"):
                    for column in required_instant_cols:
                        if column not in list(timeline_df.columns):
                            timeline_df[column] = float("nan")
                timeline_df = timeline_df.copy()
                timeline_df.insert(0, "run", run_index)
                timeline_frames.append(timeline_df)
        if timeline_frames:
            pd.concat(timeline_frames, ignore_index=True).to_csv(
                timeline_path, index=False, encoding="utf-8"
            )
        else:
            timeline_path = None

        message_lines = [f"✅ Résultats exportés : <b>{chemin}</b>"]
        if runs_metrics:
            message_lines.append(f"Métriques : <b>{metrics_path}</b>")
        if timeline_path:
            message_lines.append(f"Timeline : <b>{timeline_path}</b>")
        message_lines.append("(Ouvre-les avec Excel ou pandas)")
        export_message.object = "<br>".join(message_lines)

        _update_metrics_timeline_pane(
            _set_metrics_timeline_window(_get_last_metrics_timeline()),
            force=True,
        )

        try:
            folder = dest_dir
            if sys.platform.startswith("win"):
                os.startfile(folder)
            else:
                opener = "open" if sys.platform == "darwin" else "xdg-open"
                subprocess.Popen([opener, folder])
        except Exception:
            pass
    except Exception as e:
        export_message.object = f"❌ Erreur lors de l'export : {e}"


export_button.on_click(exporter_csv)


# --- Bouton d'accélération ---
def fast_forward(event=None):
    global sim, sim_callback, chrono_callback, map_anim_callback
    global start_time, max_real_time, auto_fast_forward
    panel_state = _get_panel_state()
    doc = getattr(panel_state, "curdoc", None)
    if doc is None:
        export_message.object = "⚠️ Session Panel indisponible."
        return
    if sim and sim.running:
        if paused:
            export_message.object = "⚠️ Impossible d'accélérer pendant la pause."
            return
        # If no events remain, finalise immediately without spawning a thread
        if not sim.event_queue:
            fast_forward_progress.visible = True
            fast_forward_progress.value = 100
            on_stop(None)
            return
        auto_fast_forward = True
        if not _has_simulation_limit_from_sim():
            auto_fast_forward = False
            export_message.object = (
                "⚠️ Définissez un nombre de paquets par nœud ou une durée simulée supérieure à 0 "
                "pour utiliser l'accélération."
            )
            return

        fast_forward_progress.visible = True
        fast_forward_progress.value = 0

        # Disable pause during fast forward and remember previous state
        global pause_prev_disabled
        pause_prev_disabled = pause_button.disabled
        pause_button.disabled = True

        # Disable buttons during fast forward
        fast_forward_button.disabled = True
        stop_button.disabled = True

        # Stop periodic callbacks to avoid concurrent updates
        if sim_callback:
            sim_callback.stop()
            sim_callback = None
        if map_anim_callback:
            map_anim_callback.stop()
            map_anim_callback = None
        if chrono_callback:
            chrono_callback.stop()
            chrono_callback = None

        # Pause chrono so time does not keep increasing during fast forward
        start_time = None
        max_real_time = None

        current_sim = sim
        current_doc = doc
        current_cleanup = _cleanup_callbacks
        current_on_stop = on_stop
        state_container = _SESSION_STATE

        def current_session_alive() -> bool:
            return session_alive(current_doc, state_container)

        current_fast_forward_progress = fast_forward_progress
        current_export_button = export_button
        current_pause_button = pause_button
        current_update_map = update_map
        current_stop_button = stop_button
        current_fast_forward_button = fast_forward_button

        def run_and_update():
            try:
                total_packets = (
                    current_sim.packets_to_send * current_sim.num_nodes
                    if current_sim.packets_to_send > 0
                    else None
                )
                sim_duration = getattr(
                    current_sim, "max_sim_time", getattr(current_sim, "sim_duration_limit", None)
                )
                last = -1
                while current_sim.event_queue and current_sim.running:
                    current_sim.step()
                    pct: int | None = None
                    if total_packets:
                        pct = int(current_sim.packets_sent / total_packets * 100)
                    reached_time_limit = (
                        sim_duration and sim_duration > 0.0 and current_sim.current_time >= sim_duration
                    )
                    if sim_duration and sim_duration > 0.0:
                        pct = int(min(current_sim.current_time / sim_duration * 100, 100))
                    if reached_time_limit:
                        pct = 100
                    if pct is not None and pct != last:
                        last = pct
                        if current_session_alive():
                            current_doc.add_next_tick_callback(
                                lambda val=pct: setattr(
                                    current_fast_forward_progress, "value", val
                                )
                            )
                    if reached_time_limit:
                        break

                def update_ui():
                    current_fast_forward_progress.value = 100
                    if not current_session_alive():
                        current_cleanup()
                        try:
                            if current_sim is sim:
                                current_on_stop(None)
                        finally:
                            current_export_button.disabled = False
                        return
                    metrics = current_sim.get_metrics()
                    _set_metric_indicators(metrics)
                    # Les détails de PDR ne sont pas affichés en direct
                    sf_dist = metrics["sf_distribution"]
                    sf_fig = go.Figure(
                        data=[go.Bar(x=[f"SF{sf}" for sf in sf_dist.keys()], y=list(sf_dist.values()))]
                    )
                    sf_fig.update_layout(
                        title="Répartition des SF par nœud",
                        xaxis_title="SF",
                        yaxis_title="Nombre de nœuds",
                        yaxis_range=[0, current_sim.num_nodes],
                    )
                    sf_hist_pane.object = sf_fig
                    current_update_map()
                    try:
                        if current_sim is sim:
                            current_on_stop(None)
                    finally:
                        current_export_button.disabled = False
                    current_pause_button.disabled = pause_prev_disabled

                if current_session_alive():
                    current_doc.add_next_tick_callback(update_ui)
                else:
                    current_cleanup()
                    try:
                        if current_sim is sim:
                            current_on_stop(None)
                    finally:
                        current_export_button.disabled = False
            finally:
                def restore_buttons() -> None:
                    sim_running = getattr(current_sim, "running", False)
                    sim_duration_limit = getattr(
                        current_sim, "max_sim_time", getattr(current_sim, "sim_duration_limit", None)
                    )
                    has_limit = (
                        getattr(current_sim, "packets_to_send", 0) > 0
                        or (sim_duration_limit is not None and sim_duration_limit > 0.0)
                    )
                    current_export_button.disabled = False
                    current_pause_button.disabled = pause_prev_disabled
                    current_stop_button.disabled = not sim_running
                    current_fast_forward_button.disabled = (not sim_running) or not has_limit
                    current_fast_forward_progress.value = 100
                    current_fast_forward_progress.visible = False

                if current_session_alive():
                    current_doc.add_next_tick_callback(restore_buttons)
                else:
                    restore_buttons()

        threading.Thread(target=run_and_update, daemon=True).start()


fast_forward_button.on_click(fast_forward)


# --- Bouton "Pause/Reprendre" ---
def on_pause(event=None):
    """Toggle simulation pause state safely."""
    global sim_callback, chrono_callback, start_time, elapsed_time, paused
    if sim is None or not sim.running:
        return

    if not paused:
        # Pausing the simulation
        if sim_callback:
            sim_callback.stop()
            sim_callback = None
        if chrono_callback:
            chrono_callback.stop()
            chrono_callback = None
        if start_time is not None:
            elapsed_time = time.time() - start_time
        start_time = None  # Freeze chrono while paused
        pause_button.name = "▶ Reprendre"
        pause_button.button_type = "success"
        fast_forward_button.disabled = True
        paused = True
    else:
        # Resuming the simulation
        if start_time is None:
            start_time = time.time() - elapsed_time
        if sim_callback is None:
            sim_callback = pn.state.add_periodic_callback(step_simulation, period=100, timeout=None)
        if chrono_callback is None:
            chrono_callback = pn.state.add_periodic_callback(periodic_chrono_update, period=100, timeout=None)
        pause_button.name = "⏸ Pause"
        pause_button.button_type = "primary"
        fast_forward_button.disabled = not _has_simulation_limit_from_sim()
        paused = False


pause_button.on_click(on_pause)


# --- Case à cocher mobilité : pour mobilité à chaud, hors simulation ---
def on_mobility_toggle(event):
    global sim
    if sim and sim.running:
        sim.mobility_enabled = event.new
        if event.new:
            for node in sim.nodes:
                sim.mobility_model.assign(node)
                sim.schedule_mobility(node, sim.current_time + sim.mobility_model.step)


mobility_checkbox.param.watch(on_mobility_toggle, "value")


# --- Activation des champs SF et puissance ---
def on_fixed_sf_toggle(event):
    sf_value_input.disabled = not event.new


def on_fixed_power_toggle(event):
    tx_power_input.disabled = not event.new


fixed_sf_checkbox.param.watch(on_fixed_sf_toggle, "value")
fixed_power_checkbox.param.watch(on_fixed_power_toggle, "value")

# --- Affichage zone manuelle ---
def on_manual_toggle(event):
    position_textarea.visible = event.new

manual_pos_toggle.param.watch(on_manual_toggle, "value")

# --- Mode FLoRa complet ---
def on_flora_toggle(event):
    if event.new:
        detection_threshold_input.value = -110.0
        # En mode FLoRa, la durée minimale d'interférence est fixée à 5 s
        min_interference_input.value = 5.0
        detection_threshold_input.disabled = True
        min_interference_input.disabled = True
        flora_mode_toggle.button_type = "primary"
    else:
        detection_threshold_input.disabled = False
        min_interference_input.disabled = False
        flora_mode_toggle.button_type = "default"

flora_mode_toggle.param.watch(on_flora_toggle, "value")

# --- Mise à jour du bouton d'accélération lorsqu'on change les limites de simulation ---
def on_packets_change(event):
    _refresh_fast_forward_state_from_inputs()


def on_sim_duration_change(event):
    _refresh_fast_forward_state_from_inputs()


packets_input.param.watch(on_packets_change, "value")
sim_duration_input.param.watch(on_sim_duration_change, "value")
heatmap_res_slider.param.watch(update_heatmap, "value")
hist_metric_select.param.watch(lambda event: update_histogram(), "value")
show_paths_checkbox.param.watch(lambda event: update_map(), "value")

_refresh_fast_forward_state_from_inputs()


def _on_adr_select(event):
    module = ADR_MODULES[event.new]
    if module is not selected_adr_module:
        select_adr(module, event.new)


adr_select.param.watch(_on_adr_select, "value")

# --- Associer les callbacks aux boutons ---
start_button.on_click(on_start)
stop_button.on_click(on_stop)
heatmap_button.on_click(toggle_heatmap)

# --- Mise en page du dashboard ---
controls = pn.WidgetBox(
    num_nodes_input,
    num_gateways_input,
    area_input,
    mode_select,
    interval_input,
    first_packet_input,
    packets_input,
    seed_input,
    num_runs_input,
    adr_node_checkbox,
    adr_server_checkbox,
    adr_select,
    fixed_sf_checkbox,
    sf_value_input,
    fixed_power_checkbox,
    tx_power_input,
    num_channels_input,
    channel_dist_select,
    mobility_checkbox,
    mobility_model_select,
    mobility_speed_min_input,
    mobility_speed_max_input,
    flora_mode_toggle,
    detection_threshold_input,
    min_interference_input,
    battery_capacity_input,
    payload_size_input,
    node_class_select,
    sim_duration_input,
    real_time_duration_input,
    pn.Row(start_button, stop_button),
    pn.Row(fast_forward_button, pause_button),
    fast_forward_progress,
    export_button,
    export_message,
)
controls.width = 350

metrics_col = pn.Column(
    chrono_indicator,
    pdr_indicator,
    collisions_indicator,
    energy_indicator,
    delay_indicator,
    throughput_indicator,
    retrans_indicator,
    pdr_table,
)
metrics_col.width = 220

center_col = pn.Column(
    map_pane,
    pn.Row(show_paths_checkbox, heatmap_button, heatmap_res_slider),
    heatmap_pane,
    hist_metric_select,
    sf_hist_pane,
    timeline_pane,
    metrics_timeline_pane,
    pn.Row(
        pn.Column(manual_pos_toggle, position_textarea, width=650),
    ),
    sizing_mode="stretch_width",
)
center_col.width = 650

dashboard = pn.Row(
    controls,
    center_col,
    metrics_col,
    sizing_mode="stretch_width",
)
dashboard.servable(title="Simulateur LoRa")
pn.state.on_session_destroyed(lambda _, cleanup=_cleanup_callbacks: cleanup())
