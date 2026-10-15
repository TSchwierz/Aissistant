"""OKOK parser and morning listen-window tests. No Bluetooth adapter required."""

import unittest

from server.modules.health.okok import parse_c0_payload, parse_manufacturer_data, reading_from_advertisement
from server.modules.health.scale_window import scan_requested, should_listen


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
