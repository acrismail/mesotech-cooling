"""Sıcaklık + debi. Donanım yoksa PlantSim kullanır."""

from __future__ import annotations

import threading
import time
from datetime import datetime

import config
import hardware
from plant_sim import PlantSim

try:
    from w1thermsensor import W1ThermSensor  # type: ignore

    HAS_W1 = True
except Exception:
    HAS_W1 = False


class SensorManager:
    def __init__(self, plant: PlantSim | None = None):
        self.plant = plant or PlantSim()
        self.use_hw = hardware.available() and HAS_W1
        self.temp_in_sensor = None
        self.temp_out_sensor = None
        self.flow_count = 0
        self.last_flow_time = time.time()
        self.flow_rate = 0.0
        self.flow_lock = threading.Lock()
        if self.use_hw:
            self._init_hw()
        print(f"SensorManager: {'HARDWARE' if self.use_hw else 'SIMULATION'}")

    def _init_hw(self) -> None:
        hardware.setup()
        sensors = list(W1ThermSensor.get_available_sensors())
        by_id = {s.id: s for s in sensors}
        if config.TEMP_IN_ID and config.TEMP_IN_ID in by_id:
            self.temp_in_sensor = by_id[config.TEMP_IN_ID]
        elif sensors:
            self.temp_in_sensor = sensors[0]
        if config.TEMP_OUT_ID and config.TEMP_OUT_ID in by_id:
            self.temp_out_sensor = by_id[config.TEMP_OUT_ID]
        elif len(sensors) > 1:
            self.temp_out_sensor = sensors[1]
        try:
            import RPi.GPIO as GPIO  # type: ignore

            GPIO.add_event_detect(
                config.FLOW_SENSOR_PIN,
                GPIO.RISING,
                callback=self._count_pulse,
                bouncetime=5,
            )
        except Exception as exc:
            print(f"Akış kesmesi kurulamadı: {exc}")

    def _count_pulse(self, _channel) -> None:
        with self.flow_lock:
            self.flow_count += 1

    def _read_hw_temps(self):
        try:
            t_in = self.temp_in_sensor.get_temperature() if self.temp_in_sensor else None
            t_out = self.temp_out_sensor.get_temperature() if self.temp_out_sensor else None
            return t_in, t_out
        except Exception as exc:
            print(f"Sıcaklık okuma hatası: {exc}")
            return None, None

    def _read_hw_flow(self) -> float:
        now = time.time()
        elapsed = now - self.last_flow_time
        with self.flow_lock:
            count = self.flow_count
            self.flow_count = 0
        if elapsed >= 0.4:
            self.flow_rate = max(0.0, (count / elapsed) * 60.0 / config.FLOW_PULSES_PER_LITER)
            self.last_flow_time = now
        return self.flow_rate

    def get_all_data(self, pump: float = 0.0, fan: float = 0.0) -> dict:
        if self.use_hw:
            t_in, t_out = self._read_hw_temps()
            flow = self._read_hw_flow()
            return {
                "temp_in": t_in,
                "temp_out": t_out,
                "t_amb": None,
                "flow_rate": flow,
                "level": 70.0,
                "power_w": 42.0 + 1.15 * pump + 0.95 * fan,
                "timestamp": datetime.now().isoformat(),
            }
        self.plant.set_actuators(pump, fan)
        data = self.plant.step(config.UPDATE_INTERVAL)
        data["timestamp"] = datetime.now().isoformat()
        return data

    def cleanup(self) -> None:
        return
