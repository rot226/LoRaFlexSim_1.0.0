# Comparaison des fonctionnalités LoRaWAN

Ce document résume les différences entre la simulation FLoRa d'origine
(`flora-master/src/LoRa/`) et l'implémentation Python présente dans `launcher/`.

## Fonctionnalités prises en charge par FLoRa

- Gestion basique des trames LoRa avec accusés de réception.
- Évaluation de l'ADR côté serveur via `NetworkServerApp::evaluateADR`.
- Types de messages ``JOIN_REQUEST`` et ``JOIN_REPLY`` définis dans
  `LoRaAppPacket.msg`.
- Aucune prise en charge intégrée des classes B ou C.
- Pas de chiffrement ou d'authentification des messages.

## Fonctionnalités de l'implémentation Python

- Support complet du protocole LoRaWAN : frames ``LoRaWANFrame``,
  chiffrement AES et calcul du MIC.
- Gestion des classes A, B et C dans `server.py` et `node.py` (beacons,
  ping slots, réception continue).
- Implémentation de nombreuses commandes MAC
  (``LinkADRReq``, ``DeviceTimeReq``, ``PingSlotChannelReq``…).
- Procédure d’activation OTAA via un serveur de join (`JoinServer`).
- Historique SNR et ajustement ADR conforme à la spécification.

## Fonctionnalités équivalentes

- Les deux versions permettent l’émission de messages et un accusé de
  réception optionnel.
- Les performances énergétiques s’appuient sur le profil FLoRa dans les
  deux cas.
- Un mécanisme d’ADR est disponible de part et d’autre, bien que
  l’algorithme diffère légèrement.

## Fonctionnalités propres à la version Python

- Sécurité LoRaWAN (chiffrement des charges utiles et MIC).
- Gestion explicite des classes B et C avec planification des downlinks.
- Grand nombre de commandes MAC supplémentaires.
- Activation OTAA avec dérivation dynamique des clés.

## Éléments pouvant affecter la comparaison des métriques

- L’ajout du chiffrement et des en-têtes LoRaWAN augmente la taille des
  paquets, ce qui se traduit par un airtime plus long qu’avec FLoRa.
- L’implémentation des classes B/C introduit des fenêtres de réception
  supplémentaires qui n’existent pas dans FLoRa.
- Les algorithmes ADR ne prennent pas en compte exactement les mêmes
  seuils, entraînant des évolutions de SF ou de puissance différentes.
- Le compteur `adr_ack_cnt` est désormais remis à zéro à chaque downlink
  et la montée en SF ou puissance suit la logique LoRaWAN après
  `adr_ack_limit + adr_ack_delay` transmissions sans réponse.
