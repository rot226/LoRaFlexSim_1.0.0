import sys
import argparse
import pandas as pd
import matplotlib.pyplot as plt

from loraflexsim.utils.plotting import parse_formats, save_multi_format


def main(files, formats):
    data = [pd.read_csv(f) for f in files]
    df = pd.concat(data, ignore_index=True)
    by_nodes = df.groupby("nodes")["PDR(%)"].mean()
    print(by_nodes)
    by_nodes.plot(marker="o")
    plt.xlabel("Nombre de n\u0153uds")
    plt.ylabel("PDR moyen (%)")
    plt.grid(True)
    save_multi_format(plt.gcf(), "pdr_par_nodes", formats)
    print("Graphique sauvegard\u00e9 dans pdr_par_nodes.*")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", help="Fichiers CSV de r\u00e9sultats")
    parser.add_argument(
        "--formats",
        default="png,jpg,eps",
        help="Liste de formats s\u00e9par\u00e9s par des virgules",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = parse_args()
    main(args.files, parse_formats(args.formats))
