"""Pure wire-format codecs.

R48Protocol        - Emerson / Vertiv R48 message layout (big-endian floats).
WaveshareProtocol  - Waveshare USB-CAN-A serial framing.

Neither class performs I/O; both are pure functions wrapped in a class so
they can be tested and mocked in isolation (SRP).
"""
from __future__ import annotations

import math
import struct
import time
from typing import Optional

from .exceptions import ProtocolError, ValidationError
from .models import CANFrame, TelemetryValue


# ---------------------------------------------------------------
# R48 rectifier protocol
# ---------------------------------------------------------------

class R48Protocol:
    DEFAULT_TX_ID = 0x0607FF83
    DEFAULT_READ_ID = 0x06000783
    DEFAULT_CONTROL_ID = 0x06080783

    ADDR_MASK = 0x0000FF00
    ADDR_SHIFT = 8

    MSG_RESPONSE_PROPERTY = 0x41

    VOLTAGE_MIN = 41.0
    VOLTAGE_MAX = 58.5
    CURRENT_MIN = 5.5
    CURRENT_MAX = 62.5
    RATED_CURRENT = 62.5
    RATED_FRACTION = 1.21

    CMD_VOLT_ONLINE = 0x21
    CMD_VOLT_PERM = 0x24
    CMD_CURR_ONLINE = 0x22
    CMD_CURR_PERM = 0x19

    PROP_VOUT = 0x01
    PROP_IOUT = 0x02
    PROP_ILIMIT = 0x03
    PROP_TEMP = 0x04
    PROP_VIN = 0x05

    PROPERTY_NAMES = {
        PROP_VOUT: ("Output voltage", "V"),
        PROP_IOUT: ("Output current", "A"),
        PROP_ILIMIT: ("Current limit", "A"),
        PROP_TEMP: ("Temperature", "\u00b0C"),
        PROP_VIN: ("Input voltage", "V"),
    }

    READ_ALL = bytes.fromhex("00 F0 00 80 46 A5 34 00")

    def __init__(self, target_address: Optional[int] = None) -> None:
        self._target: Optional[int] = None
        self.set_target_address(target_address)

    # ---- target address ---------------------------------------

    def set_target_address(self, address: Optional[int]) -> None:
        if address is None:
            self._target = None
            return
        if not 0 <= address <= 0xFF:
            raise ValidationError("PSU address must be 0x00..0xFF")
        self._target = address

    @property
    def target_address(self) -> Optional[int]:
        return self._target

    def _substitute(self, base_id: int) -> int:
        if self._target is None:
            return base_id
        return (base_id & ~self.ADDR_MASK) | (self._target << self.ADDR_SHIFT)

    @property
    def TX_ID(self) -> int:
        return self._substitute(self.DEFAULT_TX_ID)

    @property
    def READ_ID(self) -> int:
        return self._substitute(self.DEFAULT_READ_ID)

    @property
    def CONTROL_ID(self) -> int:
        return self._substitute(self.DEFAULT_CONTROL_ID)

    # ---- float helpers ----------------------------------------

    @staticmethod
    def pack_float_be(value: float) -> bytes:
        return struct.pack(">f", value)

    @staticmethod
    def unpack_float_be(data: bytes) -> float:
        if len(data) != 4:
            raise ProtocolError("A float requires exactly 4 bytes")
        return struct.unpack(">f", data)[0]

    @staticmethod
    def _validate_finite(value: float, name: str) -> None:
        if not math.isfinite(value):
            raise ValidationError(f"{name} must be a finite number")

    # ---- current conversion -----------------------------------

    @classmethod
    def amps_to_fraction(cls, current_a: float) -> float:
        return (current_a / cls.RATED_CURRENT) * cls.RATED_FRACTION

    @classmethod
    def fraction_to_amps(cls, fraction: float) -> float:
        return (fraction / cls.RATED_FRACTION) * cls.RATED_CURRENT

    # ---- source address discovery -----------------------------

    @staticmethod
    def extract_source_address(frame: CANFrame) -> Optional[int]:
        rid = frame.arbitration_id
        if (rid >> 24) & 0xFF != 0x06:
            return None
        if (rid >> 16) & 0xFF != 0x0F:
            return None
        addr_byte = (rid >> 8) & 0xFF
        if not (addr_byte & 0x80):
            return None
        return addr_byte & 0x7F

    # ---- requests ---------------------------------------------

    def build_read_all(self) -> CANFrame:
        return CANFrame(self.READ_ID, self.READ_ALL)

    def build_read_property(self, property_id: int) -> CANFrame:
        if not 0 <= property_id <= 0xFF:
            raise ValidationError("Property id must be 0..255")
        payload = bytes((0x01, 0xF0, 0x00, property_id, 0, 0, 0, 0))
        return CANFrame(self.READ_ID, payload)

    # ---- setpoints --------------------------------------------

    def build_set_voltage(self, voltage: float, permanent: bool = False) -> CANFrame:
        self._validate_finite(voltage, "Voltage")
        if not self.VOLTAGE_MIN <= voltage <= self.VOLTAGE_MAX:
            raise ValidationError(
                f"Voltage must be between {self.VOLTAGE_MIN} and {self.VOLTAGE_MAX} V"
            )
        command = self.CMD_VOLT_PERM if permanent else self.CMD_VOLT_ONLINE
        payload = bytes((0x03, 0xF0, 0x00, command)) + self.pack_float_be(voltage)
        return CANFrame(self.TX_ID, payload)

    def build_set_current(self, current: float, permanent: bool = False) -> CANFrame:
        self._validate_finite(current, "Current")
        if not self.CURRENT_MIN <= current <= self.CURRENT_MAX:
            raise ValidationError(
                f"Current must be between {self.CURRENT_MIN} and {self.CURRENT_MAX} A"
            )
        fraction = self.amps_to_fraction(current)
        command = self.CMD_CURR_PERM if permanent else self.CMD_CURR_ONLINE
        payload = bytes((0x03, 0xF0, 0x00, command)) + self.pack_float_be(fraction)
        return CANFrame(self.TX_ID, payload)

    # ---- fan / LED / DC / AC ----------------------------------

    def build_control(
        self,
        fan_full: bool = False,
        flash_led: bool = False,
        dc_off: bool = False,
        ac_off: bool = False,
    ) -> CANFrame:
        ctrl = (
            (int(dc_off) << 7)
            | (int(fan_full) << 4)
            | (int(flash_led) << 3)
            | (int(ac_off) << 2)
            | 1
        )
        payload = bytes((0x00, 0xF0, ctrl, 0x80, 0, 0, 0, 0))
        return CANFrame(self.CONTROL_ID, payload)

    def build_control_raw_byte(self, ctrl_byte: int) -> CANFrame:
        payload = bytes((0x00, 0xF0, ctrl_byte & 0xFF, 0x80, 0, 0, 0, 0))
        return CANFrame(self.CONTROL_ID, payload)

    # ---- responses --------------------------------------------

    def decode_telemetry(self, frame: CANFrame) -> Optional[TelemetryValue]:
        data = frame.data
        if len(data) != 8 or data[0] != self.MSG_RESPONSE_PROPERTY:
            return None
        property_id = data[3]
        try:
            value = self.unpack_float_be(data[4:8])
        except ProtocolError:
            return None
        if not math.isfinite(value):
            return None

        definition = self.PROPERTY_NAMES.get(property_id)
        known = definition is not None
        name, unit = definition if known else (f"Property 0x{property_id:02X}", "")

        return TelemetryValue(
            property_id=property_id,
            name=name,
            unit=unit,
            value=value,
            raw=bytes(data),
            received_at=time.time(),
            known=known,
            source_address=self.extract_source_address(frame),
        )


# ---------------------------------------------------------------
# Waveshare USB-CAN-A serial framing
# ---------------------------------------------------------------

class WaveshareProtocol:
    HEADER = 0xAA
    FOOTER = 0x55
    TYPE_BASE = 0xC0

    EXTENDED_FLAG = 0x20
    REMOTE_FLAG = 0x10

    @classmethod
    def encode(cls, frame: CANFrame) -> bytes:
        max_id = 0x1FFFFFFF if frame.extended else 0x7FF

        if not 0 <= frame.arbitration_id <= max_id:
            raise ValueError("CAN ID is out of range")
        if len(frame.data) > 8:
            raise ValueError("Classic CAN payload cannot exceed 8 bytes")
        if frame.remote and frame.data:
            raise ValueError("Remote frame cannot contain data")

        frame_type = cls.TYPE_BASE | len(frame.data)
        if frame.extended:
            frame_type |= cls.EXTENDED_FLAG
        if frame.remote:
            frame_type |= cls.REMOTE_FLAG

        id_size = 4 if frame.extended else 2
        can_id = frame.arbitration_id.to_bytes(id_size, "little")

        return (
            bytes((cls.HEADER, frame_type))
            + can_id
            + frame.data
            + bytes((cls.FOOTER,))
        )

    @classmethod
    def decode_buffer(cls, buffer: bytearray) -> list:
        frames = []

        while buffer:
            try:
                start = buffer.index(cls.HEADER)
            except ValueError:
                buffer.clear()
                break

            if start:
                del buffer[:start]

            if len(buffer) < 2:
                break

            frame_type = buffer[1]
            if (frame_type & 0xC0) != cls.TYPE_BASE:
                del buffer[0]
                continue

            extended = bool(frame_type & cls.EXTENDED_FLAG)
            remote = bool(frame_type & cls.REMOTE_FLAG)
            dlc = frame_type & 0x0F

            if dlc > 8 or (remote and dlc != 0):
                del buffer[0]
                continue

            id_size = 4 if extended else 2
            frame_size = 2 + id_size + dlc + 1

            if len(buffer) < frame_size:
                break

            if buffer[frame_size - 1] != cls.FOOTER:
                del buffer[0]
                continue

            can_id = int.from_bytes(buffer[2:2 + id_size], "little")
            data_start = 2 + id_size
            data = bytes(buffer[data_start:data_start + dlc])

            frames.append(CANFrame(can_id, data, extended, remote))
            del buffer[:frame_size]

        return frames

    @staticmethod
    def build_configuration(
        bitrate: int = 125_000,
        extended: bool = True,
        mode: int = 0,
    ) -> bytes:
        bitrate_codes = {
            1_000_000: 0x01, 800_000: 0x02, 500_000: 0x03, 400_000: 0x04,
            250_000: 0x05, 200_000: 0x06, 125_000: 0x07, 100_000: 0x08,
            50_000: 0x09, 20_000: 0x0A, 10_000: 0x0B, 5_000: 0x0C,
        }

        if bitrate not in bitrate_codes:
            raise ValueError("Unsupported CAN bitrate")
        if mode not in (0, 1, 2, 3):
            raise ValueError("Invalid CAN operating mode")

        packet = bytearray(20)
        packet[0:5] = bytes((
            0xAA, 0x55, 0x12,
            bitrate_codes[bitrate],
            0x02 if extended else 0x01,
        ))
        packet[5:13] = bytes(8)
        packet[13] = mode
        packet[14] = 0x00
        packet[15:19] = bytes(4)
        packet[19] = sum(packet[2:19]) & 0xFF

        return bytes(packet)