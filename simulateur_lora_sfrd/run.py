import argparse
import configparser
import csv

from traffic.exponential import sample_interval
from traffic.rng_manager import RngManager
import logging
import sys
from pathlib import Path

PAYLOAD_SIZE = 20  # octets simulés par paquet

# Configuration du logger pour afficher les informations
logging.basicConfig(level=logging.INFO, format="%(message)s")

# Logger dédié aux diagnostics (collisions, etc.)
diag_logger = logging.getLogger("diagnostics")
if not diag_logger.handlers:
    handler = logging.FileHandler("diagnostics.log", mode="w")
    handler.setFormatter(logging.Formatter("%(message)s"))
    diag_logger.addHandler(handler)
diag_logger.setLevel(logging.INFO)


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
):
    """Exécute une simulation LoRa simplifiée et retourne les métriques.

    Les transmissions peuvent se faire sur plusieurs canaux et plusieurs
    passerelles. Les nœuds sont répartis de façon uniforme sur les ``channels``
    et sur les ``gateways`` disponibles et les collisions ne surviennent
    qu'entre nœuds partageant à la fois le même canal **et** la même passerelle.
    """
    if nodes < 1:
        raise ValueError("nodes must be >= 1")
    if gateways < 1:
        raise ValueError("gateways must be >= 1")
    if channels < 1:
        raise ValueError("channels must be >= 1")
    if not isinstance(interval, float) or interval <= 0:
        raise ValueError("mean_interval must be positive float")
    if first_interval is not None and (
        not isinstance(first_interval, float) or first_interval <= 0
    ):
        raise ValueError("first_interval must be positive float")
    if steps <= 0:
        raise ValueError("steps must be > 0")

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
    airtime = channel.airtime(7, payload_size=PAYLOAD_SIZE)
    tx_energy = (tx_current - idle_current) * voltage * airtime
    rx_energy = (rx_current - idle_current) * voltage * airtime
    # Liste des délais de livraison (0 pour chaque paquet car la transmission
    # réussie est immédiate dans ce modèle simplifié)
    delays = []

    # Génération des instants d'émission pour chaque nœud et attribution d'un canal
    send_times = {node: [] for node in range(nodes)}
    node_channels = {node: node % channels for node in range(nodes)}
    node_gateways = {node: node % max(1, gateways) for node in range(nodes)}
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


    # Simulation pas à pas
    events: dict[float, list[int]] = {}
    for node, times in send_times.items():
        for t in times:
            events.setdefault(t, []).append(node)

    for t in sorted(events.keys()):
        nodes_ready = events[t]
        for gw in range(max(1, gateways)):
            gw_nodes = [n for n in nodes_ready if node_gateways[n] == gw]
            for ch in range(channels):
                nodes_on_ch = [n for n in gw_nodes if node_channels[n] == ch]
                nb_tx = len(nodes_on_ch)
                if nb_tx == 0:
                    continue
                total_transmissions += nb_tx
                energy_consumed += nb_tx * (tx_energy + rx_energy)
                if nb_tx == 1:
                    n = nodes_on_ch[0]
                    rng = rng_manager.get_stream("traffic", n)
                    success = True
                    if (
                        fine_fading_std > 0.0
                        and rng.normal(0.0, fine_fading_std) < -3.0
                    ):
                        success = False
                    if noise_std > 0.0 and rng.normal(0.0, noise_std) > 3.0:
                        success = False
                    if success:
                        delivered += 1
                        delays.append(0)
                        if debug_rx:
                            logging.debug(f"t={t:.3f} Node {n} GW {gw} CH {ch} reçu")
                    else:
                        collisions += 1
                        if debug_rx:
                            logging.debug(
                                f"t={t:.3f} Node {n} GW {gw} CH {ch} rejeté (bruit)"
                            )
                            diag_logger.info(
                                f"t={t:.3f} gw={gw} ch={ch} collision=[{n}] cause=noise"
                            )
                else:
                    rng = rng_manager.get_stream("traffic", nodes_on_ch[0])
                    winner = rng.choice(nodes_on_ch)
                    success = True
                    if (
                        fine_fading_std > 0.0
                        and rng.normal(0.0, fine_fading_std) < -3.0
                    ):
                        success = False
                    if noise_std > 0.0 and rng.normal(0.0, noise_std) > 3.0:
                        success = False
                    if success:
                        collisions += nb_tx - 1
                        delivered += 1
                        delays.append(0)
                        if debug_rx:
                            for n in nodes_on_ch:
                                if n == winner:
                                    logging.debug(
                                        f"t={t:.3f} Node {n} GW {gw} CH {ch} reçu après collision"
                                    )
                                else:
                                    logging.debug(
                                        f"t={t:.3f} Node {n} GW {gw} CH {ch} perdu (collision)"
                                    )
                        diag_logger.info(
                            f"t={t:.3f} gw={gw} ch={ch} collision={nodes_on_ch} winner={winner}"
                        )
                    else:
                        collisions += nb_tx
                        if debug_rx:
                            for n in nodes_on_ch:
                                logging.debug(
                                    f"t={t:.3f} Node {n} GW {gw} CH {ch} perdu (collision/bruit)"
                                )
                        diag_logger.info(
                            f"t={t:.3f} gw={gw} ch={ch} collision={nodes_on_ch} none"
                        )

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
    parser = argparse.ArgumentParser(description="Simulateur LoRa – Mode CLI")
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

    if args.runs < 1:
        parser.error("--runs must be >= 1")

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
        gw.pop_downlink(node.id)  # illustration
        logging.info(f"Exemple LoRaWAN : trame uplink FCnt={frame.fcnt}, RX1={rx1}s")
        sys.exit()

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
        f"Débit moyen={averages[5]:.2f} bps"
    )

    if args.output:
        with open(args.output, mode="w", newline="") as f:
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
            for run_idx, (d, c, p, e, ad, th) in enumerate(results, start=1):
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
                        f"{p:.2f}",
                        f"{e:.3f}",
                        f"{ad:.2f}",
                        f"{th:.2f}",
                    ]
                )
        logging.info(f"Résultats enregistrés dans {args.output}")

    return results, tuple(averages)


if __name__ == "__main__":
    main()
