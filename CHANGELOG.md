# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Changed
- Significantly increased channel degradation in `adr_standard_1` for simulator validation.
- Send interval distribution now follows a strict exponential law and timestamps are only postponed when a transmission is still ongoing.

## [5.0] - 2025-07-24
### Added
- Complete rewrite of the LoRa network simulator in Python.
- Command-line interface and interactive dashboard.
- FastAPI REST and WebSocket API.
- Advanced propagation models with fading, mobility and obstacle support.
- LoRaWAN implementation with ADR logic, classes B and C, and AES-128 security.
- CSV export and detailed metrics.
- Unit tests with pytest and analysis scripts.
