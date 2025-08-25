# Équations principales du simulateur

Ce document rassemble les formules de référence employées par le simulateur FLoRa.

## Perte de parcours

Le module `flora_phy.py` reproduit la perte de parcours de FLoRa :

```python
loss = PATH_LOSS_D0 + 10 * n * math.log10(distance / REFERENCE_DISTANCE)
```

avec `PATH_LOSS_D0 = 127.41` dB et `REFERENCE_DISTANCE = 40` m. L'exposant `n` vaut `2.7` pour le profil `flora`【F:README.md†L424-L433】【F:loraflexsim/launcher/flora_phy.py†L29-L61】.

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
