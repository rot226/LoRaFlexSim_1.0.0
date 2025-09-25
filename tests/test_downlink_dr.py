from loraflexsim.launcher.lorawan import DOWNLINK_DR_TO_SF, rx1_downlink_dr


def test_rx1_downlink_eu868():
    assert rx1_downlink_dr("EU868", uplink_dr=5, rx1_dr_offset=2) == 3


def test_rx1_downlink_us915_table():
    assert rx1_downlink_dr("US915", uplink_dr=0, rx1_dr_offset=0) == 10
    assert rx1_downlink_dr("US915", uplink_dr=3, rx1_dr_offset=3) == 10
    assert rx1_downlink_dr("US915", uplink_dr=4, rx1_dr_offset=7) == 8


def test_rx1_downlink_unknown_region_defaults():
    assert rx1_downlink_dr("UNKNOWN", uplink_dr=2, rx1_dr_offset=5) == 0


def test_downlink_dr_to_sf_extends_mapping():
    assert DOWNLINK_DR_TO_SF[10] == 10
    assert DOWNLINK_DR_TO_SF[13] == 7
