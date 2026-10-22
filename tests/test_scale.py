"""OKOK parser and morning listen-window tests. No Bluetooth adapter required."""

import unittest

from server.modules.health.okok import (
    ScaleReading,
    parse_c0_payload,
    parse_manufacturer_data,
    reading_from_advertisement,
)
from server.modules.health.scale_window import (
    ReadingHold,
    scan_requested,
    should_listen,
    should_replace_reading,
)


class ListenWindowTests(unittest.TestCase):
    def test_morning_hours_only(self):
        self.assertFalse(should_listen(hour=5, recorded_today=False))
        self.assertTrue(should_listen(hour=6, recorded_today=False))
        self.assertTrue(should_listen(hour=11, recorded_today=False))
        self.assertFalse(should_listen(hour=12, recorded_today=False))

    def test_stops_after_today_is_recorded(self):
        self.assertFalse(should_listen(hour=8, recorded_today=True))

    def test_manual_override(self):
        self.assertTrue(scan_requested(mode="on", hour=20, recorded_today=True))
        self.assertFalse(scan_requested(mode="off", hour=8, recorded_today=False))
        self.assertTrue(scan_requested(mode="auto", hour=8, recorded_today=False))
        self.assertFalse(scan_requested(mode="auto", hour=8, recorded_today=True))


def _reading(weight: float, *, stable: bool, impedance: float | None = None) -> ScaleReading:
    return ScaleReading(
        weight_kg=weight,
        impedance_ohm=impedance,
        unit="kg",
        decimals=1,
        stable=stable,
        scale_mac=None,
        protocol="C0",
        raw_hex="",
    )


class ReadingHoldTests(unittest.TestCase):
    def test_unstable_is_not_stored(self):
        hold = ReadingHold(settle_seconds=8)
        self.assertIsNone(hold.offer(_reading(74.2, stable=False), 0))
        self.assertIsNone(hold.flush())

    def test_impedance_is_stored_immediately(self):
        hold = ReadingHold(settle_seconds=8)
        stored = hold.offer(_reading(74.2, stable=True, impedance=520), 0)
        self.assertIsNotNone(stored)
        assert stored is not None
        self.assertEqual(stored.impedance_ohm, 520)

    def test_lock_without_impedance_waits(self):
        hold = ReadingHold(settle_seconds=8)
        first = _reading(74.2, stable=True)
        self.assertIsNone(hold.offer(first, 0))
        self.assertFalse(hold.due(7.9))
        self.assertTrue(hold.due(8))
        stored = hold.take()
        self.assertIsNotNone(stored)
        assert stored is not None
        self.assertAlmostEqual(stored.weight_kg, 74.2)

    def test_impedance_after_the_lock_is_stored(self):
        hold = ReadingHold(settle_seconds=8)
        self.assertIsNone(hold.offer(_reading(74.2, stable=True), 0))
        stored = hold.offer(_reading(74.2, stable=True, impedance=480), 2)
        self.assertIsNotNone(stored)
        assert stored is not None
        self.assertEqual(stored.impedance_ohm, 480)

    def test_weight_change_resets_the_wait(self):
        hold = ReadingHold(settle_seconds=8)
        self.assertIsNone(hold.offer(_reading(70.0, stable=True), 0))
        self.assertIsNone(hold.offer(_reading(74.0, stable=True), 5))
        self.assertFalse(hold.due(12))
        self.assertTrue(hold.due(13))

    def test_flush_keeps_a_lock_when_listening_stops(self):
        hold = ReadingHold(settle_seconds=8)
        self.assertIsNone(hold.offer(_reading(74.2, stable=True), 1))
        stored = hold.flush()
        self.assertIsNotNone(stored)
        self.assertIsNone(hold.flush())

    def test_same_weight_is_not_replaced_until_impedance_arrives(self):
        self.assertFalse(should_replace_reading(74.2, None, 74.2, None))
        self.assertTrue(should_replace_reading(74.2, None, 74.2, 500))
        self.assertTrue(should_replace_reading(74.2, 500, 75.0, 500))
        self.assertFalse(should_replace_reading(74.2, 500, 74.25, 510))


class OkokParserTests(unittest.TestCase):
    def test_c0_locked_kg(self):
        # 75.0 kg, divider 10, kg, stable. Company id low byte is C0.
        payload = bytes([0x02, 0xEE, 0x00, 0x00, 0x00, 0x00, 0x01])
        reading = parse_manufacturer_data(0x00C0, payload)
        self.assertIsNotNone(reading)
        assert reading is not None
        self.assertAlmostEqual(reading.weight_kg, 75.0)
        self.assertTrue(reading.stable)
        self.assertEqual(reading.unit, "kg")
        self.assertEqual(reading.protocol, "C0")

    def test_unstable_c0_is_not_stable(self):
        # 0x24 = kg measuring (not locked): bit0 clear, divisor 10, unit kg.
        payload = bytes([0x02, 0xEE, 0x00, 0x00, 0x00, 0x00, 0x24])
        reading = parse_c0_payload(payload)
        self.assertIsNotNone(reading)
        assert reading is not None
        self.assertFalse(reading.stable)

    def test_advertisement_uses_device_address_when_mac_missing(self):
        payload = bytes([0x02, 0xEE, 0x00, 0x00, 0x00, 0x00, 0x01])
        reading = reading_from_advertisement(
            "AA:BB:CC:DD:EE:FF",
            {0x00C0: payload},
        )
        self.assertIsNotNone(reading)
        assert reading is not None
        self.assertEqual(reading.scale_mac, "AA:BB:CC:DD:EE:FF")

    def test_rejects_zero_weight(self):
        payload = bytes([0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01])
        self.assertIsNone(parse_c0_payload(payload))


if __name__ == "__main__":
    unittest.main()
