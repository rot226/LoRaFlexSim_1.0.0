from loraflexsim.launcher.simulator import Simulator
from loraflexsim.launcher import radr, adr_standard_1


def test_radr_reacts_faster_than_standard():
    # High SNR should immediately decrease SF with radr
    sim_r = Simulator(num_nodes=1, num_gateways=1, adr_node=True, adr_server=True, seed=1)
    radr.apply(sim_r)
    node_r = sim_r.nodes[0]
    ns_r = sim_r.network_server
    initial_sf_r = node_r.sf
    ns_r.evaluate_adr(node_r, snr=ns_r.snr_high_threshold + 5)
    assert node_r.sf < initial_sf_r

    # Standard ADR requires history; single evaluation keeps SF unchanged
    sim_s = Simulator(num_nodes=1, num_gateways=1, adr_node=True, adr_server=True, seed=1)
    adr_standard_1.apply(sim_s)
    node_s = sim_s.nodes[0]
    ns_s = sim_s.network_server
    initial_sf_s = node_s.sf
    ns_s.evaluate_adr(node_s, snr=20)
    assert node_s.sf == initial_sf_s

    # Low SNR causes immediate SF increase with radr
    node_r.sf = 7
    ns_r.evaluate_adr(node_r, snr=ns_r.snr_low_threshold - 5)
    assert node_r.sf > 7

    node_s.sf = 7
    ns_s.evaluate_adr(node_s, snr=-20)
    assert node_s.sf == 7
