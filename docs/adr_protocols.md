# Protocoles ADR LoRa

Cette page résume plusieurs stratégies d'Adaptive Data Rate (ADR) pour LoRaWAN.
Le protocole `ADR_ML` propose une approche fondée sur le machine learning.

| Protocole | Principe général | Machine learning | Avantages | Limites |
|-----------|-----------------|-----------------|-----------|---------|
| ADR standard | Algorithme LoRaWAN basé sur l'historique SNR pour ajuster SF et puissance. | Non | Simple, conforme à la spécification, faible surcharge réseau. | Réagit lentement, peu adapté aux nœuds mobiles ou aux environnements très variables. |
| EXPLoRa-SF | Répartition équitable des spreading factors pour maximiser le débit global. | Non | Améliore l'équité entre nœuds, réduit les collisions. | Nécessite une coordination centrale, peut augmenter la latence pour certains nœuds. |
| EXPLoRa-AT | Extension d'EXPLoRa optimisant SF et temps d'accès pour équilibrer l'occupation du canal. | Non | Meilleure utilisation du temps d'antenne, réduit la congestion. | Complexité accrue, besoin de synchronisation précise. |
| ADR-Lite | Version simplifiée avec seuils SNR fixes pour un ajustement rapide. | Non | Faible calcul côté serveur, adaptation rapide. | Moins précise, risque d'augmentation de la consommation ou des collisions. |
| ADR-Max | Algorithme ADR standard exploitant le SNR maximal des 20 derniers uplinks pour réduire SF et puissance. | Non | Compatible LoRaWAN, optimise le débit. | Requiert un historique suffisant, réagit lentement aux variations rapides. |
| RADR | ADR réactif ajustant SF et puissance à chaque message selon la dernière qualité du lien. | Oui | Très réactif aux variations, adapté aux scénarios de mobilité. | Mesures bruyantes entraînant des oscillations, nécessite plus de signalisations. |
| ADR_ML | Modèle fondé sur le machine learning pour prédire SF et puissance à partir des caractéristiques du lien. | Oui | Peut s'adapter à des scénarios complexes, performances potentielles supérieures. | Besoin de données d'entraînement, coût computationnel, explicabilité limitée. |

L'algorithme **ADR-Lite** n'emploie aucun procédé de machine learning : il se contente de comparer le SNR mesuré à des seuils fixes pour ajuster rapidement le spreading factor.

## ADR-Max

Cette stratégie suit l'algorithme ADR standard décrit dans la spécification LoRaWAN.
Le serveur calcule le SNR maximal observé parmi les 20 derniers uplinks d'un nœud.
Lorsque ce SNR offre une marge suffisante, l'algorithme réduit d'abord le
spreading factor puis la puissance d'émission afin d'augmenter le débit tout en
restant compatible avec LoRaWAN.

**Avantages**

- Optimise le débit et la consommation énergétique.
- Conserve une compatibilité totale avec la spécification LoRaWAN.

**Risques**

- Nécessite au moins 20 uplinks pour une estimation fiable.
- Réagit lentement aux fluctuations rapides du canal radio.

## EXPLoRa-AT

Cette variante d'EXPLoRa initialise tous les nœuds avec une marge
d'installation de 10 dB et le spreading factor SF12. Chaque nœud émet
ainsi à puissance maximale et l'algorithme ajuste ensuite SF et puissance
en fonction du SNR mesuré lors des premiers uplinks pour équilibrer
l'occupation du canal.
