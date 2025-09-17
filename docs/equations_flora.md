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
`antenna_gain = 0` dBi【F:loraflexsim/launcher/channel.py†L26-L42】. Pour une
distance de `2` km :

```text
loss = 128.95 + 23.2 * log10(2) ≈ 135.9 dB
```

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
