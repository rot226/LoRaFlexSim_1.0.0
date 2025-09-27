# Résultats de la démo longue portée

## Synthèse du preset `flora_hata`
- Aire de simulation : 576 km² avec 9 nœuds (8 paquets chacun).
- PDR globale : 95,83 %.
- PDR par Spreading Factor :
  - SF12 : 91,67 % (limitée par les nœuds en bordure vers ~11 km).
  - SF11 : 100,00 %.
  - SF10 : 100,00 %.
  - SF9 : 93,75 %.
- Marge RSSI pour SF12 : –114,62 dBm (maximum observé).
- Marge SNR pour SF12 : 2,39 dB (maximum observé).

Observation notable : le preset `flora_hata` conserve une livraison parfaite pour les paquets SF11 et SF10, tandis que les SF12 et SF9 subissent une légère baisse (≤ 8 points de pourcentage) en raison des liaisons longues distances.

## Export des timelines de métriques

Le tableau de bord Panel permet désormais d'exporter, en plus des événements et
des métriques agrégées, une timeline détaillée par run. Le bouton **Exporter**
crée un fichier `metrics_timeline_<horodatage>.csv` obtenu via `pandas.concat`
de toutes les timelines de runs. Chaque ligne correspond à un événement
`TX_END` et contient notamment l'instant simulé, la PDR cumulée, les collisions
cumulées, l'énergie totale et le débit instantané.
