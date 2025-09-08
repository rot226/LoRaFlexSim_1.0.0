"""Trace la distribution des Spreading Factors depuis des fichiers CSV."""

import argparse
import pandas as pd
import matplotlib.pyplot as plt

from loraflexsim.utils.plotting import parse_formats, save_multi_format


def main(files: list[str], formats: list[str]) -> None:
    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    sf_cols = [c for c in df.columns if c.startswith("sf_distribution.")]
    if sf_cols:
        sf_counts = {int(c.split(".")[1]): int(df[c].sum()) for c in sf_cols}
    else:
        sf_cols = [c for c in df.columns if c.startswith("sf")]
        sf_counts = {int(c[2:]): int(df[c].sum()) for c in sf_cols}
    if not sf_counts:
        print("Aucune colonne SF trouv\u00e9e dans les fichiers fournis.")
        return
    sfs = sorted(sf_counts)
    counts = [sf_counts[sf] for sf in sfs]
    for sf, count in zip(sfs, counts):
        print(f"SF{sf}: {count}")
    plt.bar(sfs, counts)
    plt.xlabel("Spreading Factor")
    plt.ylabel("Paquets")
    plt.grid(True)
    save_multi_format(plt.gcf(), "sf_distribution", formats)
    print("Graphique sauvegard\u00e9 dans sf_distribution.*")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", help="Fichiers CSV de m\u00e9triques")
    parser.add_argument(
        "--formats",
        default="png,jpg,eps",
        help="Liste de formats s\u00e9par\u00e9s par des virgules",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = parse_args()
    main(args.files, parse_formats(args.formats))
