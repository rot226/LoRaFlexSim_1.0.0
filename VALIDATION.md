# Validation

The LoRaFlexSim project includes a Dockerfile to reproduce the test environment.

## Build the image

```bash
docker build -t loraflexsim:test -f docker/Dockerfile .
```

## Run the test suite

```bash
docker run --rm loraflexsim:test
```

Expected output:

```
136 passed, 13 skipped in 33.47s
```

In the current environment Docker is unavailable, so the LoRaFlexSim image could not be built. Running `pytest -q` directly produced the above results.

## FLoRa equivalence test

To compare LoRaFlexSim with the native FLoRa implementation for path loss, RSSI and PER, first build the C++ library:

```bash
scripts/build_flora_cpp.sh
```

Then run the dedicated test:

```bash
pytest tests/test_flora_equivalence.py
```

The test checks several distances, spreading factors and bandwidths against the FLoRa binary.

## FLoRa reference trace comparison

LoRaFlexSim also embeds a lightweight suite that replays reference traces
derived from the original FLoRa formulas (RSSI/SNR, capture effect and ADR
decisions). The traces are defined in `loraflexsim/tests/reference_traces.py`
and are compared against the simulator through parameterised tests located in
`loraflexsim/tests/test_flora_trace_alignment.py`.

To execute the comparison locally:

```bash
pytest loraflexsim/tests/test_flora_trace_alignment.py
```

All tolerances default to ±0.6 dB. They can be relaxed for investigations by
setting the `FLORA_TRACE_TOLERANCE` environment variable before running
`pytest`, for example `FLORA_TRACE_TOLERANCE=1.0 pytest ...`.
