# Vérification du serveur de join

Ce document résume les vérifications manuelles effectuées pour assurer le bon fonctionnement du serveur de join minimal fourni par `loraflexsim`.

## Tests automatisés

La suite de tests `pytest` inclut `tests/test_join_server.py` qui couvre :

- l'enregistrement d'un appareil sur le `JoinServer` ;
- la validation du MIC pour un `JoinRequest` valide ;
- le chiffrement du `JoinAccept` et la dérivation des clés de session (`NwkSKey`, `AppSKey`) ;
- le rejet des requêtes avec MIC invalide et l'absence de dérivation de clés dans ce cas.

Pour exécuter uniquement ces tests :

```bash
pytest tests/test_join_server.py
```

## Simulation d'une requête OTAA

Le script Python ci-dessous permet de simuler une requête OTAA complète et de vérifier la distribution des clés côté nœud et côté serveur.

```python
from loraflexsim.launcher.join_server import JoinServer
from loraflexsim.launcher.lorawan import (
    JoinRequest,
    compute_join_mic,
    decrypt_join_accept,
    derive_session_keys,
)

join_eui = 0x70B3D57ED0000000
dev_eui = 0x0004A30B001C0530
app_key = bytes.fromhex("8A2C1F6E9D4475B0FF1133557799BBAA")

server = JoinServer(net_id=0x123456)
server.register(join_eui, dev_eui, app_key)

request = JoinRequest(join_eui, dev_eui, dev_nonce=0x2345)
request.mic = compute_join_mic(app_key, request.to_bytes())

accept, nwk_skey, app_skey = server.handle_join(request)
print(f"JoinAccept MIC valide? {accept.mic == compute_join_mic(app_key, accept.to_bytes())}")
print(f"DevAddr attribuée: 0x{accept.dev_addr:08X}")

expected_nwk, expected_app = derive_session_keys(
    app_key, request.dev_nonce, accept.app_nonce, server.net_id
)
print(
    "Clés dérivées côté serveur et nœud identiques?",
    (nwk_skey, app_skey) == (expected_nwk, expected_app),
)
print(f"NwkSKey: {nwk_skey.hex()}\nAppSKey: {app_skey.hex()}")

stored = server.get_session_keys(join_eui, dev_eui)
print(f"Clés stockées côté serveur: {stored[0].hex()} / {stored[1].hex()}")

# Vérification côté nœud (simulation)
decrypted, mic = decrypt_join_accept(app_key, accept.encrypted, len(accept.to_bytes()))
print(
    "Déchiffrement côté nœud OK?",
    decrypted.dev_addr == accept.dev_addr and mic == accept.mic,
)
print(f"AppNonce reçu: 0x{decrypted.app_nonce:06X}")
```

Le script reproduit les étapes suivantes :

1. Enregistrement du couple `(JoinEUI, DevEUI)` avec son `AppKey` ;
2. Construction du `JoinRequest` et calcul du MIC avec l'`AppKey` ;
3. Traitement de la requête par le `JoinServer` qui :
   - vérifie le MIC,
   - génère un `JoinAccept` chiffré et son MIC,
   - dérive les clés de session `NwkSKey` et `AppSKey`,
   - stocke les clés pour l'appareil ;
4. Simulation côté nœud du déchiffrement du `JoinAccept` et vérification de la cohérence des clés et du `DevAddr`.

L'exécution affiche les clés dérivées ainsi que la validation du MIC et du `JoinAccept` chiffré, confirmant que les clés distribuées au nœud correspondent à celles conservées par le serveur.
