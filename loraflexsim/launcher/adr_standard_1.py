from __future__ import annotations

from .simulator import Simulator
from . import server
from .lorawan import TX_POWER_INDEX_TO_DBM
from .channel import Channel
from .gateway import FLORA_NON_ORTH_DELTA

def apply(
    sim: Simulator,
    *,
    degrade_channel: bool = False,
    profile: str = "flora",
    capture_mode: str = "flora",
) -> None:
    """Configure ADR variant ``adr_standard_1`` (LoRaWAN defaults).

    Parameters
    ----------
    sim : Simulator
        Instance to modify in-place.
    degrade_channel : bool, optional
        Paramètre conservé pour compatibilité. Depuis la version 1.1, il est
        ignoré et n'altère plus les canaux radio existants.
    profile : str, optional
        Conservé pour compatibilité. Aucun effet depuis la version 1.1.
    capture_mode : str, optional
        Conservé pour compatibilité. Aucun effet depuis la version 1.1.
    """
    # Marge ADR
    Simulator.MARGIN_DB = 15.0
    server.MARGIN_DB = Simulator.MARGIN_DB
    sim.adr_node = True
    sim.adr_server = True
    # Utilise la moyenne de SNR sur 20 paquets comme dans FLoRa
    sim.adr_method = "avg"
    sim.network_server.adr_enabled = True
    sim.network_server.adr_method = "avg"
    for node in sim.nodes:
        # Démarre au SF12 pour une sensibilité maximale sauf si un SF fixe est
        # déjà défini par le simulateur LoRaFlexSim
        if getattr(sim, "fixed_sf", None) is None:
            node.sf = 12
            node.initial_sf = 12
        else:
            node.initial_sf = node.sf
        # Démarre avec la puissance TX maximale (14 dBm, index 0)
        max_tx_power = TX_POWER_INDEX_TO_DBM[0]
        node.tx_power = max_tx_power
        node.initial_tx_power = max_tx_power
        # Compteurs ADR
        node.adr_ack_cnt = 0
        node.adr_ack_limit = 64
        node.adr_ack_delay = 32

    # Autorise l'interférence inter-SF comme dans FLoRa
    for ch in sim.multichannel.channels:
        ch.orthogonal_sf = False
        ch.non_orth_delta = FLORA_NON_ORTH_DELTA

    # Propager le comportement non orthogonal aux canaux des nœuds
    for node in sim.nodes:
        node.channel.orthogonal_sf = False
        node.channel.non_orth_delta = FLORA_NON_ORTH_DELTA

    # Pour les scénarios à SF fixe conserver un seuil très permissif pour
    # coller au comportement historique
    if getattr(sim, "fixed_sf", None) is not None:
        for ch in sim.multichannel.channels:
            ch.detection_threshold_dBm = -float("inf")

    # S'assurer que le serveur et le canal principal reflètent les réglages
    sim.channel = sim.multichannel.channels[0]
    sim.channel.orthogonal_sf = False
    sim.channel.non_orth_delta = FLORA_NON_ORTH_DELTA
    sim.network_server.channel = sim.channel
