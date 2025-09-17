# TICKET-002 – SNIR passerelle pour l’ADR serveur

## Description
Lors de la réception d’un uplink, le serveur ADR estime le SNR en soustrayant un bruit moyen global `Channel.noise_floor_dBm()` au RSSI remonté par la passerelle.【F:loraflexsim/launcher/server.py†L524-L604】 Dans FLoRa, l’information SNIR par passerelle est transmise directement au serveur (`NetworkServerApp::evaluateADR`), ce qui reflète les conditions radio locales.【F:flora-master/src/LoRa/NetworkServerApp.cc†L300-L370】

## Impact
Avec plusieurs passerelles ou des environnements hétérogènes (bruits différents), l’ADR LoRaFlexSim peut sélectionner des SF/puissances inadaptés : le serveur considère un canal « bruyant » alors que la passerelle qui a décodé la trame dispose d’un SNIR élevé. Cela entraîne des régressions par rapport aux décisions FLoRa.

## Pistes de résolution
- Propager le SNIR calculé par la passerelle (`Gateway.end_reception`) au lieu de recalculer un SNR global côté serveur.
- Stocker l’écart type du bruit par passerelle pour rapprocher l’algorithme de `NetworkServerApp::evaluateADR`.
- Ajouter un test de non-régression comparant l’ADR LoRaFlexSim et FLoRa sur un scénario multi-passerelle.
