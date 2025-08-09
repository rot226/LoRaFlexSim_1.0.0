import sys
import pandas as pd
import matplotlib.pyplot as plt


def main(files):
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
    if len(sys.argv) < 2:
        print("Usage: python analyse_resultats.py resultats1.csv [...]")
    else:
        main(sys.argv[1:])
