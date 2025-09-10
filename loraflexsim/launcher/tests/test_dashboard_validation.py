import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import loraflexsim.launcher as launcher_pkg


def _stub_module():
    mod = types.ModuleType("stub")

    def apply(sim):
        sim.adr_node = False
        sim.adr_server = True

    mod.apply = apply
    return mod


for name in ["explora_sf", "explora_at", "adr_lite", "adr_max", "radr", "adr_ml"]:
    mod = _stub_module()
    setattr(launcher_pkg, name, mod)
    sys.modules[f"launcher.{name}"] = mod
    sys.modules[f"loraflexsim.launcher.{name}"] = mod

panel = pytest.importorskip("panel")
if panel.state.curdoc is None:
    from bokeh.document import Document

    panel.state.curdoc = Document()
dashboard = pytest.importorskip("loraflexsim.launcher.dashboard")


def reset_inputs():
    dashboard.sim = None
    dashboard.interval_input.value = 1.0
    dashboard.num_nodes_input.value = 1
    dashboard.area_input.value = 100.0
    dashboard.packets_input.value = 1
    dashboard.real_time_duration_input.value = 0.0
    dashboard.export_message.object = ""


def test_invalid_interval_prevents_start():
    reset_inputs()
    dashboard.interval_input.value = 0
    dashboard.on_start(None)
    assert dashboard.sim is None
    assert "⚠️" in dashboard.export_message.object


def test_invalid_nodes_prevents_start():
    reset_inputs()
    dashboard.num_nodes_input.value = 0
    dashboard.on_start(None)
    assert dashboard.sim is None
    assert "⚠️" in dashboard.export_message.object


def test_invalid_area_prevents_start():
    reset_inputs()
    dashboard.area_input.value = -1
    dashboard.on_start(None)
    assert dashboard.sim is None
    assert "⚠️" in dashboard.export_message.object


@pytest.mark.parametrize(
    "module,name,adr_node,adr_server",
    [
        (dashboard.adr_standard_1, "ADR 1", True, True),
        (dashboard.adr_2, "ADR 2", True, True),
        (dashboard.adr_3, "ADR 3", True, True),
        (dashboard.explora_sf, "Explora-SF", False, True),
        (dashboard.explora_at, "Explora-AT", False, True),
        (dashboard.adr_lite, "ADR-Lite", False, True),
        (dashboard.adr_max, "ADR-Max", False, True),
        (dashboard.radr, "R-ADR", False, True),
        (dashboard.adr_ml, "ML-ADR", False, True),
    ],
)
def test_select_adr_updates_checkboxes(module, name, adr_node, adr_server):
    reset_inputs()
    dashboard.select_adr(module, name, adr_node=adr_node, adr_server=adr_server)
    assert dashboard.adr_node_checkbox.value is adr_node
    assert dashboard.adr_server_checkbox.value is adr_server
    assert name in dashboard.adr_active_badge.object
