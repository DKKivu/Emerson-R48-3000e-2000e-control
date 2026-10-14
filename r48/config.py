"""Immutable application configuration."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    title: str = "Emerson / Vertiv R48 Controller"
    width: int = 1120
    height: int = 940

    serial_port: str = "COM3"
    serial_baud: int = 2_000_000
    can_bitrate: int = 125_000

    poll_interval_ms: int = 1000
    keepalive_ms: int = 10_000
    age_refresh_ms: int = 500
    stale_after_s: float = 5.0
    gui_interval_ms: int = 50
    max_events_per_cycle: int = 200
    max_log_lines: int = 1200
    scan_spacing_ms: int = 90