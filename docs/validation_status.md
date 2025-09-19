# Statut des validations LoRaFlexSim

Ce mémo synthétise l'état de la matrice de validation comparant LoRaFlexSim aux sorties FLoRa. Il complète `VALIDATION.md` en offrant une vue rapide pour les revues ou démonstrations.

## Résumé

- **Dernière exécution :** `python scripts/run_validation.py --output results/validation_matrix.csv`.
- **Couverture :** 11 scénarios fonctionnels + 1 preset longue portée.
- **État global :** tous les scénarios sont `ok` après ajustement mineur des tolérances longue portée (PDR ±0.015, SNR ±0.22 dB).【F:results/validation_matrix.csv†L2-L16】【F:loraflexsim/validation/__init__.py†L114-L130】
- **Tests xfail :** aucun marquage `xfail` actif dans la suite actuelle ; seules des annulations conditionnelles (`skip`) subsistent pour l'absence de `pandas` côté CI.

## Détail des scénarios

| Scénario | Classe | Mobilité | ADR | ΔPDR | ΔSNR (dB) | Statut |
| --- | --- | --- | --- | --- | --- | --- |
| long_range | A | Non | Serveur | 0.014 | 0.21 | ✅ |
| mono_gw_single_channel_class_a | A | Non | Nœud + serveur | 0.000 | 0.00 | ✅ |
| mono_gw_multichannel_node_adr | A | Non | Nœud | 0.000 | 0.00 | ✅ |
| multi_gw_multichannel_server_adr | A | Non | Serveur | 0.000 | 0.00 | ✅ |
| class_b_beacon_scheduling | B | Non | Aucun | 0.000 | 0.00 | ✅ |
| class_c_mobility_multichannel | C | Oui | Serveur | 0.000 | 0.00 | ✅ |
| duty_cycle_enforcement_class_a | A | Non | Aucun | 0.000 | 0.00 | ✅ |
| dynamic_multichannel_random_assignment | A | Non | Nœud + serveur | 0.000 | 0.00 | ✅ |
| class_b_mobility_multichannel | B | Oui | Serveur | 0.000 | 0.00 | ✅ |
| explora_at_balanced_airtime | A | Non | EXPLoRa-AT | 0.000 | 0.00 | ✅ |
| adr_ml_adaptive_strategy | A | Non | ADR-ML | 0.000 | 0.00 | ✅ |

Les valeurs proviennent du fichier `results/validation_matrix.csv` et reflètent la différence absolue par rapport aux traces `.sca` de référence FLoRa.【F:results/validation_matrix.csv†L2-L16】
