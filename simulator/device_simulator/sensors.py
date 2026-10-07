"""Simple, repeatable sensor simulation with plausible room readings."""

from __future__ import annotations

import random


class NormalSensorSimulator:
    """Generate gently varying DHT11 readings and occasional PIR motion events."""

    def __init__(self, rng: random.Random | None = None) -> None:
        self._rng = rng or random.Random()
        self._temperature = self._rng.uniform(23.0, 29.0)
        self._humidity = self._rng.uniform(40.0, 65.0)
        self._motion = False

    def read(self) -> dict[str, float | bool]:
        """Return the next normal set of sensor readings."""
        self._temperature = min(32.0, max(18.0, self._temperature + self._rng.uniform(-0.4, 0.4)))
        self._humidity = min(80.0, max(30.0, self._humidity + self._rng.uniform(-1.5, 1.5)))

        # Motion is usually absent; brief events make the PIR output look realistic.
        if self._motion:
            self._motion = self._rng.random() < 0.25
        else:
            self._motion = self._rng.random() < 0.12

        return {
            "temperature": round(self._temperature, 1),
            "humidity": round(self._humidity, 1),
            "motion": self._motion,
        }
