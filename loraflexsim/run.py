import argparse
import configparser
import csv
import math
import numbers
import operator

import logging
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

try:
    import numpy as _np  # type: ignore

    _REAL_NUMPY = getattr(_np, "__name__", "") == "numpy"
except Exception:  # pragma: no cover - gracefully degrade when numpy missing
    _np = None
    _REAL_NUMPY = False

from traffic.exponential import sample_interval
from traffic.rng_manager import RngManager

from .launcher.non_orth_delta import load_non_orth_delta
PAYLOAD_SIZE = 20  # octets simulés par paquet
_FAST_STEP_RATIO = 0.1


def apply_speed_settings(
    nodes: int,
    steps: int,
    *,
    fast: bool = False,
    sample_size: float | None = None,
    min_fast_steps: int = 600,
) -> tuple[int, int]:
    """Return adjusted ``(nodes, steps)`` for quick simulation passes.

    When ``fast`` is enabled only a fraction of the original steps are simulated
    (10 % by default, but never more than ``min_fast_steps``) and the number of
    nodes is halved to keep contention patterns while reducing runtime.  The
    ``sample_size`` option accepts a fraction between 0 and 1 to explicitly
    trim the simulated duration.  Invalid ``sample_size`` values raise a
    :class:`ValueError` to mirror ``argparse``'s validation.
    """

    if steps <= 0:
        raise ValueError("steps must be > 0")
    if nodes <= 0:
        raise ValueError("nodes must be > 0")
    if fast:
        fast_steps = max(1, int(math.ceil(steps * _FAST_STEP_RATIO)))
        steps = min(steps, max(min_fast_steps, fast_steps))
        nodes = max(1, int(math.ceil(nodes * 0.5)))
    if sample_size is not None:
        if not (0.0 < sample_size <= 1.0):
            raise ValueError("sample_size must be within (0, 1]")
        steps = max(1, int(math.ceil(steps * sample_size)))
    return nodes, steps

# Configuration du logger pour afficher les informations
logging.basicConfig(level=logging.INFO, format="%(message)s")

# Logger dédié aux diagnostics (collisions, etc.)
diag_logger = logging.getLogger("diagnostics")
if not diag_logger.handlers:
    handler = logging.FileHandler("diagnostics.log", mode="w")
    handler.setFormatter(logging.Formatter("%(message)s"))
    diag_logger.addHandler(handler)
diag_logger.setLevel(logging.INFO)


@dataclass(eq=False)
class _Transmission:
    node: int
    start: float
    end: float
    sf: int
    gateway: int
    channel: int
    rssi: float
    status: str = "pending"


def _ensure_positive_int(name: str, value, minimum: int = 1) -> int:
    """Return ``value`` as an int after validating its type and range."""

    if isinstance(value, bool):
        raise TypeError(f"{name} must be an integer, not bool")
    try:
        ivalue = operator.index(value)
    except TypeError as exc:
        raise TypeError(f"{name} must be an integer") from exc
    if ivalue < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return ivalue


def simulate(
    nodes,
    gateways,
    mode,
    interval,
    steps,
    channels=1,
    *,
    first_interval=None,
    fine_fading_std=0.0,
    noise_std=0.0,
    debug_rx=False,
    phy_model="omnet",
    voltage=3.3,
    tx_current=0.06,
    rx_current=0.011,
    idle_current=1e-6,
    rng_manager: RngManager | None = None,
    non_orth_delta: list[list[float]] | None = None,
):
    """Exécute une simulation LoRaFlexSim simplifiée et retourne les métriques.

    Les transmissions peuvent se faire sur plusieurs canaux et plusieurs
    passerelles. Les nœuds sont répartis de façon uniforme sur les ``channels``
    et sur les ``gateways`` disponibles et les collisions ne surviennent
    qu'entre nœuds partageant à la fois le même canal **et** la même passerelle.
    """
    nodes = _ensure_positive_int("nodes", nodes)
    gateways = _ensure_positive_int("gateways", gateways)
    channels = _ensure_positive_int("channels", channels)

    # Accept values that behave like floats (e.g. numpy floating types) while
    # still rejecting integers and booleans to remain consistent with the
    # documented API which expects real-valued parameters.
    if not (
        isinstance(interval, numbers.Real)
        and not isinstance(interval, numbers.Integral)
        and interval > 0
        and math.isfinite(interval)
    ):
        raise ValueError("interval must be a positive float")
    if first_interval is not None and not (
        isinstance(first_interval, numbers.Real)
        and not isinstance(first_interval, numbers.Integral)
        and first_interval > 0
        and math.isfinite(first_interval)
    ):
        raise ValueError("first_interval must be positive float")
    steps = _ensure_positive_int("steps", steps)

    mode_lower = mode.lower()
    if mode_lower not in {"random", "periodic"}:
        raise ValueError("mode must be 'Random' or 'Periodic'")

    if rng_manager is None:
        rng_manager = RngManager(0)

    # Initialisation des compteurs
    total_transmissions = 0
    collisions = 0
    delivered = 0
    energy_consumed = 0.0
    from .launcher.channel import Channel

    channel = Channel(
        tx_current_a=tx_current,
        rx_current_a=rx_current,
        idle_current_a=idle_current,
        voltage_v=voltage,
    )
    if non_orth_delta is not None:
        channel.non_orth_delta = non_orth_delta
    sf_tx_energy: list[float] = [0.0] * 6
    sf_rx_energy: list[float] = [0.0] * 6
    for idx, sf in enumerate(range(7, 13)):
        airtime = channel.airtime(sf, payload_size=PAYLOAD_SIZE)
        sf_tx_energy[idx] = (tx_current - idle_current) * voltage * airtime
        sf_rx_energy[idx] = (rx_current - idle_current) * voltage * airtime
    # Liste des délais de livraison (0 pour chaque paquet car la transmission
    # réussie est immédiate dans ce modèle simplifié)
    delays = []

    # Génération des instants d'émission pour chaque nœud et attribution d'un canal
    send_times = {node: [] for node in range(nodes)}
    if _REAL_NUMPY:
        node_channels = _np.mod(_np.arange(nodes, dtype=_np.int32), channels)
        node_gateways = _np.mod(_np.arange(nodes, dtype=_np.int32), max(1, gateways))
        node_sf = _np.empty(nodes, dtype=_np.int16)
    else:
        node_channels = [node % channels for node in range(nodes)]
        node_gateways = [node % max(1, gateways) for node in range(nodes)]
        node_sf = [0] * nodes
    # Random spreading factor for each node to allow cross-SF interference
    for node in range(nodes):
        sf_value = 7 + rng_manager.get_stream("sf", node).integers(0, 6)
        if _REAL_NUMPY:
            node_sf[node] = sf_value
        else:
            node_sf[node] = sf_value
    # Le paramètre phy_model est présent pour conserver une interface similaire
    # au tableau de bord mais n'influence pas ce modèle simplifié.

    for node in range(nodes):
        rng = rng_manager.get_stream("traffic", node)
        if mode_lower == "periodic":
            # Randomize the initial offset like the full Simulator
            base = first_interval if first_interval is not None else interval
            t = rng.random() * base
            while t < steps:
                send_times[node].append(t)
                t += interval
            send_times[node] = sorted(set(send_times[node]))
        else:  # mode "Random"
            # Génère les instants d'envoi selon une loi exponentielle
            first = first_interval if first_interval is not None else interval
            t = sample_interval(first, rng)
            while t < steps:
                send_times[node].append(t)
                t += sample_interval(interval, rng)


    node_airtime = {
        node: channel.airtime(int(node_sf[node]), payload_size=PAYLOAD_SIZE)
        for node in range(nodes)
    }

    events: dict[float, list[tuple[int, float]]] = {}
    for node, times in send_times.items():
        airtime = node_airtime[node]
        for t in times:
            events.setdefault(t, []).append((node, t + airtime))

    active_transmissions: dict[tuple[int, int], list[_Transmission]] = defaultdict(list)
    time_epsilon = 1e-9

    def finalize_transmission(tx: _Transmission) -> None:
        nonlocal collisions, delivered, delays
        if tx.status == "lost":
            collisions += 1
            if debug_rx:
                logging.debug(
                    f"t={tx.start:.3f} Node {tx.node} GW {tx.gateway} CH {tx.channel} perdu (collision)"
                )
            return
        rng = rng_manager.get_stream("traffic", tx.node)
        success = True
        if fine_fading_std > 0.0 and rng.normal(0.0, fine_fading_std) < -3.0:
            success = False
        if noise_std > 0.0 and rng.normal(0.0, noise_std) > 3.0:
            success = False
        if success:
            delivered += 1
            delays.append(0)
            if debug_rx:
                logging.debug(
                    f"t={tx.start:.3f} Node {tx.node} GW {tx.gateway} CH {tx.channel} reçu"
                )
        else:
            collisions += 1
            if debug_rx:
                logging.debug(
                    f"t={tx.start:.3f} Node {tx.node} GW {tx.gateway} CH {tx.channel} rejeté (bruit)"
                )
            diag_logger.info(
                f"t={tx.start:.3f} gw={tx.gateway} ch={tx.channel} collision=[{tx.node}] cause=noise"
            )

    def cleanup_pair(pair_key: tuple[int, int], current_time: float) -> None:
        transmissions = active_transmissions.get(pair_key)
        if not transmissions:
            return
        remaining: list[_Transmission] = []
        for tx in transmissions:
            if tx.end <= current_time + time_epsilon:
                finalize_transmission(tx)
            else:
                remaining.append(tx)
        if remaining:
            active_transmissions[pair_key] = remaining
        else:
            active_transmissions.pop(pair_key, None)

    def resolve_collisions(pair_key: tuple[int, int], current_time: float) -> None:
        transmissions = active_transmissions.get(pair_key)
        if not transmissions:
            return
        overlapping = [
            tx for tx in transmissions if tx.start <= current_time < tx.end
        ]
        if len(overlapping) <= 1:
            return
        unique_nodes = {tx.node for tx in overlapping}
        if len(unique_nodes) == 1:
            overlap_ids = {id(tx) for tx in overlapping}
            latest_tx = max(overlapping, key=lambda tx: tx.start)
            latest_id = id(latest_tx)
            remaining_after: list[_Transmission] = []
            for tx in transmissions:
                tx_id = id(tx)
                if tx_id == latest_id:
                    remaining_after.append(tx)
                elif tx_id in overlap_ids:
                    finalize_transmission(tx)
                else:
                    remaining_after.append(tx)
            if remaining_after:
                active_transmissions[pair_key] = remaining_after
            else:
                active_transmissions.pop(pair_key, None)
            return
        candidates = [tx for tx in overlapping if tx.status != "lost"]
        if not candidates:
            return
        if non_orth_delta is None:
            if len(candidates) == 1:
                winners = candidates
            else:
                rng = rng_manager.get_stream("traffic", candidates[0].node)
                chosen = rng.choice([tx.node for tx in candidates])
                winners = [
                    next(tx for tx in candidates if tx.node == chosen)
                ]
        else:
            winners: list[_Transmission] = []
            for tx in candidates:
                captured = True
                for other in overlapping:
                    if tx is other:
                        continue
                    diff = tx.rssi - other.rssi
                    th = non_orth_delta[tx.sf - 7][other.sf - 7]
                    if diff < th:
                        captured = False
                        break
                if captured:
                    winners.append(tx)
        nodes_in_collision = [tx.node for tx in overlapping]
        if len(winners) == 1:
            winner = winners[0]
            for tx in overlapping:
                if tx is winner:
                    tx.status = "captured"
                else:
                    tx.status = "lost"
            diag_logger.info(
                f"t={current_time:.3f} gw={pair_key[0]} ch={pair_key[1]} collision={nodes_in_collision} winner={winner.node}"
            )
            if debug_rx:
                for tx in overlapping:
                    if tx is winner:
                        logging.debug(
                            f"t={current_time:.3f} Node {tx.node} GW {pair_key[0]} CH {pair_key[1]} reçu après collision"
                        )
                    else:
                        logging.debug(
                            f"t={current_time:.3f} Node {tx.node} GW {pair_key[0]} CH {pair_key[1]} perdu (collision)"
                        )
        else:
            for tx in overlapping:
                tx.status = "lost"
            diag_logger.info(
                f"t={current_time:.3f} gw={pair_key[0]} ch={pair_key[1]} collision={nodes_in_collision} none"
            )
            if debug_rx:
                for tx in overlapping:
                    logging.debug(
                        f"t={current_time:.3f} Node {tx.node} GW {pair_key[0]} CH {pair_key[1]} perdu (collision)"
                    )

    for t in sorted(events.keys()):
        nodes_ready = events[t]
        if not nodes_ready:
            continue
        node_ids = [node for node, _ in nodes_ready]
        end_times = {node: t_end for node, t_end in nodes_ready}
        pair_map: dict[tuple[int, int], list[int]] = {}
        for n in node_ids:
            key = (int(node_gateways[n]), int(node_channels[n]))
            pair_map.setdefault(key, []).append(int(n))

        for pair_key, nodes_on_ch in pair_map.items():
            cleanup_pair(pair_key, t)
            nb_tx = len(nodes_on_ch)
            if nb_tx == 0:
                continue
            total_transmissions += nb_tx
            energy_consumed += sum(
                sf_tx_energy[int(node_sf[n]) - 7]
                + sf_rx_energy[int(node_sf[n]) - 7]
                for n in nodes_on_ch
            )

            transmissions = active_transmissions[pair_key]
            for n in nodes_on_ch:
                sf_value = int(node_sf[n])
                t_end = end_times[n]
                transmissions.append(
                    _Transmission(
                        node=n,
                        start=t,
                        end=t_end,
                        sf=sf_value,
                        gateway=pair_key[0],
                        channel=pair_key[1],
                        rssi=rng_manager.get_stream("rssi", n).normal(-100.0, 3.0),
                    )
                )

            resolve_collisions(pair_key, t)

    for pair_key in list(active_transmissions.keys()):
        cleanup_pair(pair_key, float("inf"))

    # Calcul des métriques finales
    pdr = (delivered / total_transmissions) * 100 if total_transmissions > 0 else 0
    avg_delay = (sum(delays) / len(delays)) if delays else 0
    throughput_bps = delivered * PAYLOAD_SIZE * 8 / steps if steps > 0 else 0.0

    idle_energy = (nodes + max(1, gateways)) * idle_current * voltage * steps
    energy_consumed += idle_energy

    return (
        delivered,
        collisions,
        pdr,
        energy_consumed,
        avg_delay,
        throughput_bps,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="LoRaFlexSim – Mode CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemples :\n"
            "  # Scénario urbain calé sur FLoRa\n"
            "  python run.py --nodes 100 --gateways 1 --channels 3 --mode random \\\n"
            "    --interval 100 --first-interval 100 --steps 7200 --phy-model flora --seed 42\n\n"
            "  # Scénario 15 km avec le preset longue portée\n"
            "  python run.py --long-range-demo very_long_range --seed 3\n"
        ),
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.ini",
        help="Fichier INI de configuration des paramètres",
    )
    parser.add_argument("--nodes", type=int, default=10, help="Nombre de nœuds")
    parser.add_argument("--gateways", type=int, default=1, help="Nombre de gateways")
    parser.add_argument(
        "--channels", type=int, default=1, help="Nombre de canaux radio"
    )
    parser.add_argument(
        "--mode",
        choices=["random", "periodic"],
        default="random",
        type=str.lower,
        help="Mode de transmission",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=10.0,
        help="Intervalle moyen ou fixe entre transmissions",
    )
    parser.add_argument(
        "--first-interval",
        type=float,
        default=None,
        help="Moyenne exponentielle pour la première transmission",
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=100,
        help="Nombre de pas de temps de la simulation",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help=(
            "Exécute un run tronqué (10 % des pas de temps, au moins 600 s) et "
            "réduit le nombre de nœuds de moitié pour les tests rapides."
        ),
    )
    parser.add_argument(
        "--sample-size",
        type=float,
        default=None,
        help="Fraction (0-1] de la durée totale à simuler pour un run exploratoire",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        help="Nombre d'exécutions à réaliser",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Fichier CSV pour sauvegarder les résultats (optionnel)",
    )
    parser.add_argument(
        "--lorawan-demo",
        action="store_true",
        help="Exécute un exemple LoRaWAN",
    )
    parser.add_argument(
        "--long-range-demo",
        nargs="?",
        const="flora_hata",
        choices=["flora", "flora_hata", "rural_long_range", "very_long_range"],
        help=(
            "Exécute un scénario longue portée reproductible. "
            "Optionnellement, préciser le preset (flora, flora_hata, rural_long_range, very_long_range)."
        ),
    )
    parser.add_argument(
        "--long-range-auto",
        nargs="+",
        type=float,
        metavar=("AREA_KM2", "MAX_DISTANCE_KM"),
        help=(
            "Estime un scénario longue portée à partir d'une surface cible (km²) et "
            "d'une distance maximale (km). La distance est optionnelle et vaut la moitié "
            "du côté si omise."
        ),
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Graine aléatoire pour reproduire les résultats",
    )
    parser.add_argument(
        "--fine-fading",
        type=float,
        default=0.0,
        help="Écart-type du fading fin (dB)",
    )
    parser.add_argument(
        "--noise-std",
        type=float,
        default=0.0,
        help="Écart-type du bruit thermique variable (dB)",
    )
    parser.add_argument(
        "--phy-model",
        choices=["omnet", "flora", "flora_cpp"],
        default="omnet",
        help="Modèle physique à utiliser (omnet, flora ou flora_cpp)",
    )
    parser.add_argument(
        "--voltage",
        type=float,
        default=3.3,
        help="Tension d'alimentation du transceiver (V)",
    )
    parser.add_argument(
        "--tx-current",
        type=float,
        default=0.06,
        help="Courant en émission (A)",
    )
    parser.add_argument(
        "--rx-current",
        type=float,
        default=0.011,
        help="Courant en réception (A)",
    )
    parser.add_argument(
        "--idle-current",
        type=float,
        default=1e-6,
        help="Courant en veille (A)",
    )
    parser.add_argument(
        "--debug-rx",
        action="store_true",
        help="Trace chaque paquet reçu ou rejeté",
    )
    parser.add_argument(
        "--non-orth-matrix",
        dest="non_orth_matrix",
        action="append",
        help=(
            "Chemin vers un fichier JSON/INI décrivant la matrice "
            "NON_ORTH_DELTA. Peut être fourni plusieurs fois pour comparer l'impact "
            "de différentes matrices."
        ),
    )

    # Preliminary parse to load configuration defaults
    pre_args, _ = parser.parse_known_args(argv)
    if pre_args.config and Path(pre_args.config).is_file():
        cp = configparser.ConfigParser()
        cp.read(pre_args.config)
        if cp.has_section("simulation") and "mu_send" in cp["simulation"]:
            mu = float(cp["simulation"]["mu_send"])
            parser.set_defaults(interval=mu, first_interval=mu)

    args = parser.parse_args(argv)

    if args.debug_rx:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.long_range_auto and not (1 <= len(args.long_range_auto) <= 2):
        parser.error("--long-range-auto attend 1 ou 2 valeurs (surface, distance optionnelle)")

    if args.long_range_auto and args.long_range_demo:
        parser.error("--long-range-auto est incompatible avec --long-range-demo")

    if args.runs < 1:
        parser.error("--runs must be >= 1")

    try:
        adjusted_nodes, adjusted_steps = apply_speed_settings(
            args.nodes,
            args.steps,
            fast=args.fast,
            sample_size=args.sample_size,
        )
    except ValueError as exc:
        parser.error(str(exc))
    if (adjusted_nodes, adjusted_steps) != (args.nodes, args.steps):
        logging.info(
            "Mode rapide activé : %d nœuds -> %d, durée %d s -> %d s",
            args.nodes,
            adjusted_nodes,
            args.steps,
            adjusted_steps,
        )
    args.nodes = adjusted_nodes
    args.steps = adjusted_steps

    def _report_long_range(
        simulator,
        params,
        label: str,
        csv_preset: str,
        extra_columns: dict[str, str] | None = None,
    ) -> None:
        metrics = simulator.get_metrics()
        sf = metrics["pdr_by_sf"]

        def _percent(value: float) -> float:
            return value * 100.0

        area_km2 = simulator.area_size ** 2 / 1_000_000.0
        sf12_distances = [
            math.hypot(node.x - simulator.gateways[0].x, node.y - simulator.gateways[0].y)
            for node in simulator.nodes
            if node.sf == 12
        ]
        max_rssi = float("nan")
        max_snr = float("nan")
        successful_sf12 = [
            ev
            for ev in simulator.events_log
            if ev.get("result") == "Success" and ev["sf"] == 12 and ev["rssi_dBm"] is not None
        ]
        if successful_sf12:
            max_rssi = max(ev["rssi_dBm"] for ev in successful_sf12)
            max_snr = max(ev["snr_dB"] for ev in successful_sf12)

        logging.info(
            "Scénario longue portée (%s) : %d nœuds sur %.1f km², TX=%.1f dBm, "
            "gains TX/RX=%.1f/%.1f dBi",
            label,
            len(simulator.nodes),
            area_km2,
            params.tx_power_dBm,
            params.tx_antenna_gain_dB,
            params.rx_antenna_gain_dB,
        )
        logging.info(
            "PDR global %.1f %% | SF12 %.1f %% | SF11 %.1f %% | SF10 %.1f %% | SF9 %.1f %%",
            _percent(metrics["PDR"]),
            _percent(sf[12]),
            _percent(sf[11]),
            _percent(sf[10]),
            _percent(sf[9]),
        )
        logging.info(
            "Distances SF12: %s km | RSSI max SF12 %.1f dBm | SNR max %.1f dB",
            ", ".join(f"{d/1000:.1f}" for d in sf12_distances),
            max_rssi,
            max_snr,
        )

        if args.output:
            header = [
                "preset",
                "area_km2",
                "nodes",
                "packets_per_node",
                "pdr_total_pct",
                "pdr_sf12_pct",
                "pdr_sf11_pct",
                "pdr_sf10_pct",
                "pdr_sf9_pct",
                "max_rssi_sf12_dBm",
                "max_snr_sf12_dB",
            ]
            row = [
                csv_preset,
                f"{area_km2:.3f}",
                len(simulator.nodes),
                params.packets_per_node,
                f"{_percent(metrics['PDR']):.2f}",
                f"{_percent(sf[12]):.2f}",
                f"{_percent(sf[11]):.2f}",
                f"{_percent(sf[10]):.2f}",
                f"{_percent(sf[9]):.2f}",
                f"{max_rssi:.2f}" if successful_sf12 else "",
                f"{max_snr:.2f}" if successful_sf12 else "",
            ]

            if extra_columns:
                for key, value in extra_columns.items():
                    header.append(key)
                    row.append(value)

            with open(args.output, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(header)
                writer.writerow(row)


    if args.long_range_auto:
        from .scenarios import (
            build_simulator_from_suggestion,
            suggest_parameters,
        )

        area_km2 = args.long_range_auto[0]
        max_distance_km = args.long_range_auto[1] if len(args.long_range_auto) == 2 else None
        suggestion = suggest_parameters(area_km2, max_distance_km)
        seed = args.seed if args.seed is not None else 2
        simulator = build_simulator_from_suggestion(suggestion, seed=seed)
        simulator.run()

        logging.info(
            "Suggestion longue portée : surface demandée=%.2f km², surface appliquée=%.2f km², "
            "distance max=%.2f km (références %s → %s, facteur %.2f)",
            area_km2,
            suggestion.area_km2,
            suggestion.max_distance_km,
            suggestion.reference_presets[0],
            suggestion.reference_presets[1],
            suggestion.interpolation_factor,
        )

        extra = {
            "requested_area_km2": f"{area_km2:.3f}",
            "requested_max_distance_km": f"{(max_distance_km if max_distance_km is not None else suggestion.max_distance_km):.3f}",
            "applied_area_km2": f"{suggestion.area_km2:.3f}",
            "applied_max_distance_km": f"{suggestion.max_distance_km:.3f}",
            "reference_lo": suggestion.reference_presets[0],
            "reference_hi": suggestion.reference_presets[1],
            "interpolation_factor": f"{suggestion.interpolation_factor:.3f}",
        }
        _report_long_range(
            simulator,
            suggestion.parameters,
            f"auto ({suggestion.environment})",
            "auto",
            extra_columns=extra,
        )
        return

    if args.long_range_demo:
        from .scenarios import (
            LONG_RANGE_RECOMMENDATIONS,
            build_long_range_simulator,
        )

        preset = args.long_range_demo
        params = LONG_RANGE_RECOMMENDATIONS[preset]
        seed = args.seed if args.seed is not None else 2
        simulator = build_long_range_simulator(preset, seed=seed)
        simulator.run()
        _report_long_range(simulator, params, preset, preset)
        return

    logging.info(
        f"Simulation d'un réseau LoRa : {args.nodes} nœuds, {args.gateways} gateways, "
        f"{args.channels} canaux, mode={args.mode}, "
        f"intervalle={args.interval}, steps={args.steps}, "
        f"first_interval={args.first_interval}"
    )
    if args.lorawan_demo:
        from .launcher.node import Node
        from .launcher.gateway import Gateway
        from .launcher.server import NetworkServer

        gw = Gateway(0, 0, 0)
        ns = NetworkServer(process_delay=0.001)
        ns.gateways = [gw]
        node = Node(0, 0, 0, 7, 20)
        frame = node.prepare_uplink(b"ping", confirmed=True)
        ns.send_downlink(node, b"ack")
        rx1, _ = node.schedule_receive_windows(0)
        gw.pop_downlink(node.id)  # illustration (frame, data_rate, tx_power)
        logging.info(f"Exemple LoRaWAN : trame uplink FCnt={frame.fcnt}, RX1={rx1}s")
        sys.exit()

    matrices = args.non_orth_matrix or [None]
    all_results: list[tuple] = []
    for matrix_path in matrices:
        matrix = load_non_orth_delta(matrix_path) if matrix_path else None
        if matrix_path:
            logging.info(f"Utilisation de la matrice {matrix_path}")
        results = []
        for i in range(args.runs):
            seed = args.seed + i if args.seed is not None else i
            rng_manager = RngManager(seed)

            delivered, collisions, pdr, energy, avg_delay, throughput = simulate(
                args.nodes,
                args.gateways,
                args.mode,
                args.interval,
                args.steps,
                args.channels,
                first_interval=args.first_interval,
                fine_fading_std=args.fine_fading,
                noise_std=args.noise_std,
                debug_rx=args.debug_rx,
                phy_model=args.phy_model,
                voltage=args.voltage,
                tx_current=args.tx_current,
                rx_current=args.rx_current,
                idle_current=args.idle_current,
                rng_manager=rng_manager,
                non_orth_delta=matrix,
            )
            results.append((delivered, collisions, pdr, energy, avg_delay, throughput))
            logging.info(
                f"Run {i + 1}/{args.runs} : PDR={pdr:.2f}% , Paquets livrés={delivered}, Collisions={collisions}, "
                f"Énergie consommée={energy:.3f} J, Délai moyen={avg_delay:.2f} unités de temps, "
                f"Débit moyen={throughput:.2f} bps"
            )

        averages = [
            sum(r[i] for r in results) / len(results) for i in range(len(results[0]))
        ]
        logging.info(
            f"Moyenne : PDR={averages[2]:.2f}% , Paquets livrés={averages[0]:.2f}, Collisions={averages[1]:.2f}, "
            f"Énergie consommée={averages[3]:.3f} J, Délai moyen={averages[4]:.2f} unités de temps, "
            f"Débit moyen={averages[5]:.2f} bps",
        )
        all_results.append((matrix_path, results, tuple(averages)))

        if args.output:
            out_path = args.output
            if matrix_path:
                p = Path(args.output)
                out_path = str(p.with_name(f"{p.stem}_{Path(matrix_path).stem}{p.suffix}"))
            with open(out_path, mode="w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "nodes",
                        "gateways",
                        "channels",
                        "mode",
                        "interval",
                        "steps",
                        "run",
                        "delivered",
                        "collisions",
                        "PDR(%)",
                        "energy_J",
                        "avg_delay",
                        "throughput_bps",
                    ]
                )
                for run_idx, (d, c, p_val, e, ad, th) in enumerate(results, start=1):
                    writer.writerow(
                        [
                            args.nodes,
                            args.gateways,
                            args.channels,
                            args.mode,
                            args.interval,
                            args.steps,
                            run_idx,
                            d,
                            c,
                            f"{p_val:.2f}",
                            f"{e:.3f}",
                            f"{ad:.2f}",
                            f"{th:.2f}",
                        ]
                    )
            logging.info(f"Résultats enregistrés dans {out_path}")

    return all_results


if __name__ == "__main__":
    main()
