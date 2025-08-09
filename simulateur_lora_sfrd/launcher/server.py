from __future__ import annotations

import logging
import heapq

from typing import TYPE_CHECKING
from .downlink_scheduler import DownlinkScheduler
from .join_server import JoinServer  # re-export

__all__ = ["NetworkServer", "JoinServer"]

if TYPE_CHECKING:  # pragma: no cover - for type checking only
    from .lorawan import LoRaWANFrame, JoinAccept

logger = logging.getLogger(__name__)

# Paramètres ADR (valeurs issues de la spécification LoRaWAN)
REQUIRED_SNR = {7: -7.5, 8: -10.0, 9: -12.5, 10: -15.0, 11: -17.5, 12: -20.0}
MARGIN_DB = 15.0


class NetworkServer:
    """Représente le serveur de réseau LoRa (collecte des paquets reçus)."""

    def __init__(
        self,
        join_server=None,
        *,
        simulator=None,
        process_delay: float = 0.0,
        network_delay: float = 0.0,
        adr_method: str = "max",
    ):
        """Initialise le serveur réseau.

        :param join_server: Instance facultative de serveur d'activation OTAA.
        :param simulator: Référence au :class:`Simulator` pour planifier
            éventuellement certains événements (classe C).
        :param process_delay: Délai de traitement du serveur (s).
        :param network_delay: Délai de propagation des messages (s).
        :param adr_method: Méthode d'agrégation du SNR pour l'ADR
            (``"max"`` ou ``"avg"``).
        """
        # Ensemble des identifiants d'événements déjà reçus (pour éviter les doublons)
        self.received_events = set()
        # Stockage optionnel d'infos sur les réceptions (par ex : via quelle passerelle)
        self.event_gateway = {}
        # Compteur de paquets reçus
        self.packets_received = 0
        # Nombre de doublons ignorés
        self.duplicate_packets = 0
        # Indicateur ADR serveur
        self.adr_enabled = False
        # Références pour ADR serveur
        self.nodes = []
        self.gateways = []
        self.channel = None
        self.net_id = 0
        self.next_devaddr = 1
        self.scheduler = DownlinkScheduler(link_delay=network_delay)
        self.join_server = join_server
        self.simulator = simulator
        self.process_delay = process_delay
        self.network_delay = network_delay
        self.adr_method = adr_method
        self.pending_process: dict[int, tuple[int, int, int, float | None, object]] = {}
        self.beacon_interval = 128.0
        self.beacon_drift = 0.0
        self.ping_slot_interval = 1.0
        self.ping_slot_offset = 2.0
        self.last_beacon_time: float | None = None

    def next_beacon_time(self, after_time: float) -> float:
        """Return the next beacon time after ``after_time``."""
        from .lorawan import next_beacon_time

        return next_beacon_time(
            after_time,
            self.beacon_interval,
            last_beacon=self.last_beacon_time,
            drift=self.beacon_drift,
        )

    def notify_beacon(self, time: float) -> None:
        """Record that a beacon was emitted at ``time``."""
        self.last_beacon_time = time

    # ------------------------------------------------------------------
    # Downlink management
    # ------------------------------------------------------------------
    def send_downlink(
        self,
        node,
        payload: bytes | LoRaWANFrame | JoinAccept = b"",
        confirmed: bool = False,
        adr_command: tuple | None = None,
        request_ack: bool = False,
        at_time: float | None = None,
        gateway=None,
    ):
        """Queue a downlink frame for a node via ``gateway`` or the first one."""
        from .lorawan import (
            LoRaWANFrame,
            LinkADRReq,
            SF_TO_DR,
            DBM_TO_TX_POWER_INDEX,
            JoinAccept,
        )

        gw = gateway or (self.gateways[0] if self.gateways else None)
        if gw is None:
            return
        fctrl = 0x20 if request_ack else 0
        frame: LoRaWANFrame | JoinAccept
        if isinstance(payload, JoinAccept):
            frame = payload
        elif isinstance(payload, LoRaWANFrame):
            frame = payload
        else:
            raw = payload.to_bytes() if hasattr(payload, "to_bytes") else bytes(payload)
            frame = LoRaWANFrame(
                mhdr=0x60,
                fctrl=fctrl,
                fcnt=node.fcnt_down,
                payload=raw,
                confirmed=confirmed,
            )
        priority = -1 if confirmed or adr_command or request_ack or isinstance(frame, JoinAccept) else 0
        if adr_command and isinstance(frame, LoRaWANFrame):
            if len(adr_command) == 2:
                sf, power = adr_command
                chmask = node.chmask
                nbtrans = node.nb_trans
            else:
                sf, power, chmask, nbtrans = adr_command
            dr = SF_TO_DR.get(sf, 5)
            p_idx = DBM_TO_TX_POWER_INDEX.get(int(power), 0)
            frame.payload = LinkADRReq(dr, p_idx, chmask, nbtrans).to_bytes()
        if node.security_enabled and isinstance(frame, LoRaWANFrame):
            from .lorawan import encrypt_payload, compute_mic

            enc = encrypt_payload(
                node.appskey, node.devaddr, node.fcnt_down, 1, frame.payload
            )
            frame.encrypted_payload = enc
            frame.mic = compute_mic(node.nwkskey, node.devaddr, node.fcnt_down, 1, enc)
        node.fcnt_down += 1
        if at_time is None:
            if node.class_type.upper() == "B":
                after = self.simulator.current_time if self.simulator else 0.0
                self.scheduler.schedule_class_b(
                    node,
                    after,
                    frame,
                    gw,
                    self.beacon_interval,
                    self.ping_slot_interval,
                    self.ping_slot_offset,
                    last_beacon_time=getattr(node, "last_beacon_time", None),
                    priority=priority,
                )
            elif node.class_type.upper() == "C":
                after = self.simulator.current_time if self.simulator else 0.0
                self.scheduler.schedule_class_c(node, after, frame, gw, priority=priority)
            else:
                end = getattr(node, "last_uplink_end_time", None)
                if end is not None:
                    from .lorawan import compute_rx1, compute_rx2

                    after = self.simulator.current_time if self.simulator else 0.0
                    rx1 = compute_rx1(end, node.rx_delay)
                    rx2 = compute_rx2(end, node.rx_delay)
                    self.scheduler.schedule_class_a(
                        node,
                        after,
                        rx1,
                        rx2,
                        frame,
                        gw,
                        priority=priority,
                    )
                else:
                    gw.buffer_downlink(node.id, frame)
        else:
            if node.class_type.upper() == "B":
                self.scheduler.schedule_class_b(
                    node,
                    at_time,
                    frame,
                    gw,
                    self.beacon_interval,
                    self.ping_slot_interval,
                    self.ping_slot_offset,
                    last_beacon_time=getattr(node, "last_beacon_time", None),
                    priority=priority,
                )
            elif node.class_type.upper() == "C":
                self.scheduler.schedule_class_c(node, at_time, frame, gw, priority=priority)
                if self.simulator is not None:
                    from .simulator import Event, EventType

                    eid = self.simulator.event_id_counter
                    self.simulator.event_id_counter += 1
                    heapq.heappush(
                        self.simulator.event_queue,
                        Event(at_time, EventType.RX_WINDOW, eid, node.id),
                    )
            else:
                self.scheduler.schedule(node.id, at_time, frame, gw, priority=priority)
        try:
            node.downlink_pending += 1
        except AttributeError:
            pass

    def _derive_keys(
        self, appkey: bytes, devnonce: int, appnonce: int
    ) -> tuple[bytes, bytes]:
        from .lorawan import derive_session_keys

        return derive_session_keys(appkey, devnonce, appnonce, self.net_id)

    # ------------------------------------------------------------------
    # Event scheduling helpers
    # ------------------------------------------------------------------
    def schedule_receive(
        self,
        event_id: int,
        node_id: int,
        gateway_id: int,
        rssi: float | None = None,
        frame=None,
        at_time: float | None = None,
    ) -> None:
        """Planifie le traitement serveur d'une trame."""
        if self.simulator is None:
            self.receive(event_id, node_id, gateway_id, rssi, frame, end_time=at_time)
            return

        from .simulator import Event, EventType

        arrival_time = (
            (at_time if at_time is not None else self.simulator.current_time)
            + self.network_delay
        )

        if arrival_time <= self.simulator.current_time and self.process_delay <= 0:
            self.receive(event_id, node_id, gateway_id, rssi, frame)
            return

        eid = self.simulator.event_id_counter
        self.simulator.event_id_counter += 1
        self.pending_process[eid] = (
            event_id,
            node_id,
            gateway_id,
            rssi,
            frame,
            at_time,
        )
        heapq.heappush(
            self.simulator.event_queue,
            Event(arrival_time, EventType.SERVER_RX, eid, node_id),
        )

    def _handle_network_arrival(self, eid: int) -> None:
        """Planifie le traitement d'un paquet arrivé au serveur."""
        info = self.pending_process.pop(eid, None)
        if not info:
            return
        from .simulator import Event, EventType

        process_time = self.simulator.current_time + self.process_delay
        new_id = self.simulator.event_id_counter
        self.simulator.event_id_counter += 1
        self.pending_process[new_id] = info
        node_id = info[1]
        heapq.heappush(
            self.simulator.event_queue,
            Event(process_time, EventType.SERVER_PROCESS, new_id, node_id),
        )

    def _process_scheduled(self, eid: int) -> None:
        """Exécute le traitement différé d'un paquet."""
        info = self.pending_process.pop(eid, None)
        if not info:
            return
        event_id, node_id, gateway_id, rssi, frame, end_time = info
        self.receive(event_id, node_id, gateway_id, rssi, frame, end_time=end_time)

    def deliver_scheduled(self, node_id: int, current_time: float) -> None:
        """Move ready scheduled frames to the gateway buffer."""
        tolerance = 0.1
        nxt = self.scheduler.next_time(node_id)
        if nxt is not None and nxt < current_time - tolerance:
            frame, gw = self.scheduler.pop_ready(node_id, nxt)
            if frame and gw:
                gw.buffer_downlink(node_id, frame)
        frame, gw = self.scheduler.pop_ready(node_id, current_time)
        while frame and gw:
            gw.buffer_downlink(node_id, frame)
            frame, gw = self.scheduler.pop_ready(node_id, current_time)

    def _activate(self, node, gateway=None):
        from .lorawan import JoinAccept, encrypt_join_accept

        appnonce = self.next_devaddr & 0xFFFFFF
        devaddr = self.next_devaddr
        self.next_devaddr += 1
        devnonce = (node.devnonce - 1) & 0xFFFF
        nwk_skey, app_skey = self._derive_keys(node.appkey, devnonce, appnonce)
        # Store derived keys server-side but send only join parameters
        frame = JoinAccept(appnonce, self.net_id, devaddr)
        if node.security_enabled:
            enc, mic = encrypt_join_accept(node.appkey, frame)
            frame.encrypted = enc
            frame.mic = mic
        node.nwkskey = nwk_skey
        node.appskey = app_skey
        self.send_downlink(node, frame, gateway=gateway)

    def receive(
        self,
        event_id: int,
        node_id: int,
        gateway_id: int,
        rssi: float | None = None,
        frame=None,
        end_time: float | None = None,
    ):
        """
        Traite la réception d'un paquet par le serveur.
        Évite de compter deux fois le même paquet s'il arrive via plusieurs passerelles.
        :param event_id: Identifiant unique de l'événement de transmission du paquet.
        :param node_id: Identifiant du nœud source.
        :param gateway_id: Identifiant de la passerelle ayant reçu le paquet.
        :param rssi: RSSI mesuré par la passerelle pour ce paquet (optionnel).
        :param frame: Trame LoRaWAN associée pour vérification de sécurité
            (optionnelle).
        """
        if event_id in self.received_events:
            # Doublon (déjà reçu via une autre passerelle)
            logger.debug(
                f"NetworkServer: duplicate packet event {event_id} from node {node_id} (ignored)."
            )
            self.duplicate_packets += 1
            return
        # Nouveau paquet reçu
        self.received_events.add(event_id)
        self.event_gateway[event_id] = gateway_id
        self.packets_received += 1
        logger.debug(
            f"NetworkServer: packet event {event_id} from node {node_id} received via gateway {gateway_id}."
        )

        node = next((n for n in self.nodes if n.id == node_id), None)
        gw = next((g for g in self.gateways if g.id == gateway_id), None)
        if node is not None:
            node.last_uplink_end_time = end_time
        from .lorawan import JoinRequest

        if node and isinstance(frame, JoinRequest) and self.join_server:
            try:
                accept, nwk_skey, app_skey = self.join_server.handle_join(frame)
            except Exception:
                return
            node.nwkskey = nwk_skey
            node.appskey = app_skey
            node.devaddr = accept.dev_addr
            node.activated = True
            self.send_downlink(node, accept, gateway=gw)
            return

        if node and frame is not None and node.security_enabled:
            from .lorawan import validate_frame, LoRaWANFrame

            if isinstance(frame, LoRaWANFrame) and not validate_frame(
                frame,
                node.nwkskey,
                node.appskey,
                node.devaddr,
                0,
            ):
                return

        if node and not getattr(node, "activated", True):
            self._activate(node, gateway=gw)

        if node and node.last_adr_ack_req:
            # Device requested an ADR acknowledgement -> reply with current parameters
            self.send_downlink(node, adr_command=(node.sf, node.tx_power))
            node.last_adr_ack_req = False

        # Appliquer ADR complet au niveau serveur
        if self.adr_enabled and rssi is not None:
            from .lorawan import DBM_TO_TX_POWER_INDEX, TX_POWER_INDEX_TO_DBM

            node = next((n for n in self.nodes if n.id == node_id), None)
            if node:
                snr = rssi - self.channel.noise_floor_dBm()
                node.snr_history.append(snr)
                if len(node.snr_history) > 20:
                    node.snr_history.pop(0)
                if len(node.snr_history) >= 20:
                    if self.adr_method == "avg":
                        snr_m = sum(node.snr_history) / len(node.snr_history)
                    else:
                        snr_m = max(node.snr_history)
                    required = REQUIRED_SNR.get(node.sf, -20.0)
                    margin = snr_m - required - MARGIN_DB
                    nstep = round(margin / 3.0)

                    sf = node.sf
                    p_idx = DBM_TO_TX_POWER_INDEX.get(int(node.tx_power), 0)
                    max_power_index = max(TX_POWER_INDEX_TO_DBM.keys())

                    if nstep > 0:
                        while nstep > 0 and sf > 7:
                            sf -= 1
                            nstep -= 1
                        while nstep > 0 and p_idx < max_power_index:
                            p_idx += 1
                            nstep -= 1
                    elif nstep < 0:
                        while nstep < 0 and p_idx > 0:
                            p_idx -= 1
                            nstep += 1
                        while nstep < 0 and sf < 12:
                            sf += 1
                            nstep += 1

                    power = TX_POWER_INDEX_TO_DBM.get(p_idx, node.tx_power)

                    if sf != node.sf or power != node.tx_power:
                        node.sf = sf
                        node.tx_power = power
                        self.send_downlink(
                            node, adr_command=(sf, power, node.chmask, node.nb_trans)
                        )
                        node.snr_history.clear()
