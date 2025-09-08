"""Trace la consommation d'énergie totale ou par nœud depuis des CSV."""
import sys
import argparse
import pandas as pd
import matplotlib.pyplot as plt

from loraflexsim.utils.plotting import configure_style


configure_style()


def main(files: list[str], per_node: bool, style: str | None = None) -> None:
    configure_style(style)
    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    if per_node:
        cols = [c for c in df.columns if c.startswith("energy_by_node.")]
        if not cols:
            print("Aucune colonne de consommation par nœud trouvée.")
            return
        energy = {int(c.split(".")[1]): df[c].mean() for c in cols}
        nodes = sorted(energy)
        values = [energy[n] for n in nodes]
        plt.bar(nodes, values)
        plt.xlabel("Nœud")
        plt.ylabel("Énergie consommée (J)")
        plt.grid(True)
        plt.savefig("energy_per_node.png")
        print("Graphique sauvegardé dans energy_per_node.png")
    else:
        col = "energy_J" if "energy_J" in df.columns else "energy"
        if col not in df.columns:
            print("Aucune colonne energy_J ou energy trouvée.")
            return
        if "nodes" in df.columns:
            series = df.groupby("nodes")[col].mean()
            series.plot(marker="o")
            plt.xlabel("Nombre de nœuds")
        else:
            series = df[col]
            series.plot(marker="o")
            plt.xlabel("Exécution")
        plt.ylabel("Énergie consommée (J)")
        plt.grid(True)
        plt.savefig("energy_total.png")
        print("Graphique sauvegardé dans energy_total.png")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Trace l'énergie consommée")
    parser.add_argument("files", nargs="+", help="Fichiers metrics CSV")
    parser.add_argument(
        "--per-node",
        action="store_true",
        help="Trace la consommation pour chaque nœud",
    )
    parser.add_argument(
        "--style", help="Matplotlib style to apply (overrides MPLSTYLE)"
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    main(args.files, args.per_node, args.style)
