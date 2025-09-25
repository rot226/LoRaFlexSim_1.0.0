# Guide de reproduction FLoRa

Ce guide rassemble les réglages indispensables pour aligner un scénario LoRaFlexSim sur les publications historiques du projet FLoRa (OMNeT++). Il complète la section « Reproduire FLoRa » du README en regroupant les paramètres à vérifier avant toute campagne de validation.

## 1. Préparer l'environnement

1. **Installer les dépendances** via `pip install -e .` dans un environnement virtuel Python 3.10+.
2. **Cloner les références FLoRa** (`flora-master`) afin de disposer des fichiers INI/FED et des courbes radio d'origine. Les scripts de LoRaFlexSim détectent automatiquement ces ressources lorsqu'elles sont présentes à la racine du dépôt.【F:loraflexsim/launcher/simulator.py†L371-L385】【F:loraflexsim/launcher/channel.py†L68-L114】
3. **Importer les positions** des nœuds/passerelles depuis un INI FLoRa grâce à `Simulator(config_file="flora-master/simulations/.../scenario.ini", flora_mode=True)` ou via `SimulationConfig.from_ini` pour reconstruire les entités à la volée.【F:loraflexsim/launcher/simulator.py†L251-L295】【F:loraflexsim/architecture.py†L28-L69】

## 2. Paramètres indispensables

Activez systématiquement les options suivantes sur le constructeur `Simulator` :

- `flora_mode=True` : applique automatiquement le modèle physique `omnet_full`, charge la matrice de collisions non orthogonales, force le shadowing log-normal de FLoRa et verrouille le seuil de détection à `-110 dBm` sur tous les canaux.【F:loraflexsim/launcher/simulator.py†L354-L470】【F:loraflexsim/launcher/channel.py†L454-L520】
- `flora_timing=True` : aligne les temporisations MAC (RX1/RX2, latence serveur, traitement réseau) sur celles d'OMNeT++ pour garantir des fenêtres descendantes identiques.【F:loraflexsim/launcher/simulator.py†L231-L388】【F:loraflexsim/launcher/server.py†L72-L321】
- `adr_method="avg"` : reproduit la stratégie ADR historique basée sur la moyenne glissante des 20 derniers SNR remontés par chaque nœud.【F:loraflexsim/launcher/server.py†L216-L321】【F:tests/test_flora_sca.py†L18-L39】
- `phy_model="flora"` ou `"flora_cpp"` (si la bibliothèque native est compilée) : garantit l'utilisation des équations de PER et du comportement de capture exacts du code C++.【F:loraflexsim/launcher/simulator.py†L446-L575】【F:README.md†L582-L662】
- `environment="flora"` (ou `flora_hata`/`flora_oulu`) sur chaque canal pour reprendre les profils de perte log-normale validés par FLoRa.【F:loraflexsim/launcher/channel.py†L68-L114】

### Intervalle de trafic

Lorsque les fichiers INI ne précisent pas `timeToNextPacket`, LoRaFlexSim ramène automatiquement `packet_interval` et `first_packet_interval` à `100 s` pour refléter la loi exponentielle utilisée par FLoRa. Vérifiez cette valeur si vous écrivez un scénario custom.【F:loraflexsim/launcher/simulator.py†L342-L385】

## 3. Mode compatibilité et chargement des scénarios

- **Mode compatibilité tableau de bord** : activez le bouton *Mode FLoRa complet* pour verrouiller les paramètres ci-dessus depuis l'interface Panel. La bascule reflète `flora_mode`, `flora_timing`, la configuration du modèle physique et les seuils radio requis.【F:loraflexsim/launcher/dashboard.py†L194-L910】
- **Lecture d'un INI FLoRa** : `load_config` interprète les sections `[nodes]` et `[gateways]`, convertit les coordonnées et remonte les intervalles moyens présents dans le fichier. Ces valeurs sont ensuite injectées dans `Simulator` pour reproduire la cadence de trafic d'origine.【F:loraflexsim/launcher/config_loader.py†L8-L125】
- **Script d'exemple** : `python examples/run_flora_example.py` combine automatiquement `flora_mode`, `flora_timing`, `adr_method="avg"` et le chargement d'un INI de référence pour livrer une simulation clé en main.【F:examples/run_flora_example.py†L1-L58】

## 4. Contrôles rapides avant validation

| Élément | Vérification | Commande/conseil |
| --- | --- | --- |
| Paramètres radio | `flora_mode=True`, `phy_model="flora"`, preset `environment` cohérent | Inspecter `simulator.flora_mode` et `channel.environment` dans un REPL |
| Trafic | Intervalle exponentiel `100 s` ou valeur issue de l'INI | `print(simulator.packet_interval)` |
| ADR | Serveur configuré en méthode `avg` | `print(simulator.network_server.adr_method)` |
| Temporisations | `flora_timing=True` et `rx_delay=1` | `print(simulator.flora_timing, simulator.rx_delay)` |
| Références FLoRa | Traces `.sca` présentes pour la comparaison | `ls tests/integration/data/*.sca` |

En appliquant ces vérifications, chaque simulation LoRaFlexSim reproduit les métriques PDR, collisions et SNR documentées par FLoRa, assurant ainsi une validation croisée robuste.
