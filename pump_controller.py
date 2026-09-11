"""Soğutma PID: ölçüm > hedef ise PWM artar. simple_pid kullanılmaz."""

from __future__ import annotations

import threading

import config
import hardware


def _select_gains(t_amb: float | None, delta_t: float) -> tuple[float, float, float, float]:
    amb = t_amb if t_amb is not None else 24.0
    if amb >= 34 or delta_t >= 35:
        return 5.2, 0.10, 1.1, 25.0
    if amb >= 28 or delta_t >= 25:
        return 4.4, 0.13, 0.9, 12.0
    return config.PID_KP, config.PID_KI, config.PID_KD, 0.0


class HybridPumpController:
    def __init__(self):
        hardware.setup()
        self.pump_pwm = hardware.PwmOut(config.PWM_PIN, config.PWM_FREQUENCY)
        self.fan_pwm = hardware.PwmOut(config.FAN_PWM_PIN, config.PWM_FREQUENCY)
        hardware.set_motor_dir(True)
        self.lock = threading.Lock()
        self.integral = 0.0
        self.prev_meas: float | None = None
        self.pump_speed = 0.0
        self.fan_speed = 0.0
        self.setpoint = config.PID_SETPOINT_TOUT
        print(
            f"PumpController hazır. Hedef T_out={self.setpoint}°C  "
            f"Kp={config.PID_KP} Ki={config.PID_KI} Kd={config.PID_KD}"
        )

    def update(self, temp_in, temp_out, flow_rate, t_amb=None, dt=None):
        if temp_out is None:
            return self.pump_speed, self.fan_speed
        dt = dt or config.UPDATE_INTERVAL
        delta_t = (temp_in - temp_out) if temp_in is not None else 20.0
        kp, ki, kd, fan_bias = _select_gains(t_amb, delta_t)
        error = temp_out - self.setpoint  # soğutma
        with self.lock:
            p = kp * error
            self.integral += error * dt
            self.integral = max(-config.PID_I_LIMIT, min(config.PID_I_LIMIT, self.integral))
            i = ki * self.integral
            d = 0.0 if self.prev_meas is None else -kd * (temp_out - self.prev_meas) / max(dt, 1e-3)
            self.prev_meas = temp_out
            raw = max(config.PID_OUTPUT_MIN, min(config.PID_OUTPUT_MAX, p + i + d))
        if error > 0.5:
            pump = min(100.0, max(15.0, raw))
            fan = max(10.0, min(100.0, 0.7 * raw + fan_bias))
        elif raw <= 0:
            pump, fan = 0.0, 0.0
        else:
            pump = raw
            fan = min(100.0, max(0.0, 0.7 * raw + fan_bias))
        if flow_rate is not None and flow_rate < config.ANOMALY_THRESHOLDS["flow_min"] and pump > 20:
            pump, fan = 0.0, 40.0
        self._apply(pump, fan)
        return self.pump_speed, self.fan_speed

    def _apply(self, pump: float, fan: float) -> None:
        self.pump_speed = pump
        self.fan_speed = fan
        self.pump_pwm.set_duty(pump)
        self.fan_pwm.set_duty(fan)

    def set_speed_manual(self, pump: float, fan: float | None = None):
        pump = max(0.0, min(100.0, pump))
        fan = self.fan_speed if fan is None else max(0.0, min(100.0, fan))
        self._apply(pump, fan)
        return pump

    def get_speed(self) -> float:
        return self.pump_speed

    def set_target_out(self, target: float) -> float:
        self.setpoint = max(18.0, min(35.0, target))
        return self.setpoint

    def stop(self) -> None:
        self._apply(0.0, 0.0)

    def cleanup(self) -> None:
        self.pump_pwm.stop()
        self.fan_pwm.stop()
        hardware.cleanup()
        print("PWM kapatıldı")
