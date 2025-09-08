import argparse
import pandas as pd
import matplotlib.pyplot as plt

from loraflexsim.utils.plotting import configure_style


configure_style()


def main(files: list[str], style: str | None = None) -> None:
    configure_style(style)
    data = [pd.read_csv(f) for f in files]
    df = pd.concat(data, ignore_index=True)
    by_nodes = df.groupby("nodes")["PDR(%)"].mean()
    print(by_nodes)
    by_nodes.plot(marker="o")
    plt.xlabel("Nombre de n\u0153uds")
    plt.ylabel("PDR moyen (%)")
    plt.grid(True)
    plt.savefig("pdr_par_nodes.png")
    print("Graphique sauvegard\u00e9 dans pdr_par_nodes.png")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", help="Fichiers CSV de résultats")
    parser.add_argument(
        "--style", help="Matplotlib style to apply (overrides MPLSTYLE)"
    )
    args = parser.parse_args()
    main(args.files, args.style)
