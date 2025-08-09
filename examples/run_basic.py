"""Exemple basique de simulation LoRa."""

import os
import sys
import argparse

# Ajoute le répertoire parent pour pouvoir importer le package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from simulateur_lora_sfrd.launcher import Simulator
from simulateur_lora_sfrd.launcher.adr_standard_1 import apply as adr1

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Exemple basique de simulation LoRa")
    parser.add_argument("--nodes", type=int, default=20, help="Nombre de nœuds")
    parser.add_argument("--steps", type=int, default=500, help="Durée de la simulation")
    parser.add_argument(
        "--dump-intervals",
        action="store_true",
        help="Exporte les intervalles dans des fichiers Parquet",
    )
    parser.add_argument(
        "--capture-mode",
        choices=["advanced", "flora"],
        help="Active la dégradation du canal avec le mode de capture choisi",
    )
    args = parser.parse_args()

    sim = Simulator(
        num_nodes=args.nodes,
        packet_interval=10.0,
        transmission_mode="Random",
        adr_method="avg",
        dump_intervals=args.dump_intervals,
    )
    if args.capture_mode:
        adr1(sim, degrade_channel=True, capture_mode=args.capture_mode)
    sim.run(args.steps)
    print(sim.get_metrics())
