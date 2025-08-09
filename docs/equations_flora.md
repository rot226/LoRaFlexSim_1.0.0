# Équations principales du simulateur

Ce document rassemble les formules de référence employées par le simulateur FLoRa.

## Perte de parcours

Le module `flora_phy.py` reproduit la perte de parcours de FLoRa :

```python
loss = PATH_LOSS_D0 + 10 * n * math.log10(distance / REFERENCE_DISTANCE)
```

avec `PATH_LOSS_D0 = 127.41` dB et `REFERENCE_DISTANCE = 40` m. L'exposant `n` vaut `2.7` pour le profil `flora`【F:README.md†L424-L433】【F:simulateur_lora_sfrd/launcher/flora_phy.py†L29-L61】.

## Taux d'erreur paquet (PER)

La probabilité d'erreur est approchée par une loi logistique :

```python
PER = 1 / (1 + math.exp(2 * (snr - (th + 2))))
```

où `th` correspond au seuil SNR du spreading factor courant【F:README.md†L434-L441】【F:simulateur_lora_sfrd/launcher/flora_phy.py†L127-L130】.

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
【F:README.md†L642-L661】【F:simulateur_lora_sfrd/launcher/channel.py†L558-L570】

## Modèle OMNeT++

Les équations de calcul du taux d'erreur binaire (BER) et symbolique (SER) proviennent de `omnet_modulation.py` :

```python
dsnr = 20.0 * snir * bandwidth / bitrate
# Somme combinatoire
dsumk = ...
return (8.0 / 15.0) * (1.0 / 16.0) * dsumk
```

```python
ber = calculate_ber(snir, bandwidth, bitrate)
ser = 1.0 - (1.0 - ber) ** 4
return min(max(ser, 0.0), 1.0)
```
【F:simulateur_lora_sfrd/launcher/omnet_modulation.py†L8-L35】
