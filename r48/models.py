"""Immutable data models shared across the domain and the UI."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CANFrame:
    arbitration_id: int
    data: bytes
    extended: bool = True
    remote: bool = False


@dataclass(frozen=True)
class TelemetryValue:
    property_id: int
    name: str
    unit: str
    value: float
    raw: bytes
    received_at: float
    known: bool
    source_address: Optional[int] = None