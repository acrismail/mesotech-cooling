"""Kapalı devre termal maket — Pi yokken dashboardun canlı kalması için."""

from __future__ import annotations

import math
import time


class PlantSim:
    def __init__(self):
        self.t_in = 62.0
        self.t_out = 28.0
        self.t_amb = 22.0
        self.level = 78.0
        self.blockage = 1.0
        self.dirt = 1.0
        self.sensor_fail = False
        self.pump = 0.0
        self.fan = 0.0
        self.t0 = time.time()

    def set_actuators(self, pump: float, fan: float) -> None:
        self.pump = max(0.0, min(100.0, pump))
        self.fan = max(0.0, min(100.0, fan))

    def inject(self, kind: str) -> None:
        if kind == "none":
            self.blockage = 1.0
            self.dirt = 1.0
            self.sensor_fail = False
        elif kind == "dirty":
            self.dirt = 0.35
        elif kind == "blockage":
            self.blockage = 0.08
        elif kind == "sensor":
            self.sensor_fail = True

    def step(self, dt: float = 0.5) -> dict:
        elapsed = time.time() - self.t0
        self.t_amb = 21.0 + 3.0 * math.sin(elapsed / 90.0)
        flow_eff = (self.pump / 100.0) * self.blockage * (1.0 if self.level > 15 else 0.02)
        cool_eff = (self.fan / 100.0) * self.dirt * 0.055
        mix = 0.045 * flow_eff
        self.t_in += dt * (0.085 * (68.0 - self.t_out) - mix * (self.t_in - self.t_out))
        self.t_out += dt * (
            mix * (self.t_in - self.t_out)
            - cool_eff * (self.t_out - self.t_amb)
            - 0.004 * (self.t_out - self.t_amb)
        )
        self.t_in = max(self.t_amb + 2.0, min(85.0, self.t_in))
        self.t_out = max(self.t_amb - 1.0, min(80.0, self.t_out))
        if self.blockage < 0.2:
            self.level = max(8.0, self.level - dt * 0.4)
        flow = 0.0 if self.level < 15 else (self.pump / 100.0) * 18.0 * self.blockage
        power = 42.0 + 1.15 * self.pump + 0.95 * self.fan
        t_in = None if self.sensor_fail else self.t_in
        t_out = None if self.sensor_fail else self.t_out
        return {
            "temp_in": t_in,
            "temp_out": t_out,
            "t_amb": self.t_amb,
            "flow_rate": flow,
            "level": self.level,
            "power_w": power,
        }
