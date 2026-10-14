"""OKOK / Chipsea BLE advertisement parser.

Port of the Android ``OkOkParser``. Android stores the first two advertisement
bytes as a little-endian company id, and the payload starts after that.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScaleReading:
    weight_kg: float
    impedance_ohm: float | None
    unit: str
    decimals: int
    stable: bool
    scale_mac: str | None
    protocol: str
    raw_hex: str


def parse_manufacturer_data(company_id: int, data: bytes) -> ScaleReading | None:
    if not data:
        return None
    first = data[0] & 0xFF
    if company_id == 0x20CA:
        return _parse_v20(data)
    if company_id == 0x11CA:
        return _parse_v11(data)
    if company_id == 0xF0FF:
        return _parse_vf0(data)
    if first == 0xC0 and len(data) >= 9:
        return parse_c0_payload(data[2:])
    if first == 0xCA:
        return parse_ca(data)
    if (company_id & 0xFF) == 0xC0:
        return parse_c0_payload(data)
    if (company_id & 0xFF) == 0xCA:
        full = bytes([0xCA, (company_id >> 8) & 0xFF]) + data
        return parse_ca(full)
    return None


def parse_c0_payload(data: bytes) -> ScaleReading | None:
    """C0 payload after the C0 byte and sequence byte were consumed as company id.

    [0..1] weight BE, [2..3] impedance BE, [4..5] product, [6] property, [7..12] MAC.
    Property: bit0 stable, bits1-2 divisor, bits3-4 unit. 0x24 = kg measuring, 0x25 = kg locked.
    """
    if len(data) < 7:
        return None
    prop = data[6] & 0xFF
    divider = {1: 1.0, 2: 100.0}.get((prop >> 1) & 0x03, 10.0)
    unit_code = (prop >> 3) & 0x03
    weight_raw = _u16be(data, 0)
    if unit_code == 0:
        weight_kg = weight_raw / divider
    elif unit_code == 1:
        weight_kg = weight_raw / divider / 2.0
    elif unit_code == 2:
        weight_kg = (weight_raw / divider) * 0.45359237
    elif unit_code == 3:
        stones = data[0] & 0xFF
        pounds = (data[1] & 0xFF) / divider
        weight_kg = stones * 6.35029318 + pounds * 0.45359237
    else:
        return None
    if weight_kg <= 0.0 or weight_kg > 300.0:
        return None
    impedance_raw = _u16be(data, 2)
    if unit_code == 1:
        unit, decimals = "jin", 1
    elif unit_code == 2:
        unit, decimals = "lb", 1
    elif unit_code == 3:
        unit, decimals = "st", 1
    else:
        unit, decimals = "kg", 2 if divider >= 100.0 else 1
    return ScaleReading(
        weight_kg=weight_kg,
        impedance_ohm=None if impedance_raw == 0 else impedance_raw / 10.0,
        unit=unit,
        decimals=decimals,
        stable=(prop & 0x01) != 0,
        scale_mac=_format_mac(data, 7) if len(data) >= 13 else None,
        protocol="C0",
        raw_hex=data.hex(),
    )


def parse_ca(data: bytes) -> ScaleReading | None:
    if len(data) < 8 or (data[0] & 0xFF) != 0xCA:
        return None
    version = data[1] & 0xFF
    if len(data) >= 14:
        return _parse_ca_long(data, version)
    return _parse_ca_short(data, version)


def reading_from_advertisement(
    address: str | None,
    manufacturer_data: dict[int, bytes],
    service_data: dict[str, bytes] | None = None,
) -> ScaleReading | None:
    """Pick the first OKOK reading out of one advertisement."""
    for company_id, payload in manufacturer_data.items():
        if not payload:
            continue
        reading = parse_manufacturer_data(int(company_id), bytes(payload))
        if reading is None:
            continue
        if address and not reading.scale_mac:
            reading = ScaleReading(
                weight_kg=reading.weight_kg,
                impedance_ohm=reading.impedance_ohm,
                unit=reading.unit,
                decimals=reading.decimals,
                stable=reading.stable,
                scale_mac=address,
                protocol=reading.protocol,
                raw_hex=reading.raw_hex,
            )
        return reading
    for payload in (service_data or {}).values():
        if not payload:
            continue
        magic = payload[0] & 0xFF
        if magic not in (0xC0, 0xCA):
            continue
        reading = parse_manufacturer_data(magic, bytes(payload))
        if reading is not None:
            return reading
    return None


def _parse_v20(data: bytes) -> ScaleReading | None:
    if len(data) < 13:
        return None
    flags = data[6] & 0xFF
    checksum = 0x20
    for i in range(12):
        checksum ^= data[i] & 0xFF
    if (data[12] & 0xFF) != (checksum & 0xFF):
        return None
    divider = 100.0 if (flags & 0x04) else 10.0
    weight_kg = _u16be(data, 8) / divider
    if weight_kg <= 0.0 or weight_kg > 300.0:
        return None
    impedance_raw = _u16be(data, 10)
    return ScaleReading(
        weight_kg=weight_kg,
        impedance_ohm=None if impedance_raw == 0 else impedance_raw / 10.0,
        unit="kg",
        decimals=2 if divider >= 100.0 else 1,
        stable=(flags & 0x01) != 0,
        scale_mac=_format_mac(data, len(data) - 6) if len(data) >= 19 else None,
        protocol="CA-V20",
        raw_hex=data.hex(),
    )


def _parse_v11(data: bytes) -> ScaleReading | None:
    if len(data) < 17:
        return None
    checksum = 0xCA ^ 0x11
    for i in range(16):
        checksum ^= data[i] & 0xFF
    if (data[16] & 0xFF) != (checksum & 0xFF):
        return None
    props = data[9] & 0xFF
    divider = {1: 1.0, 2: 100.0}.get((props >> 1) & 0x03, 10.0)
    weight_raw = _u16be(data, 3)
    unit_code = (props >> 3) & 0x03
    if unit_code == 0:
        weight_kg = weight_raw / divider
    elif unit_code == 1:
        weight_kg = weight_raw / divider / 2.0
    elif unit_code == 2:
        weight_kg = (weight_raw / divider) * 0.45359237
    else:
        return None
    if weight_kg <= 0.0 or weight_kg > 300.0:
        return None
    return ScaleReading(
        weight_kg=weight_kg,
        impedance_ohm=None,
        unit="kg",
        decimals=2 if divider >= 100.0 else 1,
        stable=True,
        scale_mac=None,
        protocol="CA-V11",
        raw_hex=data.hex(),
    )


def _parse_vf0(data: bytes) -> ScaleReading | None:
    if len(data) < 4:
        return None
    weight_kg = _u16le(data, 2) / 10.0
    if weight_kg <= 0.0 or weight_kg > 300.0:
        return None
    return ScaleReading(
        weight_kg=weight_kg,
        impedance_ohm=None,
        unit="kg",
        decimals=1,
        stable=True,
        scale_mac=None,
        protocol="VF0",
        raw_hex=data.hex(),
    )


def _parse_ca_long(data: bytes, version: int) -> ScaleReading | None:
    locked = (data[3] & 0xFF) == 0x01
    if version == 0x11 and len(data) >= 12:
        weight_raw = _u16be(data, 5)
        imp_raw = _u16be(data, 9) if len(data) >= 12 else 0
        stable = (data[3] & 0xFF) == 0x01
    elif len(data) >= 14:
        weight_raw = 0
        imp_raw = 0
        stable = locked
        for idx in (5, 6, 9, 10):
            if idx + 1 >= len(data):
                continue
            candidate = _u16be(data, idx)
            if 200 <= candidate <= 3000:
                weight_raw = candidate
                if idx + 3 < len(data):
                    imp_raw = _u16be(data, idx + 2)
                break
        if weight_raw == 0 and len(data) >= 12:
            weight_raw = _u16be(data, len(data) - 11)
            imp_raw = _u16be(data, len(data) - 9)
    else:
        weight_raw, imp_raw, stable = 0, 0, locked
    if not 200 <= weight_raw <= 3000:
        return None
    return ScaleReading(
        weight_kg=weight_raw / 10.0,
        impedance_ohm=None if imp_raw == 0 else imp_raw / 10.0,
        unit="kg",
        decimals=1,
        stable=stable,
        scale_mac=_format_mac(data, len(data) - 6) if len(data) >= 20 else None,
        protocol=f"CA-0x{version:x}",
        raw_hex=data.hex(),
    )


def _parse_ca_short(data: bytes, version: int) -> ScaleReading | None:
    if len(data) < 8:
        return None
    locked = ((data[3] & 0xFF) if len(data) > 3 else 0) == 0x01
    weight_raw = _u16be(data, min(5, len(data) - 2))
    if not 200 <= weight_raw <= 3000:
        return None
    return ScaleReading(
        weight_kg=weight_raw / 10.0,
        impedance_ohm=None,
        unit="kg",
        decimals=1,
        stable=locked,
        scale_mac=None,
        protocol=f"CA-0x{version:x}",
        raw_hex=data.hex(),
    )


def _u16be(data: bytes, index: int) -> int:
    if index + 1 >= len(data):
        return 0
    return ((data[index] & 0xFF) << 8) | (data[index + 1] & 0xFF)


def _u16le(data: bytes, index: int) -> int:
    if index + 1 >= len(data):
        return 0
    return (data[index] & 0xFF) | ((data[index + 1] & 0xFF) << 8)


def _format_mac(data: bytes, start: int) -> str | None:
    if start + 5 >= len(data):
        return None
    return ":".join(f"{data[start + i] & 0xFF:02X}" for i in range(6))
