# TICKET-001 – Filtrage fréquentiel du calcul SNIR

## Description
Le calcul `OmnetPHY.compute_snrs` additionne l’énergie de toutes les transmissions en collision sans distinguer leur fréquence. Dans un scénario multi-canaux, un paquet reçu sur 868,1 MHz est donc dégradé par des transmissions voisines sur 868,3 MHz alors que FLoRa n’agrège que les signaux partageant exactement la même porteuse et largeur de bande.【F:loraflexsim/launcher/omnet_phy.py†L393-L507】【F:flora-master/src/LoRaPhy/LoRaAnalogModel.cc†L123-L160】

## Impact
Cette approximation provoque des faux positifs de collision/capture et fausse le SNR remonté au serveur, ce qui entraîne des pertes de paquets injustifiées dans les simulations multi-canaux. Les scénarios de validation par rapport au traceur FLoRa divergent dès que plusieurs canaux sont actifs.

## Pistes de résolution
- Ajouter `freq_list` comme paramètre obligatoire de `compute_snrs` et ignorer les transmissions dont la fréquence diffère de celle du signal étudié.
- Aligner la logique sur `LoRaAnalogModel::computeNoise` en levant une exception si des bandes se recouvrent partiellement.
- Étendre la couverture de tests pour valider le cas de collisions sur fréquences distinctes (cf. `tests/test_flora_capture.py`).
