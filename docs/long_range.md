# Scénario longue portée

Ce scénario positionne des nœuds fixes à plusieurs kilomètres les uns des autres afin de
valider la couverture en milieu rural ouvert. Deux passerelles sont espacées d'environ
6,5 km et desservent douze nœuds répartis le long de l'axe reliant les stations. Les
coordonnées sont exprimées en mètres dans `examples/long_range.yaml`.

## Hypothèses radio

- **Puissance d'émission** : chaque nœud transmet entre 17 et 27 dBm selon sa distance à
  la passerelle la plus proche pour rester au‑dessus de la sensibilité LoRa en SF 10–12.
- **Gains d'antenne** : le script de validation applique un gain de 6 dBi côté nœud et
  8 dBi côté passerelle afin de représenter une antenne colinéaire et un relais sectoriel.
- **Modèle de propagation** : canal log‑distance corrigé avec exposant γ = 2,08 et
  distance de référence de 40 m, identique au profil FLoRa `flora`.
- **Bruit et shadowing** : aucune variation aléatoire supplémentaire n'est injectée
  (σ = 0 dB) pour garantir un résultat reproductible lors de la validation.

## Validation du PDR

Le script `scripts/validate_long_range.py` exécute cinq transmissions périodiques par
nœud avec un intervalle de 30 minutes. Par défaut la validation réussit si le PDR
moyen reste supérieur à 95 %. Pour lancer la vérification :

```bash
python scripts/validate_long_range.py
```

Il est possible d'ajuster le seuil ou la graine aléatoire :

```bash
python scripts/validate_long_range.py --threshold 0.98 --seed 2
```

Le script affiche la PDR agrégée ainsi que le nombre de paquets délivrés.
