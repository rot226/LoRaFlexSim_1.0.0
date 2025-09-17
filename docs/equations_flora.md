# Équations principales du simulateur

Ce document rassemble les formules de référence employées par LoRaFlexSim, dérivées de FLoRa.

## Perte de parcours

Le module `flora_phy.py` reproduit la perte de parcours de FLoRa :

```python
loss = PATH_LOSS_D0 + 10 * gamma * math.log10(distance / REFERENCE_DISTANCE)
```

avec `PATH_LOSS_D0 = 127.41` dB et `REFERENCE_DISTANCE = 40` m. L'exposant `γ`
correspond à `Channel.path_loss_exp` : le profil `flora` charge `γ = 2.08`, soit
la même valeur que le paramètre `gamma` exposé par le module
`LoRaLogNormalShadowing` de FLoRa【F:loraflexsim/launcher/flora_phy.py†L37-L58】【F:loraflexsim/launcher/channel.py†L69-L77】【F:flora-master/src/LoRaPhy/LoRaLogNormalShadowing.ned†L20-L28】.
Ce module calcule exactement l'expression ci-dessus, en y ajoutant
éventuellement un terme gaussien de variance `σ = 3.57` pour le shadowing, ce
qui assure la cohérence directe avec LoRaFlexSim lorsque `flora` est
sélectionné comme environnement【F:flora-master/src/LoRaPhy/LoRaLogNormalShadowing.cc†L40-L49】.

### Limites de portée et bruit FLoRa

Le preset `flora` reproduit le profil log-normal de FLoRa (`γ = 2.08`, `σ = 3.57`), ce qui correspond à des liens fiables sur 10 à 12 km avant que le RSSI n'approche les sensibilités de la table `FLORA_SENSITIVITY`. Pour étendre la portée sans rompre la parité, le preset `rural_long_range` ajuste simultanément l'exposant, le point de référence et le shadowing suivant `Channel.ENV_PRESETS`, et il peut être sélectionné en conjonction avec `flora_mode` ou `flora_loss_model` pour des scénarios > 10 km validés par les tests longue distance.【F:loraflexsim/launcher/channel.py†L68-L80】【F:tests/test_long_range_presets.py†L1-L55】
Le bruit reste issu de la table statique de FLoRa : seules les combinaisons SF/BW définies héritent de valeurs spécifiques, les autres retombant sur le seuil `-110` dBm. Le parseur `parse_flora_noise_table` charge exactement `LoRaAnalogModel.cc`, ce qui garantit l'identité du bruit moyen tout en laissant à l'utilisateur la possibilité de fournir un autre fichier via `flora_noise_path`.【F:loraflexsim/launcher/channel.py†L93-L133】


### Modèle Hata‑Okumura

La variante Hata‑Okumura introduite dans `Channel` suit :

```python
loss = K1 + K2 * log10(distance_km)
```

avec `distance_km = distance / 1000`. Les constantes utilisées dans le profil
``flora_hata`` sont `K1 = 127.5` dB et `K2 = 35.2`【F:loraflexsim/launcher/channel.py†L12-L23】【F:loraflexsim/launcher/channel.py†L69-L76】.
Par exemple, pour `distance = 2` km :

```text
loss = 127.5 + 35.2 * log10(2) ≈ 138.1 dB
```

### Modèle Oulu

Le modèle basé sur les mesures d'Oulu calcule :

```python
loss = B + 10 * n * log10(distance / d0) - antenna_gain
```

Les paramètres par défaut sont `B = 128.95` dB, `n = 2.32`, `d0 = 1000` m et
`antenna_gain = 0` dBi【F:loraflexsim/launcher/channel.py†L26-L41】. Pour une
distance de `2` km :

```text
loss = 128.95 + 23.2 * log10(2) ≈ 135.9 dB
```

Ces variantes rejettent désormais explicitement les distances nulles ou
négatives en levant une `ValueError`, ce qui évite des entrées non physiques et
aligne les validations sur celles de FLoRa【F:loraflexsim/launcher/channel.py†L12-L41】【F:tests/test_channel_path_loss_validation.py†L1-L15】.

### Profil rural longue portée

Afin de couvrir des scénarios LoRaWAN au-delà de 5 km tout en conservant une
réception proche des seuils de FLoRa, LoRaFlexSim fournit le preset
``rural_long_range``. Celui-ci fixe ``γ = 1.7``, ``PATH_LOSS_D0 = 105`` dB et
``REFERENCE_DISTANCE = 100`` m, avec un shadowing réduit à 1.5 dB pour refléter
des zones ouvertes à antennes renforcées【F:loraflexsim/launcher/channel.py†L69-L78】.
Le tableau suivant illustre les RSSI obtenus avec une puissance d'émission de
14 dBm (cas FLoRa classique) et la marge restante vis-à-vis du seuil SF12
``-137`` dBm fourni par ``Channel.FLORA_SENSITIVITY``【F:loraflexsim/launcher/channel.py†L52-L65】 :

| Distance (km) | RSSI (dBm) | Marge vs seuil SF12 (dB) |
|---------------|------------|--------------------------|
| 1             | −108.0     | 29.0                     |
| 5             | −119.9     | 17.1                     |
| 10            | −125.0     | 12.0                     |
| 12            | −126.4     | 10.6                     |
| 15            | −128.0     | 9.0                      |

Ces valeurs montrent que, autour de 10–15 km, le RSSI reste dans la fenêtre
``−130…−120`` dBm suggérée par FLoRa, offrant une marge confortable pour des
spreading factors élevés tout en conservant une modélisation réaliste.【F:loraflexsim/launcher/channel.py†L69-L78】

### Obstacles avec le PHY OMNeT++

Lorsque `Channel` utilise le PHY inspiré d'OMNeT++, le calcul `compute_rssi`
appelle d'abord `OmnetPHY` puis retranche l'atténuation supplémentaire fournie
par `ObstacleLoss` si les positions sont connues. Les obstacles sont donc pris
en compte quel que soit le modèle de PHY actif, y compris avec les optimisations
`omnet_phy` introduites pour reproduire le comportement FLoRa【F:loraflexsim/launcher/channel.py†L579-L616】.

### Rapport signal sur bruit (SNR)

Le rapport signal sur bruit renvoyé par `Channel.compute_rssi` suit l'expression

```python
snr = rssi - noise + snr_offset_dB
```

où `noise` provient soit de la table FLoRa, soit du bruit thermique simulé.
La valeur tirée est désormais mémorisée dans `Channel.last_noise_dBm` et
réutilisée tout au long du traitement d'une transmission : atténuation par
interférence, comparaison au seuil de sensibilité et capture par la passerelle
partagent exactement le même échantillon de bruit. Cette mémorisation évite de
ré-échantillonner `noise_floor_dBm()` lorsque `noise_floor_std` est non nul et
stabilise ainsi les décisions « heard »/« collision » du simulateur
évènementiel.【F:loraflexsim/launcher/simulator.py†L900-L936】【F:loraflexsim/launcher/channel.py†L467-L557】
Par défaut, aucun « gain de traitement » n'est ajouté afin de reproduire les
traces SNR issues de FLoRa. Un paramètre optionnel `processing_gain=True`
permet toutefois de retrouver l'ancien comportement en ajoutant
`10 * log10(2 ** sf)` lorsque le spreading factor est connu, tant pour le
canal de base que pour les variantes OMNeT++ et avancées
【F:loraflexsim/launcher/channel.py†L683-L707】【F:loraflexsim/launcher/omnet_phy.py†L349-L365】【F:loraflexsim/launcher/advanced_channel.py†L668-L692】.

## Taux d'erreur paquet (PER)

La fonction `FloraPHY.packet_error_rate` accepte un paramètre `per_model`
permettant de basculer entre deux approximations :

- ``"logistic"`` — approximation historique de FLoRa :

  ```python
  PER = 1 / (1 + math.exp(2 * (snr - (th + 2))))
  ```

  où `th` est le seuil SNR du spreading factor courant【F:loraflexsim/launcher/flora_phy.py†L149-L152】.

- ``"croce"`` — modèle analytique issu des expressions BER/SER :

  ```python
  snir = 10 ** (snr / 10.0)
  ber = calculate_ber(snir, sf)
  ser = calculate_ser(snir, sf)
  n_bits = payload_bytes * 8
  per_bit = 1.0 - (1.0 - ber) ** n_bits
  n_sym = math.ceil(n_bits / sf)
  per_sym = 1.0 - (1.0 - ser) ** n_sym
  per = max(per_bit, per_sym)
  ```

  Cette formule suit l'approximation de Croce *et al.* pour un paquet de
  ``payload_bytes`` octets【F:loraflexsim/launcher/flora_phy.py†L154-L161】.

## Calcul de l'airtime

La durée d'un paquet LoRa est obtenue à partir de :

```text
T_sym = 2**SF / BW
T_preamble = (preamble_symbols + 4.25) * T_sym
N_payload = 8 + max(ceil((8*payload_size - 4*SF + 28 + 16) / (4*(SF - 2*DE))), 0)
            * (coding_rate + 4)
T_payload = N_payload * T_sym
airtime = T_preamble + T_payload
```

Cette formule est utilisée par `Channel.airtime` pour renvoyer la durée en secondes :

```python
rs = bandwidth / (2 ** sf)
ts = 1.0 / rs
de = 1 if sf >= low_data_rate_threshold else 0
cr_denom = coding_rate + 4
numerator = 8 * payload_size - 4 * sf + 28 + 16 - 20 * 0
denominator = 4 * (sf - 2 * de)
n_payload = max(math.ceil(numerator / denominator), 0) * cr_denom + 8
t_preamble = (preamble_symbols + 4.25) * ts
t_payload = n_payload * ts
return t_preamble + t_payload
```
【F:README.md†L642-L661】【F:loraflexsim/launcher/channel.py†L558-L570】

## Modèle OMNeT++

Les équations de calcul du taux d'erreur binaire (BER) et symbolique (SER)
proviennent de `omnet_modulation.py` et suivent l'approximation analytique
de Croce *et al.* (2018) :

```python
n = 2 ** sf
ber = 0.5 * math.erfc(math.sqrt(snir * n / (2 * math.pi)))
ser = 1 - (1 - ber) ** sf
```

Cette expression donne directement la BER en fonction du rapport
signal/bruit linéaire ``snir`` et du spreading factor ``sf``
【F:loraflexsim/launcher/omnet_modulation.py†L7-L25】.

## Seuil de détection (sensibilité)

Pour rester compatible avec FLoRa, le seuil de détection est obtenu à
partir de la table de sensibilité ``FLORA_SENSITIVITY``. Pour un spreading
factor ``SF`` et une largeur de bande ``BW`` donnés, le seuil appliqué est :

```python
threshold = Channel.FLORA_SENSITIVITY[sf][int(bandwidth)]
```

Une méthode utilitaire expose ce calcul via
``Channel.flora_detection_threshold`` qui fournit ``-110`` dBm par défaut
lorsque la paire ``(SF, BW)`` n'est pas présente dans la table
【F:loraflexsim/launcher/channel.py†L52-L63】.

## Calcul ADR : SNRmargin et Nstep

Lors de l'ADR serveur, la marge SNR et le nombre de pas d'adaptation sont
évalués ainsi :

```text
SNRmargin = SNRm - requiredSNR - adrDeviceMargin
Nstep = round(SNRmargin / 3)
```

où `SNRm` est le SNR moyen mesuré et `requiredSNR` le seuil requis selon le
spreading factor【F:flora-master/src/LoRa/NetworkServerApp.cc†L361-L372】.
Exemple pour `SNRm = 5` dB, `requiredSNR = -12.5` dB (SF9) et
`adrDeviceMargin = 10` dB :

```text
SNRmargin = 5 - (-12.5) - 10 = 7.5 dB
Nstep = round(7.5 / 3) = 3
```

## Consommation d'énergie

Chaque état du transceiver applique la relation élémentaire
``E = V \times I \times t`` où ``V`` est la tension d'alimentation,
``I`` le courant propre à l'état et ``t`` la durée passée dans cet état.
La méthode ``OmnetPHY.update`` incrémente ainsi quatre compteurs :

- ``E_tx = V \times I_tx \times t_tx`` pour l'émission,
- ``E_rx = V \times I_rx \times t_rx`` pour la réception,
- ``E_idle = V \times I_idle \times t_idle`` lorsque la radio est au repos,
- ``E_start = V \times I_start \times t_start`` durant les phases de
  démarrage (``start_tx`` ou ``start_rx``).

Un test de régression vérifie l'accumulation correcte de ces énergies lors
d'une transmission.

## Tableau de capture SF

La décision de capture entre deux paquets repose sur la matrice
`nonOrthDelta` ; un paquet est conservé si la différence `signalRSSI -
interferenceRSSI` dépasse la valeur correspondante :

| SF\Interf. | 7  | 8   | 9   | 10  | 11  | 12  |
|------------|----|-----|-----|-----|-----|-----|
| **7**      | 1  | -8  | -9  | -9  | -9  | -9  |
| **8**      | -11| 1   | -11 | -12 | -13 | -13 |
| **9**      | -15| -13 | 1   | -13 | -14 | -15 |
| **10**     | -19| -18 | -17 | 1   | -17 | -18 |
| **11**     | -22| -22 | -21 | -20 | 1   | -20 |
| **12**     | -25| -25 | -25 | -24 | -23 | 1   |

Par exemple, un paquet SF7 reçu à `-97` dBm en présence d'une interférence SF9
à `-90` dBm est décodé car `-97 - (-90) = -7` dB ≥ `-9` dB. La table provient du
récepteur FLoRa【F:flora-master/src/LoRaPhy/LoRaReceiver.h†L60-L67】.
