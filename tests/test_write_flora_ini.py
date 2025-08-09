from simulateur_lora_sfrd.launcher.config_loader import (
    write_flora_ini,
    parse_flora_interval,
    parse_flora_first_interval,
)


def test_write_intervals(tmp_path):
    ini = tmp_path / "scenario.ini"
    nodes = [{"x": 1.0, "y": 2.0}]
    gateways = [{"x": 3.0, "y": 4.0}]
    write_flora_ini(nodes, gateways, ini, next_interval=7.5, first_interval=1.5)
    assert parse_flora_interval(ini) == 7.5
    assert parse_flora_first_interval(ini) == 7.5
