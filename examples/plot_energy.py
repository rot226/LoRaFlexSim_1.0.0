"""Trace la consommation d'énergie totale ou par nœud depuis des CSV."""
import sys
import argparse
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt


def main(
    files: list[str],
    per_node: bool,
    output_dir: Path,
    basename: str | None,
) -> None:
    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    output_dir.mkdir(parents=True, exist_ok=True)
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
        if basename is None:
            basename = "energy_per_node"
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
        if basename is None:
            basename = "energy_total"
    plt.tight_layout()
    for ext, params in {"png": {"dpi": 300}, "jpg": {"dpi": 300}, "eps": {}}.items():
        path = output_dir / f"{basename}.{ext}"
        plt.savefig(path, **params)
        print(f"Graphique sauvegardé dans {path}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Trace l'énergie consommée et sauvegarde le graphique en PNG, JPG et EPS"
    )
    parser.add_argument("files", nargs="+", help="Fichiers metrics CSV")
    parser.add_argument(
        "--per-node",
        action="store_true",
        help="Trace la consommation pour chaque nœud",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("."),
        help="Répertoire de sortie (défaut : dossier courant)",
    )
    parser.add_argument(
        "--basename",
        default=None,
        help="Nom de base du fichier sans extension. Par défaut 'energy_total' ou 'energy_per_node' selon --per-node",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    main(args.files, args.per_node, args.output_dir, args.basename)

