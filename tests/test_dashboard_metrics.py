"""Tests unitaires pour l'agrégation des métriques du tableau de bord."""

from pathlib import Path
import ast
import importlib


def _load_aggregate_function():
    dashboard_path = (
        Path(__file__).resolve().parents[1] / "loraflexsim" / "launcher" / "dashboard.py"
    )
    source = dashboard_path.read_text(encoding="utf-8")
    module_ast = ast.parse(source)
    func_source = None
    for node in module_ast.body:
        if isinstance(node, ast.FunctionDef) and node.name == "aggregate_run_metrics":
            func_source = ast.get_source_segment(source, node)
            break
    if func_source is None:
        raise AssertionError("aggregate_run_metrics introuvable dans dashboard.py")
    namespace: dict = {}
    exec(func_source, namespace)
    return namespace["aggregate_run_metrics"]


aggregate_run_metrics = _load_aggregate_function()


def test_aggregate_run_metrics_weighted_values():
    metrics_runs = [
        {
            "tx_attempted": 10,
            "delivered": 9,
            "collisions": 1,
            "retransmissions": 2,
            "duplicates": 0,
            "energy_J": 1.5,
            "energy_nodes_J": 1.0,
            "energy_gateways_J": 0.5,
            "avg_delay_s": 2.0,
            "avg_arrival_interval_s": 5.0,
            "throughput_bps": 100.0,
            "simulation_time_s": 10.0,
            "energy_class_A_J": 1.0,
        },
        {
            "tx_attempted": 1000,
            "delivered": 500,
            "collisions": 500,
            "retransmissions": 50,
            "duplicates": 1,
            "energy_J": 100.0,
            "energy_nodes_J": 60.0,
            "energy_gateways_J": 40.0,
            "avg_delay_s": 10.0,
            "avg_arrival_interval_s": 7.0,
            "throughput_bps": 5.0,
            "simulation_time_s": 100.0,
            "energy_class_A_J": 30.0,
        },
    ]

    aggregated = aggregate_run_metrics(metrics_runs)

    assert aggregated["tx_attempted"] == 1010
    assert aggregated["delivered"] == 509
    assert aggregated["collisions"] == 501
    assert aggregated["retransmissions"] == 52
    assert aggregated["duplicates"] == 1
    assert aggregated["energy_J"] == 101.5
    assert aggregated["energy_nodes_J"] == 61.0
    assert aggregated["energy_gateways_J"] == 40.5
    assert aggregated["simulation_time_s"] == 110.0
    assert aggregated["energy_class_A_J"] == 31.0

    # PDR doit correspondre au rapport global entre livraisons et tentatives.
    expected_pdr = 509 / 1010
    assert aggregated["PDR"] == expected_pdr

    # Le délai moyen est pondéré par le nombre de paquets livrés.
    expected_delay = (2.0 * 9 + 10.0 * 500) / 509
    assert aggregated["avg_delay_s"] == expected_delay

    # L'intervalle d'émission moyen est pondéré par les tentatives.
    expected_interval = (5.0 * 10 + 7.0 * 1000) / 1010
    assert aggregated["avg_arrival_interval_s"] == expected_interval

    # Le débit agrégé doit être pondéré par la durée simulée.
    expected_throughput = (100.0 * 10.0 + 5.0 * 100.0) / 110.0
    assert aggregated["throughput_bps"] == expected_throughput


