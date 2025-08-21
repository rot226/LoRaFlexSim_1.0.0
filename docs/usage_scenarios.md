# Scénarios d'utilisation

Ce document décrit les scripts fournis pour lancer et visualiser des simulations
LoRa. Chaque utilitaire indique ses paramètres, leurs valeurs par défaut et la
sortie attendue.

## Scripts de simulation (`run_*`)

### `run_mobility_multichannel.py`
- **Description** : exécute quatre scénarios combinant mobilité et mono/tri‑canal.
- **Paramètres principaux**
  - `--nodes` (50) : nombre de nœuds simulés.
  - `--packets` (100) : paquets à émettre par nœud.
  - `--seed` (1) : graine aléatoire.
  - `--adr-node`, `--adr-server` : active l'ADR sur les nœuds/serveur.
  - `--area-size` (1000.0) : côté du carré de simulation (m).
  - `--interval` (60.0) : intervalle moyen d'émission (s).
  - `--replicates` (1) : répétitions du scénario.
- **Sortie** : `results/mobility_multichannel.csv` contenant moyenne et écart‑type de
  la PDR, du taux de collision, du délai moyen et de l'énergie par nœud.

### `run_mobility_latency_energy.py`
- **Description** : mêmes scénarios que ci‑dessus en enregistrant PDR, délai,
  énergie et collisions.
- **Paramètres** : identiques à `run_mobility_multichannel.py`.
- **Sortie** : `results/mobility_latency_energy.csv` avec moyenne et écart‑type des
  quatre métriques.

### `run_battery_tracking.py`
- **Description** : suit l'énergie restante de chaque nœud après chaque événement.
- **Paramètres**
  - `--nodes` (5) : nombre de nœuds.
  - `--packets` (3) : paquets par nœud.
  - `--seed` (1) : graine aléatoire.
- **Sortie** : `results/battery_tracking.csv` avec `time`, `node_id`, `energy_j` et
  `capacity_j`.

## Scripts de visualisation (`plot_*`)

### `plot_mobility_multichannel.py`
- **Paramètres** : chemin du CSV agrégé et `--output-dir` ("figures").
- **Sortie** : graphiques PNG de PDR, taux de collision, délai moyen et énergie
  moyenne par nœud.

### `plot_mobility_latency_energy.py`
- **Paramètres** : CSV d'entrée et `--output-dir` ("figures").
- **Sortie** : fichiers SVG pour la PDR, le délai moyen, l'énergie moyenne par
  nœud et le taux de collision.

### `plot_battery_tracking.py`
- **Paramètres** : aucun ; lit `results/battery_tracking.csv`.
- **Sortie** : `figures/battery_tracking.png` montrant l'énergie résiduelle.

### `plot_node_positions.py`
- **Paramètres** : `--num-nodes` (100), `--area-size` (1000.0), `--seed` (42),
  `--output` ("figures/node_positions.png").
- **Sortie** : carte de dispersion des positions initiales.

## Scénarios prédéfinis

Les scénarios utilisés par les scripts `run_mobility_multichannel.py` et
`run_mobility_latency_energy.py` sont :

| Nom | Mobilité | Fréquences (MHz) |
|-----|-----------|-------------------|
| `static_single` | Non | 868.1 |
| `static_three`  | Non | 868.1 / 868.3 / 868.5 |
| `mobile_single` | Oui | 868.1 |
| `mobile_three`  | Oui | 868.1 / 868.3 / 868.5 |

## Exemple complet

```bash
python scripts/run_mobility_multichannel.py --nodes 200 --interval 1 --replicates 5
python scripts/plot_mobility_multichannel.py results/mobility_multichannel.csv
```

Le premier script génère `results/mobility_multichannel.csv`, puis le second
crée des graphiques dans le dossier `figures`.

## Interprétation des métriques

- **PDR** (« Packet Delivery Ratio ») : pourcentage de paquets reçus. 100 %
  est le plafond théorique ; une valeur basse indique une forte perte.
- **Énergie par nœud** : joules consommés par un nœud. Le plafond est la
  capacité de la batterie ; une valeur élevée signifie une durée de vie plus
  courte.
- **Délai moyen** : temps moyen entre l'émission et la réception. Des délais
  trop importants peuvent violer les exigences applicatives.
- **Taux de collision** : pourcentage de transmissions perdues pour collision
  (plafond à 100 %). Un taux élevé signale une saturation du canal.

