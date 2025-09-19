# Plan de tests LoRaFlexSim

Ce document dresse la cartographie des modules critiques et des scénarios `pytest` qui les couvrent. Il met également en avant les lacunes actuelles afin de guider les futures contributions.

## Modules clés

### `loraflexsim/launcher/channel.py`
- **Rôle :** gestion du modèle radio (perte de trajet, bruit, presets FLoRa, calcul d'airtime et de capture).
- **Tests existants :**
  - `tests/test_channel_path_loss.py` valide la loi log-normale FLoRa et les presets longue portée.
  - `tests/test_channel_path_loss_validation.py` compare les presets aux traces `.sca` de référence.
  - `tests/test_degraded_channel_interval.py`, `tests/test_long_range_presets.py` et `tests/test_mobility_multichannel_integration.py` vérifient respectivement la dégradation contrôlée, les presets longue portée et l'intégration multicanale.

### `loraflexsim/launcher/omnet_phy.py`
- **Rôle :** reproduction du PHY OMNeT++ (capture, bruit corrélé, consommation énergétique événementielle).
- **Tests existants :**
  - `tests/test_omnet_phy_energy.py`, `tests/test_rx_chain.py` et `tests/test_overlap_snir.py` couvrent l'accumulation d'énergie, la chaîne de réception et le calcul SNIR.
  - `tests/test_flora_capture.py` garantit l'équivalence des traces FLoRa.
  - `tests/test_startup_currents.py` et `tests/test_pa_ramp.py` vérifient la modélisation des transitoires.

### `loraflexsim/launcher/gateway.py`
- **Rôle :** représentation passerelle (capture, énergie, filtrage multicanal).
- **Tests existants :**
  - `tests/test_gateway_capture.py` et `tests/test_collision_capture.py` valident la logique de capture et de collision.
  - `tests/test_network_server.py`, `tests/test_rx_windows.py` et `tests/test_compare_flora.py` exercent l'interaction passerelle ↔ serveur.
  - `tests/test_energy_profile_preservation.py` s'assure que la comptabilité énergétique reste cohérente après conversions de profils.

### `loraflexsim/launcher/server.py`
- **Rôle :** ordonnanceur réseau, ADR, gestion des fenêtres RX et de la file d'événements.
- **Tests existants :**
  - `tests/test_network_server.py` couvre l'ordonnancement et la dé-duplication.
  - `tests/test_no_random_drop.py`, `tests/test_run_simulate.py` et `tests/test_class_bc.py` vérifient respectivement la livraison descendante, les scénarios CLI et les classes B/C.
  - `tests/integration/test_validation_matrix.py` confronte l'ADR serveur et les métriques globales aux traces FLoRa.

### `loraflexsim/launcher/lorawan.py`
- **Rôle :** encodage MAC (OTAA, commandes ADR, gestion des fenêtres RX, cryptographie AES/MIC).
- **Tests existants :**
  - `tests/test_class_a.py` et `tests/test_rx_windows.py` valident la temporalité RX1/RX2.
  - `tests/test_adr.py`, `tests/test_adr_lite.py` et `tests/test_adr_max.py` vérifient les conversions SF/puissance.
  - `tests/test_flora_energy.py` s'assure que la comptabilité énergétique LoRaWAN reste identique à FLoRa.

### Mobilité (`loraflexsim/launcher/*mobility*.py`)
- **Rôle :** générateurs de trajectoires (random waypoint, traces GPS, terrain).
- **Tests existants :**
  - `tests/test_random_waypoint_mobility.py`, `tests/test_path_mobility.py` et `tests/test_run_mobility_models_path.py` couvrent la génération et la persistance.
  - `tests/test_mobility_multichannel_integration.py`, `tests/test_mobility_latency.py` et `tests/test_mobility_energy_per_packet.py` vérifient l'intégration complète.
  - `tests/test_node_positions_mobility.py` contrôle la cohérence des positions injectées au simulateur.

### API (`loraflexsim/launcher/web_api.py`)
- **Rôle :** façade FastAPI pour piloter le simulateur et diffuser les métriques en WebSocket.
- **Tests existants :** `tests/test_rest_api_gap.py` vérifie la disponibilité de
  l'endpoint `/simulations/status` et le cycle de vie complet (repos → en cours
  → arrêté).

## Lacunes identifiées et scénarios `pytest`

| Lacune | Description | Nouveau test |
| --- | --- | --- |
| Duty-cycle dynamique | Le `DutyCycleReq` LoRaWAN ajuste désormais le `DutyCycleManager` et replanifie les transmissions. | `tests/test_duty_cycle_gap.py` |

## Commandes utiles

- Lancer uniquement les tests de couverture des lacunes :
  ```bash
  pytest tests/test_rest_api_gap.py tests/test_energy_breakdown_gap.py tests/test_duty_cycle_gap.py
  ```
- Exécuter la matrice d'intégration complète :
  ```bash
  pytest tests/integration/test_validation_matrix.py
  ```

Le scénario `tests/test_energy_breakdown_gap.py` vérifie désormais que la décomposition énergétique expose la composante `"ramp"`.

Ce plan doit être maintenu à jour lors de l'ajout de nouvelles fonctionnalités ou de la fermeture des tests marqués `xfail`.
