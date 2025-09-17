# Scénario longue portée

Le module `loraflexsim.scenarios.long_range` fournit un scénario reproductible visant à
valider la faisabilité de liaisons LoRa supérieures à 10 km. Une passerelle unique est
placée au centre d'une aire carrée de 24 km de côté (576 km²) afin de pouvoir positionner
trois nœuds SF12 à 10–11 km et six nœuds supplémentaires entre 4 et 9 km. Les nœuds sont
répartis sur trois largeurs de bande (125/250/500 kHz) et utilisent les SF 9 à 12 pour
représenter un réseau hétérogène.

## Hypothèses radio et recommandations

Le scénario désactive le shadowing (`σ = 0 dB`) pour fournir une référence stable et se
calibre selon le preset radio choisi :

| Preset              | P<sub>TX</sub> (dBm) | Gains TX/RX (dBi) | Perte câble (dB) | PDR SF12* | RSSI max SF12 | SNR max SF12 |
|---------------------|---------------------:|------------------:|-----------------:|----------:|---------------|--------------|
| `flora`             |                 23.0 |             16/16 |             0.5  |     75 %  | −116 dBm      | 0.8 dB       |
| `flora_hata`        |                 23.0 |             16/16 |             0.5  |     75 %  | −116 dBm      | 0.7 dB       |
| `rural_long_range`  |                 16.0 |              6/6  |             0.5  |     96 %  | −105 dBm      | 12.1 dB      |

*PDR mesuré avec `packets_per_node=8` et `seed=3`.

Ces réglages correspondent à l'utilisation d'antennes directionnelles (≈16 dBi) pour les
profils `flora`/`flora_hata`, et d'antennes colinéaires (≈6 dBi) pour `rural_long_range`.
Les niveaux de RSSI observés restent largement au‑dessus des sensibilités définies par
`Channel.FLORA_SENSITIVITY` pour chaque combinaison SF/BW, garantissant un PDR SF12 ≥ 70 %
jusqu'à 11 km.

## Exécution et vérification

L'intégration `tests/integration/test_long_range_large_area.py` vérifie que le PDR SF12
reste supérieur à 70 % pour les trois presets tout en contrôlant les marges de RSSI/SNR.
Le scénario peut également être lancé depuis la CLI :

```bash
python -m loraflexsim.run --long-range-demo        # preset par défaut : flora_hata
python -m loraflexsim.run --long-range-demo flora  # forcé sur le preset log-normal
```

Le script affiche la PDR agrégée, les métriques par SF et la marge RSSI/SNR maximale
mesurée sur les paquets SF12.
