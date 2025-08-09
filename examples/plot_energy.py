"""Trace la consommation d'\u00e9nergie totale ou par n\u0153ud depuis des CSV."""
import sys
import argparse
import pandas as pd
import matplotlib.pyplot as plt


def main(files: list[str], per_node: bool) -> None:
    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    if per_node:
        cols = [c for c in df.columns if c.startswith("energy_by_node.")]
        if not cols:
            print("Aucune colonne de consommation par n\u0153ud trouv\u00e9e.")
            return
        energy = {int(c.split(".")[1]): df[c].mean() for c in cols}
        nodes = sorted(energy)
        values = [energy[n] for n in nodes]
        plt.bar(nodes, values)
        plt.xlabel("N\u0153ud")
        plt.ylabel("\u00c9nergie consomm\u00e9e (J)")
        plt.grid(True)
        plt.savefig("energy_per_node.png")
        print("Graphique sauvegard\u00e9 dans energy_per_node.png")
    else:
        col = "energy_J" if "energy_J" in df.columns else "energy"
        if col not in df.columns:
            print("Aucune colonne energy_J ou energy trouv\u00e9e.")
            return
        if "nodes" in df.columns:
            series = df.groupby("nodes")[col].mean()
            series.plot(marker="o")
            plt.xlabel("Nombre de n\u0153uds")
        else:
            series = df[col]
            series.plot(marker="o")
            plt.xlabel("Ex\u00e9cution")
        plt.ylabel("\u00c9nergie consomm\u00e9e (J)")
        plt.grid(True)
        plt.savefig("energy_total.png")
        print("Graphique sauvegard\u00e9 dans energy_total.png")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Trace l'\u00e9nergie consomm\u00e9e")
    parser.add_argument("files", nargs="+", help="Fichiers metrics CSV")
    parser.add_argument(
        "--per-node",
        action="store_true",
        help="Trace la consommation pour chaque n\u0153ud",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    main(args.files, args.per_node)
