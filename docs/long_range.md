# Scénario longue portée

Le module `loraflexsim.scenarios.long_range` fournit un scénario reproductible visant à
valider la faisabilité de liaisons LoRa supérieures à 10 km. Une passerelle unique est
placée au centre d'une aire carrée de 24 km de côté (576 km²) afin de positionner trois
nœuds SF12 à 10–11 km et six nœuds supplémentaires entre 4 et 9 km. Le preset
`very_long_range` étend l'aire à 32 km (1 024 km²) et ajoute deux nœuds SF12 à 13,5 et
15 km pour valider la robustesse des liaisons très longues. Les nœuds sont répartis sur
trois largeurs de bande (125/250/500 kHz) et utilisent les SF 9 à 12 pour représenter un
réseau hétérogène.

## Hypothèses radio et recommandations

Le scénario désactive le shadowing (`σ = 0 dB`) pour fournir une référence stable et se
calibre selon le preset radio choisi :

| Preset              | P<sub>TX</sub> (dBm) | Gains TX/RX (dBi) | Perte câble (dB) | PDR SF12* | RSSI max SF12 | SNR max SF12 |
|---------------------|---------------------:|------------------:|-----------------:|----------:|---------------|--------------|
| `flora`             |                 23.0 |             16/16 |             0.5  |     75 %  | −116 dBm      | 0.8 dB       |
| `flora_hata`        |                 23.0 |             16/16 |             0.5  |     75 %  | −116 dBm      | 0.7 dB       |
| `rural_long_range`  |                 16.0 |              6/6  |             0.5  |     96 %  | −105 dBm      | 12.1 dB      |
| `very_long_range`   |                 27.0 |             19/19 |             0.5  |    100 %  | −106 dBm      | 10.8 dB      |

*PDR mesuré avec `packets_per_node=8` et `seed=3`.

Ces réglages correspondent à l'utilisation d'antennes directionnelles (≈16 dBi) pour les
profils `flora`/`flora_hata`, et d'antennes colinéaires (≈6 dBi) pour `rural_long_range`.
Les niveaux de RSSI observés restent largement au‑dessus des sensibilités définies par
`Channel.FLORA_SENSITIVITY` pour chaque combinaison SF/BW, garantissant un PDR SF12 ≥ 70 %
jusqu'à 15 km selon le preset sélectionné.

## Choisir puissance et gains selon la distance

Les presets fournissent des combinaisons de puissance/gain directement exploitables.
La table ci-dessous résume les marges SF12 obtenues avec la largeur de bande 125 kHz :

| Distance cible | Preset | P<sub>TX</sub> (dBm) | Gains TX/RX (dBi) | Marge RSSI estimée* |
|----------------|--------|---------------------:|------------------:|--------------------:|
| 10 km          | `rural_long_range` | 16.0 | 6 / 6  | +28.7 dB |
| 12 km          | `flora_hata`       | 23.0 | 16 / 16 | +10.4 dB |
| 15 km          | `very_long_range`  | 27.0 | 19 / 19 | +21.3 dB |

*Marge calculée via `scripts/long_range_margin.py --preset <preset> --distances 10 12 15`.

## Exécution et vérification

L'intégration `tests/integration/test_long_range_large_area.py` vérifie que le PDR SF12
reste supérieur à 70 % pour les trois presets tout en contrôlant les marges de RSSI/SNR.
Le scénario peut également être lancé depuis la CLI :

```bash
python -m loraflexsim.run --long-range-demo        # preset par défaut : flora_hata
python -m loraflexsim.run --long-range-demo flora  # forcé sur le preset log-normal
python -m loraflexsim.run --long-range-demo very_long_range --seed 3
```

### Exemple de configuration CLI

```bash
python -m loraflexsim.run \
  --long-range-demo rural_long_range \
  --seed 3 \
  --runs 2 \
  --output results/long_range_rural.csv
```

Cette configuration reproduit les hypothèses `LongRangeParameters` du preset
`rural_long_range`, exécute deux runs consécutifs avec la graine utilisée par les tests
d'intégration et enregistre un récapitulatif des PDR et marges RSSI/SNR dans `results/`.

Le script affiche la PDR agrégée, les métriques par SF et la marge RSSI/SNR maximale
mesurée sur les paquets SF12. Pour explorer d'autres combinaisons puissance/gain, utilisez
`python scripts/long_range_margin.py --preset very_long_range --distances 10 12 15 --csv results/very_long_range_margins.csv`.
