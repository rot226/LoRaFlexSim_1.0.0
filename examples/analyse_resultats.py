import sys
import argparse
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt


def main(files: list[str], output_dir: Path, basename: str) -> None:
    data = [pd.read_csv(f) for f in files]
    df = pd.concat(data, ignore_index=True)
    by_nodes = df.groupby("nodes")["PDR(%)"].mean()
    print(by_nodes)
    by_nodes.plot(marker="o")
    plt.xlabel("Nombre de nœuds")
    plt.ylabel("PDR moyen (%)")
    plt.grid(True)
    plt.tight_layout()
    output_dir.mkdir(parents=True, exist_ok=True)
    for ext, params in {"png": {"dpi": 300}, "jpg": {"dpi": 300}, "eps": {}}.items():
        path = output_dir / f"{basename}.{ext}"
        plt.savefig(path, **params)
        print(f"Graphique sauvegardé dans {path}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Analyse des résultats et sauvegarde le PDR moyen en PNG, JPG et EPS"
        )
    )
    parser.add_argument("files", nargs="+", help="Fichiers de résultats CSV")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("."),
        help="Répertoire de sortie (défaut : dossier courant)",
    )
    parser.add_argument(
        "--basename",
        default="pdr_par_nodes",
        help="Nom de base du fichier sans extension",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    main(args.files, args.output_dir, args.basename)

