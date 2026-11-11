from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Reading:
    temperature_c: float
    humidity_pct: float


class SensorError(RuntimeError):
    pass


class DHT11Sensor:
    """Read a DHT11 on a Raspberry Pi BCM pin (default GPIO 23)."""

    def __init__(self, gpio_pin: int = 23) -> None:
        self.gpio_pin = gpio_pin
        self._device = None
        self._init_device()

    def _init_device(self) -> None:
        try:
            import board
            import adafruit_dht
        except ImportError as exc:
            raise SensorError(
                "The DHT11 driver is not installed, so indoor temperature and humidity "
                "cannot be read. On the Raspberry Pi, install adafruit-circuitpython-dht "
                "and Adafruit-Blinka. "
                f"The data pin is GPIO {self.gpio_pin}; change it with collector.gpio_pin "
                "in config.climate.toml."
            ) from exc

        pin = getattr(board, f"D{self.gpio_pin}", None)
        if pin is None:
            raise SensorError(
                f"GPIO {self.gpio_pin} is not available for the DHT11. "
                "Set collector.gpio_pin in config.climate.toml to the BCM pin the data wire uses."
            )
        # use_pulseio=False is recommended on Raspberry Pi Linux.
        self._device = adafruit_dht.DHT11(pin, use_pulseio=False)

    def read(self) -> Reading:
        assert self._device is not None
        try:
            temperature_c = self._device.temperature
            humidity = self._device.humidity
        except RuntimeError as exc:
            # DHT sensors fail individual reads often; the collector skips that sample.
            raise SensorError(f"The DHT11 read failed: {exc}") from exc

        if temperature_c is None or humidity is None:
            raise SensorError(
                "The DHT11 returned an empty reading. Check the wiring and power to the sensor."
            )
        return Reading(float(temperature_c), float(humidity))

    def close(self) -> None:
        if self._device is not None:
            try:
                self._device.exit()
            except Exception:  # noqa: BLE001
                logger.debug("DHT exit failed", exc_info=True)
            self._device = None


def create_sensor(*, gpio_pin: int) -> DHT11Sensor:
    logger.info("Using DHT11 on GPIO %s", gpio_pin)
    return DHT11Sensor(gpio_pin=gpio_pin)


def band_status(
    temperature_c: float,
    humidity_pct: float,
    temp_min: float,
    temp_max: float,
    humidity_min: float,
    humidity_max: float,
) -> dict[str, bool | str]:
    temp_ok = temp_min <= temperature_c <= temp_max
    humidity_ok = humidity_min <= humidity_pct <= humidity_max
    if temp_ok and humidity_ok:
        overall = "in_band"
    else:
        overall = "out_of_band"
    return {
        "temperature_in_band": temp_ok,
        "humidity_in_band": humidity_ok,
        "overall": overall,
    }
