"""Event-driven LoRa simulator."""

import heapq
import logging
import random
import numpy as np

from traffic.exponential import sample_interval
from traffic.rng_manager import RngManager
from pathlib import Path
from dataclasses import dataclass


# Earlier versions used integer nanoseconds for event timestamps to mimic
# OMNeT++'s scheduler tick.  For validation scenarios we rely on continuous
# double precision times, hence events directly store their timestamp in
# seconds as ``float`` values.  This avoids any quantisation effects that could
# slightly bias statistics when using sub-second intervals.
from enum import IntEnum

try:
    import pandas as pd
except Exception:  # pragma: no cover - pandas optional
    pd = None

from .node import Node
from .gateway import Gateway
from .channel import Channel
from .multichannel import MultiChannel
from .server import NetworkServer
from .duty_cycle import DutyCycleManager
from .smooth_mobility import SmoothMobility
from .id_provider import next_node_id, next_gateway_id, reset as reset_ids


class EventType(IntEnum):
    """Types d'événements traités par le simulateur."""

    TX_END = 0
    TX_START = 1
    MOBILITY = 2
    RX_WINDOW = 3
    BEACON = 4
    PING_SLOT = 5
    SERVER_RX = 6
    SERVER_PROCESS = 7


@dataclass(order=True, slots=True)
class Event:
    time: float
    type: int
    id: int
    node_id: int


logger = logging.getLogger(__name__)
diag_logger = logging.getLogger("diagnostics")


class Simulator:
    """Gère la simulation du réseau LoRa (nœuds, passerelles, événements)."""

    # Constantes ADR LoRaWAN standard
    REQUIRED_SNR = {7: -7.5, 8: -10.0, 9: -12.5, 10: -15.0, 11: -17.5, 12: -20.0}
    MARGIN_DB = 15.0  # marge d'installation en dB (typiquement 15 dB)

    def __init__(
        self,
        num_nodes: int = 10,
        num_gateways: int = 1,
        area_size: float = 1000.0,
        transmission_mode: str = "Random",
        packet_interval: float = 60.0,
        first_packet_interval: float | None = None,
        warm_up_intervals: int = 0,
        log_mean_after: int | None = None,
        interval_variation: float = 0.0,
        packets_to_send: int = 0,
        adr_node: bool = False,
        adr_server: bool = False,
        adr_method: str = "max",
        duty_cycle: float | None = 0.01,
        mobility: bool = True,
        channels=None,
        channel_distribution: str = "round-robin",
        mobility_speed: tuple[float, float] = (2.0, 10.0),
        fixed_sf: int | None = None,
        fixed_tx_power: float | None = None,
        battery_capacity_j: float | None = None,
        payload_size_bytes: int = 20,
        node_class: str = "A",
        detection_threshold_dBm: float = -float("inf"),
        min_interference_time: float = 0.0,
        flora_mode: bool = False,
        flora_timing: bool = False,
        config_file: str | None = None,
        seed: int | None = None,
        class_c_rx_interval: float = 1.0,
        phy_model: str = "",
        flora_loss_model: str = "lognorm",
        terrain_map: str | list[list[float]] | None = None,
        path_map: str | list[list[float]] | None = None,
        dynamic_obstacles: str | list[dict] | None = None,
        mobility_model=None,
        beacon_drift: float = 0.0,
        *,
        clock_accuracy: float = 0.0,
        beacon_loss_prob: float = 0.0,
        ping_slot_interval: float = 1.0,
        ping_slot_offset: float = 2.0,
        debug_rx: bool = False,
        dump_intervals: bool = False,
        pure_poisson_mode: bool = False,
        lock_step_poisson: bool = False,
        phase_noise_std_dB: float = 0.0,
        clock_jitter_std_s: float = 0.0,
        pa_ramp_up_s: float = 0.0,
        pa_ramp_down_s: float = 0.0,
    ):
        """
        Initialise la simulation LoRa avec les entités et paramètres donnés.
        :param num_nodes: Nombre de nœuds à simuler.
        :param num_gateways: Nombre de passerelles à simuler.
        :param area_size: Taille de l'aire carrée (mètres) dans laquelle sont déployés nœuds et passerelles.
        :param transmission_mode: 'Random' pour transmissions aléatoires (Poisson) ou 'Periodic' pour périodiques.
        :param packet_interval: Intervalle moyen entre transmissions (si Random, moyenne en s; si Periodic, période fixe en s).
        :param first_packet_interval: Intervalle moyen appliqué uniquement au tout premier envoi (``None`` pour utiliser ``packet_interval``).
        :param warm_up_intervals: Nombre d'intervalles à ignorer dans les métriques (warm-up).
        :param log_mean_after: Nombre d'intervalles comptabilisés après warm-up
            avant journalisation de la moyenne empirique (``None`` pour désactiver).
        :param interval_variation: Jitter relatif appliqué à chaque intervalle
            exponentiel. La valeur par défaut ``0`` reproduit fidèlement le
            modèle aléatoire de FLoRa (aucune dispersion supplémentaire).
        :param packets_to_send: Nombre de paquets à émettre **par nœud** avant
            d'arrêter la simulation (0 = infini).
        :param adr_node: Activation de l'ADR côté nœud.
        :param adr_server: Activation de l'ADR côté serveur.
        :param adr_method: Méthode d'agrégation du SNR pour l'ADR
            (``"max"`` ou ``"avg"``).
        :param duty_cycle: Facteur de duty cycle (ex: 0.01 pour 1 %). Par
            défaut à 0.01. Si None, le duty cycle est désactivé.
        :param mobility: Active la mobilité aléatoire des nœuds lorsqu'il est
            à True.
        :param mobility_speed: Couple (min, max) définissant la plage de
            vitesses de déplacement des nœuds en m/s lorsqu'ils sont mobiles.
        :param channels: ``MultiChannel`` ou liste de fréquences/``Channel`` pour
            gérer plusieurs canaux.
        :param channel_distribution: Méthode d'affectation des canaux aux nœuds
            ("round-robin" ou "random").
        :param fixed_sf: Si défini, tous les nœuds démarrent avec ce SF.
        :param fixed_tx_power: Si défini, puissance d'émission initiale commune (dBm).
        :param battery_capacity_j: Capacité de la batterie attribuée à chaque nœud (J). ``None`` pour illimité.
        :param payload_size_bytes: Taille du payload utilisé pour calculer l'airtime (octets).
        :param node_class: Classe LoRaWAN commune à tous les nœuds ('A', 'B' ou 'C').
        :param detection_threshold_dBm: RSSI minimal requis pour qu'une
            réception soit prise en compte.
        :param min_interference_time: Chevauchement temporel toléré entre
            transmissions avant de les considérer en collision (s).
        :param flora_mode: Active automatiquement les réglages du mode FLoRa
            complet (seuil -110 dBm et 5 s d'interférence minimale).
        :param flora_timing: Utilise les temporisations du projet FLoRa
            (délai réseau de 10 ms et traitement serveur de 1,2 s).
        :param config_file: Fichier INI listant les positions des nœuds et
            passerelles à charger. Lorsque défini, ``num_nodes`` et
            ``num_gateways`` sont ignorés.
        :param seed: Graine aléatoire pour reproduire le placement des nœuds et
            l'ordre statistique des intervalles. ``None`` pour un tirage
            différent à chaque exécution.
        :param class_c_rx_interval: Période entre deux vérifications de
            downlink pour les nœuds de classe C (s).
        :param phy_model: "omnet" ou "flora" pour activer un modèle physique
            inspiré de FLoRa.
        :param flora_loss_model: Variante d'atténuation FLoRa ("lognorm",
            "oulu" ou "hata").
        :param terrain_map: Carte de terrain utilisée pour la mobilité
            aléatoire (chemin JSON/texte ou matrice). Les valeurs négatives
            indiquent les obstacles et ralentissements éventuels.
        :param path_map: Carte de type obstacle où un chemin doit être trouvé
            entre deux positions. Lorsque défini, la mobilité suit les
            plus courts chemins évitant les obstacles.
        :param dynamic_obstacles: Fichier JSON ou liste décrivant des obstacles
            mouvants pour ``PathMobility``.
        :param mobility_model: Instance personnalisée de modèle de mobilité
            (prioritaire sur ``terrain_map`` et ``path_map``).
        :param beacon_drift: Dérive relative appliquée aux beacons (ppm).
        :param clock_accuracy: Écart-type de la dérive d'horloge des nœuds
            (ppm). Chaque nœud se voit attribuer un décalage aléatoire selon
            cette précision.
        :param beacon_loss_prob: Probabilité pour un nœud de manquer un beacon.
        :param ping_slot_interval: Intervalle de base entre deux ping slots
            (s).
        :param ping_slot_offset: Décalage initial entre le beacon et le premier
            ping slot (s).
        :param debug_rx: Active la journalisation détaillée des paquets reçus ou rejetés.
        :param dump_intervals: Exporte la série complète des intervalles dans un fichier Parquet.
        :param lock_step_poisson: Prégénère la séquence Poisson une seule fois et la réutilise.
        :param phase_noise_std_dB: Bruit de phase appliqué au SNR (écart-type en dB).
        :param clock_jitter_std_s: Gigue d'horloge ajoutée à chaque calcul (s).
        :param pa_ramp_up_s: Temps de montée du PA (s).
        :param pa_ramp_down_s: Temps de descente du PA (s).
        """
        # Paramètres de simulation
        if flora_mode and packet_interval == 60.0 and first_packet_interval is None:
            packet_interval = first_packet_interval = 1000.0

        self.num_nodes = num_nodes
        self.num_gateways = num_gateways
        self.area_size = area_size
        self.transmission_mode = transmission_mode
        self.packet_interval = packet_interval
        self.first_packet_interval = (
            first_packet_interval
            if first_packet_interval is not None
            else packet_interval
        )
        # Minimal delay before the first transmission (5 s in FLoRa mode)
        self.first_packet_min_delay = 0.0
        self.warm_up_intervals = warm_up_intervals
        self.log_mean_after = log_mean_after
        if interval_variation < 0 or interval_variation > 3:
            raise ValueError("interval_variation must be between 0 and 3")
        self.interval_variation = interval_variation
        self.packets_to_send = packets_to_send
        self.adr_node = adr_node
        self.adr_server = adr_server
        self.adr_method = adr_method
        self.fixed_sf = fixed_sf
        self.fixed_tx_power = fixed_tx_power
        self.battery_capacity_j = battery_capacity_j
        self.payload_size_bytes = payload_size_bytes
        self.node_class = node_class
        if flora_mode:
            if detection_threshold_dBm == -float("inf"):
                detection_threshold_dBm = -110.0
            if min_interference_time == 0.0:
                min_interference_time = 5.0
            if self.first_packet_min_delay == 0.0:
                self.first_packet_min_delay = 5.0
        if pure_poisson_mode:
            duty_cycle = None
            detection_threshold_dBm = -float("inf")
            min_interference_time = float("inf")
        self.detection_threshold_dBm = detection_threshold_dBm
        self.min_interference_time = min_interference_time
        self.pure_poisson_mode = pure_poisson_mode
        self.lock_step_poisson = lock_step_poisson
        self.flora_mode = flora_mode
        self.flora_timing = flora_timing
        self.config_file = config_file
        self.phy_model = phy_model
        self.flora_loss_model = flora_loss_model
        self.phase_noise_std_dB = phase_noise_std_dB
        self.clock_jitter_std_s = clock_jitter_std_s
        self.pa_ramp_up_s = pa_ramp_up_s
        self.pa_ramp_down_s = pa_ramp_down_s
        # Activation ou non de la mobilité des nœuds
        self.mobility_enabled = mobility
        if mobility_model is not None:
            self.mobility_model = mobility_model
        elif path_map is not None:
            if isinstance(path_map, (str, Path)):
                from .map_loader import load_map

                path_map = load_map(path_map)
            from .path_mobility import PathMobility

            self.mobility_model = PathMobility(
                area_size,
                path_map,
                min_speed=mobility_speed[0],
                max_speed=mobility_speed[1],
                dynamic_obstacles=dynamic_obstacles,
            )
        elif terrain_map is not None:
            if isinstance(terrain_map, (str, Path)):
                from .map_loader import load_map

                terrain_map = load_map(terrain_map)
            from .random_waypoint import RandomWaypoint

            self.mobility_model = RandomWaypoint(
                area_size,
                min_speed=mobility_speed[0],
                max_speed=mobility_speed[1],
                terrain=terrain_map,
            )
        else:
            self.mobility_model = SmoothMobility(
                area_size, mobility_speed[0], mobility_speed[1]
            )

        # Class B/C settings
        self.beacon_interval = 128.0
        self.ping_slot_interval = ping_slot_interval
        self.ping_slot_offset = ping_slot_offset
        self.class_c_rx_interval = class_c_rx_interval
        self.beacon_drift = beacon_drift
        self.clock_accuracy = clock_accuracy
        self.beacon_loss_prob = beacon_loss_prob
        self.debug_rx = debug_rx
        self.dump_intervals = dump_intervals

        # Gestion du duty cycle (activé par défaut à 1 %)
        self.duty_cycle_manager = DutyCycleManager(duty_cycle) if duty_cycle else None

        # Initialiser la gestion multi-canaux
        if isinstance(channels, MultiChannel):
            self.multichannel = channels
            if detection_threshold_dBm != -float("inf"):
                for ch in self.multichannel.channels:
                    ch.detection_threshold_dBm = detection_threshold_dBm
            if flora_mode:
                for ch in self.multichannel.channels:
                    ch.phy_model = "omnet_full"
            if flora_mode or phy_model.startswith("flora"):
                for ch in self.multichannel.channels:
                    if getattr(ch, "environment", None) is None:
                        ch.environment = "flora"
                        (
                            ch.path_loss_exp,
                            ch.shadowing_std,
                            ch.path_loss_d0,
                            ch.reference_distance,
                        ) = Channel.ENV_PRESETS["flora"]
                for ch in self.multichannel.channels:
                    if flora_mode and ch.multipath_taps <= 1:
                        ch.multipath_taps = 3
            for ch in self.multichannel.channels:
                ch.phase_noise_std_dB = phase_noise_std_dB
                ch.clock_jitter_std_s = clock_jitter_std_s
                ch.pa_ramp_up_s = pa_ramp_up_s
                ch.pa_ramp_down_s = pa_ramp_down_s
                if hasattr(ch, "_phase_noise"):
                    ch._phase_noise.std = phase_noise_std_dB
                if getattr(ch, "omnet_phy", None):
                    ch.omnet_phy.clock_jitter_std_s = clock_jitter_std_s
                    ch.omnet_phy.pa_ramp_up_s = pa_ramp_up_s
                    ch.omnet_phy.pa_ramp_down_s = pa_ramp_down_s
                    ch.omnet_phy._phase_noise.std = phase_noise_std_dB
        else:
            if channels is None:
                env = "flora" if (flora_mode or phy_model.startswith("flora")) else None
                ch_phy_model = "omnet_full" if flora_mode else phy_model
                ch_list = [
                    Channel(
                        detection_threshold_dBm=detection_threshold_dBm,
                        phy_model=ch_phy_model,
                        environment=env,
                        flora_loss_model=flora_loss_model,
                        multipath_taps=3 if flora_mode else 1,
                        phase_noise_std_dB=phase_noise_std_dB,
                        clock_jitter_std_s=clock_jitter_std_s,
                        pa_ramp_up_s=pa_ramp_up_s,
                        pa_ramp_down_s=pa_ramp_down_s,
                    )
                ]
            else:
                ch_list = []
                for ch in channels:
                    if isinstance(ch, Channel):
                        if detection_threshold_dBm != -float("inf"):
                            ch.detection_threshold_dBm = detection_threshold_dBm
                        if flora_mode:
                            ch.phy_model = "omnet_full"
                        if (flora_mode or phy_model.startswith("flora")) and getattr(
                            ch, "environment", None
                        ) is None:
                            ch.environment = "flora"
                            (
                                ch.path_loss_exp,
                                ch.shadowing_std,
                                ch.path_loss_d0,
                                ch.reference_distance,
                            ) = Channel.ENV_PRESETS["flora"]
                        if flora_mode and ch.multipath_taps <= 1:
                            ch.multipath_taps = 3
                        ch.phase_noise_std_dB = phase_noise_std_dB
                        ch.clock_jitter_std_s = clock_jitter_std_s
                        ch.pa_ramp_up_s = pa_ramp_up_s
                        ch.pa_ramp_down_s = pa_ramp_down_s
                        if hasattr(ch, "_phase_noise"):
                            ch._phase_noise.std = phase_noise_std_dB
                        if getattr(ch, "omnet_phy", None):
                            ch.omnet_phy.clock_jitter_std_s = clock_jitter_std_s
                            ch.omnet_phy.pa_ramp_up_s = pa_ramp_up_s
                            ch.omnet_phy.pa_ramp_down_s = pa_ramp_down_s
                            ch.omnet_phy._phase_noise.std = phase_noise_std_dB
                        ch_list.append(ch)
                    else:
                        ch_list.append(
                            Channel(
                                frequency_hz=float(ch),
                                detection_threshold_dBm=detection_threshold_dBm,
                                phy_model="omnet_full" if flora_mode else phy_model,
                                environment=(
                                    "flora"
                                    if (flora_mode or phy_model.startswith("flora"))
                                    else None
                                ),
                                flora_loss_model=flora_loss_model,
                                multipath_taps=3 if flora_mode else 1,
                                phase_noise_std_dB=phase_noise_std_dB,
                                clock_jitter_std_s=clock_jitter_std_s,
                                pa_ramp_up_s=pa_ramp_up_s,
                                pa_ramp_down_s=pa_ramp_down_s,
                            )
                        )
            self.multichannel = MultiChannel(ch_list, method=channel_distribution)

        # Compatibilité : premier canal par défaut
        self.channel = self.multichannel.channels[0]
        # Réglages de temporisation inspirés de FLoRa
        if flora_timing:
            proc_delay = 1.2
            net_delay = 0.01
        else:
            proc_delay = 0.0
            net_delay = 0.0
        # Traiter immédiatement les paquets reçus pour éviter un retard artificiel
        self.network_server = NetworkServer(
            simulator=self,
            process_delay=proc_delay,
            network_delay=net_delay,
            adr_method=self.adr_method,
        )
        self.network_server.beacon_interval = self.beacon_interval
        self.network_server.beacon_drift = self.beacon_drift
        self.network_server.ping_slot_interval = self.ping_slot_interval
        self.network_server.ping_slot_offset = self.ping_slot_offset

        # Graine commune pour reproduire FLoRa (placement et tirages aléatoires)
        self.seed = seed
        stream_hash = 3091881735
        self.rng_manager = RngManager((self.seed or 0) ^ stream_hash)
        self.pos_rng = random.Random(self.seed)
        self.interval_rng = self.rng_manager.get_stream("traffic", 0)
        if self.seed is not None:
            random.seed(self.seed)

        # Générer les passerelles
        self.gateways = []
        reset_ids()
        cfg_nodes = None
        cfg_gateways = None
        if config_file:
            from .config_loader import load_config

            cfg_nodes, cfg_gateways, mean_interval, first_mean = load_config(
                config_file
            )
            if cfg_gateways:
                self.num_gateways = len(cfg_gateways)
            if cfg_nodes:
                self.num_nodes = len(cfg_nodes)
            if mean_interval is not None:
                self.packet_interval = mean_interval
            if first_mean is not None:
                self.first_packet_interval = first_mean

        for idx in range(self.num_gateways):
            gw_id = next_gateway_id()
            if cfg_gateways and idx < len(cfg_gateways):
                gw_x = cfg_gateways[idx]["x"]
                gw_y = cfg_gateways[idx]["y"]
            elif self.num_gateways == 1:
                gw_x = area_size / 2.0
                gw_y = area_size / 2.0
            else:
                gw_x = self.pos_rng.random() * area_size
                gw_y = self.pos_rng.random() * area_size
            self.gateways.append(Gateway(gw_id, gw_x, gw_y))

        # Générer les nœuds aléatoirement dans l'aire et assigner un SF/power initiaux
        self.nodes = []
        for idx in range(self.num_nodes):
            node_id = next_node_id()
            if cfg_nodes and idx < len(cfg_nodes):
                ncfg = cfg_nodes[idx]
                x = ncfg["x"]
                y = ncfg["y"]
                sf = ncfg.get(
                    "sf",
                    (
                        self.fixed_sf
                        if self.fixed_sf is not None
                        else random.randint(7, 12)
                    ),
                )
                tx_power = ncfg.get(
                    "tx_power",
                    self.fixed_tx_power if self.fixed_tx_power is not None else 14.0,
                )
            else:
                x = self.pos_rng.random() * area_size
                y = self.pos_rng.random() * area_size
                sf = (
                    self.fixed_sf
                    if self.fixed_sf is not None
                    else random.randint(7, 12)
                )
                tx_power = (
                    self.fixed_tx_power if self.fixed_tx_power is not None else 14.0
                )
            channel = self.multichannel.select_mask(0xFFFF)
            node = Node(
                node_id,
                x,
                y,
                sf,
                tx_power,
                channel=channel,
                class_type=self.node_class,
                battery_capacity_j=self.battery_capacity_j,
                beacon_loss_prob=self.beacon_loss_prob,
                beacon_drift=(
                    random.gauss(0.0, self.clock_accuracy)
                    if self.clock_accuracy > 0.0
                    else 0.0
                ),
            )
            node._warmup_remaining = self.warm_up_intervals
            node._log_after = self.log_mean_after
            # Enregistrer les états initiaux du nœud pour rapport ultérieur
            node.initial_x = x
            node.initial_y = y
            node.initial_sf = sf
            node.initial_tx_power = tx_power
            # Attributs supplémentaires pour mobilité et ADR
            node.history = (
                []
            )  # Historique des 20 dernières transmissions (snr, delivered)
            node.in_transmission = (
                False  # Indique si le nœud est actuellement en transmission
            )
            node.current_end_time = None  # Instant de fin de la transmission en cours (si in_transmission True)
            node.last_rssi = (
                None  # Dernier meilleur RSSI mesuré pour la transmission en cours
            )
            node.last_snr = (
                None  # Dernier meilleur SNR mesuré pour la transmission en cours
            )
            if self.mobility_enabled:
                self.mobility_model.assign(node)
            node.rng = self.rng_manager.get_stream("traffic", node_id)
            self.nodes.append(node)

        # Configurer le serveur réseau avec les références pour ADR
        self.network_server.adr_enabled = self.adr_server
        self.network_server.nodes = self.nodes
        self.network_server.gateways = self.gateways
        self.network_server.channel = self.channel

        # File d'événements (min-heap)
        self.event_queue: list[Event] = []
        self.node_map = {node.id: node for node in self.nodes}
        self.current_time = 0.0
        self.event_id_counter = 0

        # Statistiques cumulatives
        self.packets_sent = 0
        self.packets_delivered = 0
        self.packets_lost_collision = 0
        self.packets_lost_no_signal = 0
        self.total_energy_J = 0.0
        self.total_delay = 0.0
        self.delivered_count = 0
        # Counters for PDR computation
        self.tx_attempted = 0
        self.rx_delivered = 0
        self.retransmissions = 0

        # Journal des événements (pour export CSV)
        self.events_log: list[dict] = []

        # Planifier le premier envoi de chaque nœud
        for node in self.nodes:
            if self.transmission_mode.lower() == "random":
                if self.lock_step_poisson:
                    if self.packets_to_send == 0:
                        raise ValueError(
                            "lock_step_poisson requires packets_to_send > 0"
                        )
                    node.precompute_poisson_arrivals(
                        self.packet_interval,
                        self.packets_to_send,
                        self.interval_rng,
                        variation=self.interval_variation,
                    )
                else:
                    node.ensure_poisson_arrivals(
                        node.last_tx_time,
                        self.packet_interval,
                        self.interval_rng,
                        min_interval=max(
                            node.last_airtime, self.first_packet_min_delay
                        ),
                        variation=self.interval_variation,
                        limit=(self.packets_to_send if self.packets_to_send else None),
                    )
                t0 = node.arrival_queue.pop(0)
            else:
                t0 = random.random() * self.packet_interval
                node.arrival_queue.append(t0)
                node.arrival_interval_sum += t0
                node.arrival_interval_count += 1
                node._last_arrival_time = t0
            self.schedule_event(
                node,
                t0,
                reason=(
                    "poisson"
                    if self.transmission_mode.lower() == "random"
                    else "periodic"
                ),
            )
            # Planifier le premier changement de position si la mobilité est activée
            if self.mobility_enabled:
                self.schedule_mobility(node, self.mobility_model.step)
            if node.class_type.upper() in ("B", "C"):
                eid = self.event_id_counter
                self.event_id_counter += 1
                heapq.heappush(
                    self.event_queue,
                    Event(0.0, EventType.RX_WINDOW, eid, node.id),
                )

        # Première émission de beacon pour la synchronisation Class B
        eid = self.event_id_counter
        self.event_id_counter += 1
        heapq.heappush(
            self.event_queue,
            Event(0.0, EventType.BEACON, eid, 0),
        )
        self.last_beacon_time = 0.0
        self.network_server.last_beacon_time = 0.0

        # Indicateur d'exécution de la simulation
        self.running = True

    def schedule_event(self, node: Node, time: float, *, reason: str = "poisson"):
        """Planifie un événement de transmission pour un nœud."""
        if not node.alive:
            return
        requested_time = time
        if (
            not self.pure_poisson_mode
            and node.current_end_time is not None
            and time < node.current_end_time
        ):
            time = node.current_end_time
            reason = "overlap"
        event_id = self.event_id_counter
        self.event_id_counter += 1
        if self.duty_cycle_manager and not self.pure_poisson_mode:
            enforced = self.duty_cycle_manager.enforce(node.id, time)
            if enforced > time:
                time = enforced
                reason = "duty_cycle"
        node.channel = self.multichannel.select_mask(getattr(node, "chmask", 0xFFFF))
        heapq.heappush(
            self.event_queue,
            Event(time, EventType.TX_START, event_id, node.id),
        )
        node.interval_log.append(
            {
                "poisson_time": requested_time,
                "tx_time": time,
                "reason": reason,
            }
        )
        logger.debug(
            f"Scheduled transmission {event_id} for node {node.id} at t={time:.2f}s"
        )

    def schedule_mobility(self, node: Node, time: float):
        """Planifie un événement de mobilité (déplacement aléatoire) pour un nœud à l'instant donné."""
        if not node.alive:
            return
        event_id = self.event_id_counter
        self.event_id_counter += 1
        heapq.heappush(
            self.event_queue,
            Event(time, EventType.MOBILITY, event_id, node.id),
        )
        logger.debug(
            f"Scheduled mobility {event_id} for node {node.id} at t={time:.2f}s"
        )

    def step(self) -> bool:
        """Exécute le prochain événement planifié. Retourne False si plus d'événement à traiter."""
        if not self.running or not self.event_queue:
            return False
        # Extraire le prochain événement (le plus tôt dans le temps)
        event = heapq.heappop(self.event_queue)
        time = event.time
        priority = event.type
        event_id = event.id
        node = self.node_map.get(event.node_id)
        if node is None and priority != EventType.BEACON:
            return True
        # Avancer le temps de simulation et mettre à jour l'état PHY
        delta = time - self.current_time
        self.current_time = time
        if delta > 0:
            for ch in self.multichannel.channels:
                if getattr(ch, "omnet_phy", None):
                    ch.omnet_phy.update(delta)
        if node is not None:
            node.consume_until(time)
            if not node.alive:
                return True

        if priority == EventType.TX_START:
            # Début d'une transmission émise par 'node'
            node_id = node.id
            node.last_tx_time = time
            if node._nb_trans_left <= 0:
                node._nb_trans_left = max(1, node.nb_trans)
            node._nb_trans_left -= 1
            if getattr(node.channel, "omnet_phy", None):
                node.channel.omnet_phy.start_tx()
            sf = node.sf
            tx_power = node.tx_power
            # Durée de la transmission
            duration = node.channel.airtime(sf, payload_size=self.payload_size_bytes)
            node.last_airtime = duration
            node.total_airtime += duration
            end_time = time + duration
            if self.duty_cycle_manager and not self.pure_poisson_mode:
                self.duty_cycle_manager.update_after_tx(node_id, time, duration)
            # Mettre à jour les compteurs de paquets émis
            self.packets_sent += 1
            self.tx_attempted += 1
            node.increment_sent()
            # Énergie consommée par la transmission (E = I * V * t)
            current_a = node.profile.get_tx_current(tx_power)
            energy_J = current_a * node.profile.voltage_v * duration
            preamble_J = (
                node.profile.preamble_current_a
                * node.profile.voltage_v
                * node.profile.preamble_time_s
            )
            self.total_energy_J += energy_J + preamble_J
            if preamble_J > 0.0:
                node.add_energy(preamble_J, "preamble")
            node.add_energy(energy_J, "tx")
            if not node.alive:
                return True
            node.state = "tx"
            node.last_state_time = end_time
            # Marquer le nœud comme en cours de transmission
            node.in_transmission = True
            node.current_end_time = end_time

            # Actualiser les offsets temps/fréquence utilisés pour cette émission
            if hasattr(node, "update_offsets"):
                node.update_offsets()

            heard_by_any = False
            best_rssi = None
            # Propagation du paquet vers chaque passerelle
            best_snr = None
            for gw in self.gateways:
                distance = node.distance_to(gw)
                kwargs = {
                    "freq_offset_hz": getattr(node, "current_freq_offset", 0.0),
                    "sync_offset_s": getattr(node, "current_sync_offset", 0.0),
                    "tx_pos": (node.x, node.y, getattr(node, "altitude", 0.0)),
                    "rx_pos": (gw.x, gw.y, getattr(gw, "altitude", 0.0)),
                }
                if hasattr(node.channel, "_obstacle_loss"):
                    kwargs["tx_angle"] = getattr(node, "orientation_az", getattr(node, "direction", 0.0))
                    kwargs["rx_angle"] = getattr(gw, "orientation_az", getattr(gw, "direction", 0.0))
                else:
                    kwargs["tx_angle"] = (
                        getattr(node, "orientation_az", 0.0),
                        getattr(node, "orientation_el", 0.0),
                    )
                    kwargs["rx_angle"] = (
                        getattr(gw, "orientation_az", 0.0),
                        getattr(gw, "orientation_el", 0.0),
                    )
                rssi, snr = node.channel.compute_rssi(
                    tx_power,
                    distance,
                    sf,
                    **kwargs,
                )
                rssi += getattr(gw, "rx_gain_dB", 0.0)
                snr += getattr(gw, "rx_gain_dB", 0.0)
                if not self.pure_poisson_mode:
                    if rssi < node.channel.detection_threshold_dBm:
                        continue  # trop faible pour être détecté
                    snr_threshold = (
                        node.channel.sensitivity_dBm.get(sf, -float("inf"))
                        - node.channel.noise_floor_dBm()
                    )
                    if snr < snr_threshold:
                        continue  # signal trop faible pour être reçu
                heard_by_any = True
                if best_rssi is None or rssi > best_rssi:
                    best_rssi = rssi
                if best_snr is None or snr > best_snr:
                    best_snr = snr
                # Démarrer la réception à la passerelle (gestion des collisions et capture)
                gw.start_reception(
                    event_id,
                    node_id,
                    sf,
                    rssi,
                    end_time,
                    node.channel.capture_threshold_dB,
                    self.current_time,
                    node.channel.frequency_hz,
                    self.min_interference_time,
                    freq_offset=getattr(node, "current_freq_offset", 0.0),
                    sync_offset=getattr(node, "current_sync_offset", 0.0),
                    bandwidth=node.channel.bandwidth,
                    noise_floor=node.channel.noise_floor_dBm(),
                    capture_mode=(
                        "omnet"
                        if node.channel.phy_model == "omnet"
                        else (
                            "flora"
                            if node.channel.phy_model.startswith("flora")
                            else (
                                "advanced" if node.channel.advanced_capture else "basic"
                            )
                        )
                    ),
                    flora_phy=(
                        node.channel.flora_phy
                        if node.channel.phy_model.startswith("flora")
                        else None
                    ),
                    orthogonal_sf=node.channel.orthogonal_sf,
                    capture_window_symbols=node.channel.capture_window_symbols,
                )

            # Retenir le meilleur RSSI/SNR mesuré pour cette transmission
            node.last_rssi = best_rssi if heard_by_any else None
            node.last_snr = best_snr if heard_by_any else None
            # Planifier l'événement de fin de transmission correspondant
            heapq.heappush(
                self.event_queue,
                Event(end_time, EventType.TX_END, event_id, node.id),
            )
            # Planifier les fenêtres de réception LoRaWAN
            rx1, rx2 = node.schedule_receive_windows(end_time)
            ev1 = self.event_id_counter
            self.event_id_counter += 1
            heapq.heappush(
                self.event_queue,
                Event(rx1, EventType.RX_WINDOW, ev1, node.id),
            )
            ev2 = self.event_id_counter
            self.event_id_counter += 1
            heapq.heappush(
                self.event_queue,
                Event(rx2, EventType.RX_WINDOW, ev2, node.id),
            )

            # Journaliser l'événement de transmission (résultat inconnu à ce stade)
            self.events_log.append(
                {
                    "event_id": event_id,
                    "node_id": node_id,
                    "sf": sf,
                    "start_time": time,
                    "end_time": end_time,
                    "energy_J": energy_J,
                    "heard": heard_by_any,
                    "rssi_dBm": best_rssi,
                    "snr_dB": best_snr,
                    "result": None,
                    "gateway_id": None,
                }
            )
            return True

        elif priority == EventType.TX_END:
            # Fin d'une transmission – traitement de la réception/perte
            node_id = node.id
            # Marquer la fin de transmission du nœud
            if getattr(node.channel, "omnet_phy", None):
                node.channel.omnet_phy.stop_tx()
            node.in_transmission = False
            node.current_end_time = None
            node.state = "rx" if node.class_type.upper() == "C" else "processing"
            # Notifier chaque passerelle de la fin de réception
            for gw in self.gateways:
                gw.end_reception(event_id, self.network_server, node_id)
            # Vérifier si le paquet a été reçu par au moins une passerelle
            delivered = event_id in self.network_server.received_events
            if delivered:
                self.packets_delivered += 1
                self.rx_delivered += 1
                node.increment_success()
                # Délai = temps de fin - temps de début de l'émission
                start_time = next(
                    item for item in self.events_log if item["event_id"] == event_id
                )["start_time"]
                delay = self.current_time - start_time
                self.total_delay += delay
                self.delivered_count += 1
            else:
                # Identifier la cause de perte: collision ou absence de couverture
                log_entry = next(
                    item for item in self.events_log if item["event_id"] == event_id
                )
                heard = log_entry["heard"]
                if heard:
                    self.packets_lost_collision += 1
                    node.increment_collision()
                else:
                    self.packets_lost_no_signal += 1
            # Mettre à jour le résultat et la passerelle du log de l'événement
            for entry in self.events_log:
                if entry["event_id"] == event_id:
                    entry["result"] = (
                        "Success"
                        if delivered
                        else ("CollisionLoss" if entry["heard"] else "NoCoverage")
                    )
                    entry["gateway_id"] = (
                        self.network_server.event_gateway.get(event_id, None)
                        if delivered
                        else None
                    )
                    break

            if self.debug_rx:
                if delivered:
                    gw_id = self.network_server.event_gateway.get(event_id, None)
                    logger.debug(
                        f"t={self.current_time:.2f} Packet {event_id} from node {node_id} reçu via GW {gw_id}"
                    )
                else:
                    reason = "Collision" if log_entry["heard"] else "NoCoverage"
                    logger.debug(
                        f"t={self.current_time:.2f} Packet {event_id} from node {node_id} perdu ({reason})"
                    )

            # Mettre à jour l'historique du nœud pour calculer les statistiques
            # récentes et éventuellement déclencher l'ADR.
            snr_value = None
            rssi_value = None
            if delivered and node.last_snr is not None:
                snr_value = node.last_snr
            if delivered and node.last_rssi is not None:
                rssi_value = node.last_rssi
            node.history.append(
                {"snr": snr_value, "rssi": rssi_value, "delivered": delivered}
            )
            if len(node.history) > 20:
                node.history.pop(0)

            # Gestion Adaptive Data Rate (ADR)
            if self.adr_node:
                # Only track history here; the actual adaptation now relies on
                # the standard adr_ack_cnt mechanism implemented in :class:`Node`.
                pass
                
            # Planifier retransmissions restantes ou prochaine émission
            if node._nb_trans_left > 0:
                self.retransmissions += 1
                self.schedule_event(
                    node, self.current_time + 1.0, reason="retransmission"
                )
            else:
                if (
                    self.packets_to_send == 0
                    or node.packets_sent < self.packets_to_send
                ):
                    if self.transmission_mode.lower() == "random":
                        if not self.lock_step_poisson:
                            node.ensure_poisson_arrivals(
                                node.last_tx_time,
                                self.packet_interval,
                                self.interval_rng,
                                variation=self.interval_variation,
                                limit=(
                                    self.packets_to_send
                                    if self.packets_to_send
                                    else None
                                ),
                            )
                        next_time = node.arrival_queue.pop(0)
                    else:
                        next_time = node._last_arrival_time + self.packet_interval
                        node.arrival_interval_sum += self.packet_interval
                        node.arrival_interval_count += 1
                        node._last_arrival_time = next_time
                    self.schedule_event(
                        node,
                        next_time if self.pure_poisson_mode else max(next_time, self.current_time),
                        reason=(
                            "poisson"
                            if self.transmission_mode.lower() == "random"
                            else "periodic"
                        ),
                    )
                else:
                    logger.debug(
                        "Packet limit reached for node %s – no more events for this node.",
                        node.id,
                    )

                if self.packets_to_send != 0 and all(
                    n.packets_sent >= self.packets_to_send for n in self.nodes
                ):
                    new_queue = []
                    for evt in self.event_queue:
                        if evt.type in (EventType.TX_END, EventType.RX_WINDOW):
                            new_queue.append(evt)
                    heapq.heapify(new_queue)
                    self.event_queue = new_queue
                    # Stop scheduling further mobility events once every node
                    # reached the packet limit to ensure the simulation
                    # completes when using fast forward.
                    self.mobility_enabled = False
                    logger.debug(
                        "Packet limit reached – no more new events will be scheduled."
                    )

            return True

        elif priority == EventType.RX_WINDOW:
            # Fenêtre de réception RX1/RX2 pour un nœud
            if node.class_type.upper() != "C":
                current = (
                    node.profile.listen_current_a
                    if node.profile.listen_current_a > 0.0
                    else node.profile.rx_current_a
                )
                state = "listen" if node.profile.listen_current_a > 0.0 else "rx"
                node.add_energy(
                    current
                    * node.profile.voltage_v
                    * node.profile.rx_window_duration,
                    state,
                )
            if not node.alive:
                return True
            node.last_state_time = time + (
                node.profile.rx_window_duration
                if node.class_type.upper() != "C"
                else 0.0
            )
            if node.class_type.upper() != "C":
                node.state = "sleep"
            self.network_server.deliver_scheduled(node.id, time)
            for gw in self.gateways:
                frame = gw.pop_downlink(node.id)
                if not frame:
                    continue
                distance = node.distance_to(gw)
                kwargs = {
                    "freq_offset_hz": 0.0,
                    "sync_offset_s": 0.0,
                    "tx_pos": (gw.x, gw.y, getattr(gw, "altitude", 0.0)),
                    "rx_pos": (node.x, node.y, getattr(node, "altitude", 0.0)),
                }
                if hasattr(node.channel, "_obstacle_loss"):
                    kwargs["tx_angle"] = getattr(gw, "orientation_az", getattr(gw, "direction", 0.0))
                    kwargs["rx_angle"] = getattr(node, "orientation_az", getattr(node, "direction", 0.0))
                else:
                    kwargs["tx_angle"] = (
                        getattr(gw, "orientation_az", 0.0),
                        getattr(gw, "orientation_el", 0.0),
                    )
                    kwargs["rx_angle"] = (
                        getattr(node, "orientation_az", 0.0),
                        getattr(node, "orientation_el", 0.0),
                    )
                rssi, snr = node.channel.compute_rssi(
                    node.tx_power,
                    distance,
                    node.sf,
                    **kwargs,
                )
                if not self.pure_poisson_mode:
                    if rssi < node.channel.detection_threshold_dBm:
                        node.downlink_pending = max(0, node.downlink_pending - 1)
                        continue
                    snr_threshold = (
                        node.channel.sensitivity_dBm.get(node.sf, -float("inf"))
                        - node.channel.noise_floor_dBm()
                    )
                    if snr >= snr_threshold:
                        node.handle_downlink(frame)
                    else:
                        node.downlink_pending = max(0, node.downlink_pending - 1)
                else:
                    node.handle_downlink(frame)
                break
            # Replanifier selon la classe du nœud
            if node.class_type.upper() == "C":
                if not (
                    self.packets_to_send != 0
                    and all(n.packets_sent >= self.packets_to_send for n in self.nodes)
                ):
                    nxt = time + self.class_c_rx_interval
                    eid = self.event_id_counter
                    self.event_id_counter += 1
                    heapq.heappush(
                        self.event_queue,
                        Event(nxt, EventType.RX_WINDOW, eid, node.id),
                    )
            return True

        elif priority == EventType.BEACON:
            nxt = self.network_server.next_beacon_time(time)
            eid = self.event_id_counter
            self.event_id_counter += 1
            heapq.heappush(
                self.event_queue,
                Event(nxt, EventType.BEACON, eid, 0),
            )
            self.last_beacon_time = time
            self.network_server.notify_beacon(time)
            end_of_cycle = nxt
            for n in self.nodes:
                if n.class_type.upper() == "B":
                    received = random.random() >= getattr(n, "beacon_loss_prob", 0.0)
                    if received:
                        n.last_beacon_time = time
                        n.clock_offset = 0.0
                    else:
                        n.miss_beacon(self.beacon_interval)
                    periodicity = 2 ** (getattr(n, "ping_slot_periodicity", 0) or 0)
                    interval = self.ping_slot_interval * periodicity
                    slot = n.next_ping_slot_time(
                        time,
                        self.beacon_interval,
                        self.ping_slot_interval,
                        self.ping_slot_offset,
                    )
                    while slot < end_of_cycle:
                        eid = self.event_id_counter
                        self.event_id_counter += 1
                        heapq.heappush(
                            self.event_queue,
                            Event(slot, EventType.PING_SLOT, eid, n.id),
                        )
                        slot += interval
            return True

        elif priority == EventType.PING_SLOT:
            if node.class_type.upper() != "B":
                return True
            current = (
                node.profile.listen_current_a
                if node.profile.listen_current_a > 0.0
                else node.profile.rx_current_a
            )
            state = "listen" if node.profile.listen_current_a > 0.0 else "rx"
            node.add_energy(
                current
                * node.profile.voltage_v
                * node.profile.rx_window_duration,
                state,
            )
            if not node.alive:
                return True
            node.last_state_time = time + node.profile.rx_window_duration
            node.state = "sleep"
            self.network_server.deliver_scheduled(node.id, time)
            for gw in self.gateways:
                frame = gw.pop_downlink(node.id)
                if not frame:
                    continue
                distance = node.distance_to(gw)
                sf = node.sf
                if node.ping_slot_dr is not None:
                    from .lorawan import DR_TO_SF

                    sf = DR_TO_SF.get(node.ping_slot_dr, node.sf)
                kwargs = {"freq_offset_hz": 0.0, "sync_offset_s": 0.0}
                if hasattr(node.channel, "_obstacle_loss"):
                    kwargs["tx_pos"] = (gw.x, gw.y, getattr(gw, "altitude", 0.0))
                    kwargs["rx_pos"] = (node.x, node.y, getattr(node, "altitude", 0.0))
                rssi, snr = node.channel.compute_rssi(
                    node.tx_power,
                    distance,
                    sf,
                    **kwargs,
                )
                if not self.pure_poisson_mode:
                    if rssi < node.channel.detection_threshold_dBm:
                        node.downlink_pending = max(0, node.downlink_pending - 1)
                        continue
                    snr_threshold = (
                        node.channel.sensitivity_dBm.get(sf, -float("inf"))
                        - node.channel.noise_floor_dBm()
                    )
                    if snr >= snr_threshold:
                        node.handle_downlink(frame)
                    else:
                        node.downlink_pending = max(0, node.downlink_pending - 1)
                else:
                    node.handle_downlink(frame)
                break
            return True

        elif priority == EventType.SERVER_RX:
            self.network_server._handle_network_arrival(event_id)
            return True

        elif priority == EventType.SERVER_PROCESS:
            self.network_server._process_scheduled(event_id)
            return True

        elif priority == EventType.MOBILITY:
            # Événement de mobilité (changement de position du nœud)
            if not self.mobility_enabled:
                return True
            node_id = node.id
            if node.in_transmission:
                # Si le nœud est en cours de transmission, reporter le déplacement à la fin de celle-ci
                next_move_time = (
                    node.current_end_time
                    if node.current_end_time is not None
                    else self.current_time
                )
                self.schedule_mobility(node, next_move_time)
            else:
                # Déplacer le nœud de manière progressive
                self.mobility_model.move(node, self.current_time)
                self.events_log.append(
                    {
                        "event_id": event_id,
                        "node_id": node_id,
                        "sf": node.sf,
                        "start_time": time,
                        "end_time": time,
                        "heard": None,
                        "result": "Mobility",
                        "energy_J": 0.0,
                        "gateway_id": None,
                        "rssi_dBm": None,
                        "snr_dB": None,
                    }
                )
                if self.mobility_enabled and (
                    self.packets_to_send == 0
                    or node.packets_sent < self.packets_to_send
                ):
                    self.schedule_mobility(node, time + self.mobility_model.step)
            return True

        # Si autre type d'événement (non prévu)
        return True

    def run(self, max_steps: int | None = None):
        """Exécute la simulation en traitant les événements jusqu'à épuisement ou jusqu'à une limite optionnelle."""
        step_count = 0
        while self.event_queue and self.running:
            self.step()
            step_count += 1
            if max_steps and step_count >= max_steps:
                break
        if self.dump_intervals:
            self.dump_interval_logs()

    def stop(self):
        """Arrête la simulation en cours."""
        self.running = False

    def get_metrics(self) -> dict:
        """Retourne un dictionnaire des métriques actuelles de la simulation."""
        total_sent = self.tx_attempted
        delivered = self.rx_delivered
        pdr = delivered / total_sent if total_sent > 0 else 0.0
        avg_delay = (
            self.total_delay / self.delivered_count if self.delivered_count > 0 else 0.0
        )
        sim_time = self.current_time
        throughput_bps = (
            self.packets_delivered * self.payload_size_bytes * 8 / sim_time
            if sim_time > 0
            else 0.0
        )
        pdr_by_node = {node.id: node.pdr for node in self.nodes}
        recent_pdr_by_node = {node.id: node.recent_pdr for node in self.nodes}
        pdr_by_sf: dict[int, float] = {}
        for sf in range(7, 13):
            nodes_sf = [n for n in self.nodes if n.sf == sf]
            sent_sf = sum(n.tx_attempted for n in nodes_sf)
            delivered_sf = sum(n.rx_delivered for n in nodes_sf)
            pdr_by_sf[sf] = delivered_sf / sent_sf if sent_sf > 0 else 0.0

        gateway_counts = {gw.id: 0 for gw in self.gateways}
        for gw_id in self.network_server.event_gateway.values():
            if gw_id in gateway_counts:
                gateway_counts[gw_id] += 1
        pdr_by_gateway = {
            gw_id: count / total_sent if total_sent > 0 else 0.0
            for gw_id, count in gateway_counts.items()
        }

        pdr_by_class: dict[str, float] = {}
        class_types = {n.class_type for n in self.nodes}
        for ct in class_types:
            nodes_cls = [n for n in self.nodes if n.class_type == ct]
            sent_cls = sum(n.tx_attempted for n in nodes_cls)
            delivered_cls = sum(n.rx_delivered for n in nodes_cls)
            pdr_by_class[ct] = delivered_cls / sent_cls if sent_cls > 0 else 0.0

        energy_by_class = {
            ct: sum(n.energy_consumed for n in self.nodes if n.class_type == ct)
            for ct in class_types
        }

        energy_by_node = {n.id: n.energy_consumed for n in self.nodes}
        airtime_by_node = {n.id: n.total_airtime for n in self.nodes}

        interval_sum = 0.0
        interval_count = 0
        for n in self.nodes:
            times = sorted(entry["tx_time"] for entry in n.interval_log)
            if self.warm_up_intervals:
                times = times[self.warm_up_intervals :]
            if len(times) > 1:
                for t0, t1 in zip(times, times[1:]):
                    interval_sum += t1 - t0
                    interval_count += 1
            else:
                interval_sum += n.arrival_interval_sum
                interval_count += n.arrival_interval_count

        avg_arrival_interval = (
            interval_sum / interval_count if interval_count > 0 else 0.0
        )

        tx_power_distribution: dict[float, int] = {}
        for node in self.nodes:
            p = node.tx_power
            tx_power_distribution[p] = tx_power_distribution.get(p, 0) + 1

        return {
            "PDR": pdr,
            "collisions": self.packets_lost_collision,
            "duplicates": self.network_server.duplicate_packets,
            "energy_J": self.total_energy_J,
            "avg_delay_s": avg_delay,
            "avg_arrival_interval_s": avg_arrival_interval,
            "throughput_bps": throughput_bps,
            "sf_distribution": {
                sf: sum(1 for node in self.nodes if node.sf == sf)
                for sf in range(7, 13)
            },
            "tx_power_distribution": tx_power_distribution,
            "pdr_by_node": pdr_by_node,
            "recent_pdr_by_node": recent_pdr_by_node,
            "pdr_by_sf": pdr_by_sf,
            "pdr_by_gateway": pdr_by_gateway,
            "pdr_by_class": pdr_by_class,
            "energy_by_node": energy_by_node,
            "airtime_by_node": airtime_by_node,
            **{f"energy_class_{ct}_J": energy_by_class[ct] for ct in energy_by_class},
            "retransmissions": self.retransmissions,
        }

    def get_events_dataframe(self) -> "pd.DataFrame | None":
        """
        Retourne un DataFrame pandas contenant le log de tous les événements de
        transmission enrichi des états initiaux et finaux des nœuds.
        """
        if pd is None:
            raise RuntimeError("pandas is required for this feature")
        if not self.events_log:
            return pd.DataFrame()
        df = pd.DataFrame(self.events_log)
        # Construire un dictionnaire id->nœud pour récupérer les états initiaux/finaux
        node_dict = {node.id: node for node in self.nodes}
        # Ajouter colonnes d'état initial et final du nœud pour chaque événement
        df["initial_x"] = df["node_id"].apply(lambda nid: node_dict[nid].initial_x)
        df["initial_y"] = df["node_id"].apply(lambda nid: node_dict[nid].initial_y)
        df["final_x"] = df["node_id"].apply(lambda nid: node_dict[nid].x)
        df["final_y"] = df["node_id"].apply(lambda nid: node_dict[nid].y)
        df["initial_sf"] = df["node_id"].apply(lambda nid: node_dict[nid].initial_sf)
        df["final_sf"] = df["node_id"].apply(lambda nid: node_dict[nid].sf)
        df["initial_tx_power"] = df["node_id"].apply(
            lambda nid: node_dict[nid].initial_tx_power
        )
        df["final_tx_power"] = df["node_id"].apply(lambda nid: node_dict[nid].tx_power)
        df["packets_sent"] = df["node_id"].apply(
            lambda nid: node_dict[nid].packets_sent
        )
        df["packets_success"] = df["node_id"].apply(
            lambda nid: node_dict[nid].packets_success
        )
        df["packets_collision"] = df["node_id"].apply(
            lambda nid: node_dict[nid].packets_collision
        )
        df["tx_attempted"] = df["node_id"].apply(
            lambda nid: node_dict[nid].tx_attempted
        )
        df["rx_delivered"] = df["node_id"].apply(
            lambda nid: node_dict[nid].rx_delivered
        )
        df["energy_consumed_J_node"] = df["node_id"].apply(
            lambda nid: node_dict[nid].energy_consumed
        )
        df["battery_capacity_J"] = df["node_id"].apply(
            lambda nid: node_dict[nid].battery_capacity_j
        )
        df["battery_remaining_J"] = df["node_id"].apply(
            lambda nid: node_dict[nid].battery_remaining_j
        )
        df["downlink_pending"] = df["node_id"].apply(
            lambda nid: node_dict[nid].downlink_pending
        )
        df["acks_received"] = df["node_id"].apply(
            lambda nid: node_dict[nid].acks_received
        )
        # Colonnes d'intérêt dans un ordre lisible
        columns_order = [
            "event_id",
            "node_id",
            "initial_x",
            "initial_y",
            "final_x",
            "final_y",
            "initial_sf",
            "final_sf",
            "initial_tx_power",
            "final_tx_power",
            "packets_sent",
            "packets_success",
            "packets_collision",
            "tx_attempted",
            "rx_delivered",
            "energy_consumed_J_node",
            "battery_capacity_J",
            "battery_remaining_J",
            "downlink_pending",
            "acks_received",
            "start_time",
            "end_time",
            "energy_J",
            "rssi_dBm",
            "snr_dB",
            "result",
            "gateway_id",
        ]
        for col in columns_order:
            if col not in df.columns:
                df[col] = None
        return df[columns_order]

    def dump_interval_logs(self, dest: str | Path = ".") -> None:
        """Écrit les intervalles théoriques et réels de chaque nœud en Parquet."""
        if not self.dump_intervals:
            return
        if pd is None:
            raise RuntimeError("pandas is required for this feature")
        dest_path = Path(dest)
        dest_path.mkdir(parents=True, exist_ok=True)
        for node in self.nodes:
            if not node.interval_log:
                continue
            df = pd.DataFrame(node.interval_log)
            df.to_parquet(dest_path / f"intervals_node_{node.id}.parquet", index=False)
