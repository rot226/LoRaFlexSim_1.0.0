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
