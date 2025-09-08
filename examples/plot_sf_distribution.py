"""Trace la distribution des Spreading Factors depuis des fichiers CSV."""
import sys
import argparse
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt


def main(files: list[str], output_dir: Path, basename: str) -> None:
    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    sf_cols = [c for c in df.columns if c.startswith("sf_distribution.")]
    if sf_cols:
        sf_counts = {int(c.split(".")[1]): int(df[c].sum()) for c in sf_cols}
    else:
        sf_cols = [c for c in df.columns if c.startswith("sf")]
        sf_counts = {int(c[2:]): int(df[c].sum()) for c in sf_cols}
    if not sf_counts:
        print("Aucune colonne SF trouvée dans les fichiers fournis.")
        return
    sfs = sorted(sf_counts)
    counts = [sf_counts[sf] for sf in sfs]
    for sf, count in zip(sfs, counts):
        print(f"SF{sf}: {count}")
    plt.bar(sfs, counts)
    plt.xlabel("Spreading Factor")
    plt.ylabel("Paquets")
    plt.grid(True)
    plt.tight_layout()
    output_dir.mkdir(parents=True, exist_ok=True)
    for ext, params in {"png": {"dpi": 300}, "jpg": {"dpi": 300}, "eps": {}}.items():
        path = output_dir / f"{basename}.{ext}"
        plt.savefig(path, **params)
        print(f"Graphique sauvegardé dans {path}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Trace la distribution des SF et sauvegarde en PNG, JPG et EPS"
    )
    parser.add_argument("files", nargs="+", help="Fichiers metrics CSV")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("."),
        help="Répertoire de sortie (défaut : dossier courant)",
    )
    parser.add_argument(
        "--basename",
        default="sf_distribution",
        help="Nom de base du fichier sans extension",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    main(args.files, args.output_dir, args.basename)

