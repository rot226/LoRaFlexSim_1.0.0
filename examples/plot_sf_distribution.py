"""Trace la distribution des Spreading Factors depuis des fichiers CSV."""
import argparse
import pandas as pd
import matplotlib.pyplot as plt

from loraflexsim.utils.plotting import configure_style


configure_style()
def main(files: list[str], style: str | None = None) -> None:
    configure_style(style)
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
    plt.savefig("sf_distribution.png")
    print("Graphique sauvegard\u00e9 dans sf_distribution.png")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", help="Fichiers CSV de métriques")
    parser.add_argument(
        "--style", help="Matplotlib style to apply (overrides MPLSTYLE)"
    )
    args = parser.parse_args()
    main(args.files, args.style)
