"""GPIO soyutlaması. RPi yoksa veya MODE=SIMULATION ise no-op."""

from __future__ import annotations

import config

try:
    import RPi.GPIO as GPIO  # type: ignore

    HAS_GPIO = True
except Exception:
    HAS_GPIO = False
    GPIO = None


_initialized = False


def available() -> bool:
    return HAS_GPIO and config.MODE.upper() == "HARDWARE"


def setup() -> None:
    global _initialized
    if not available() or _initialized:
        return
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(config.PWM_PIN, GPIO.OUT)
    GPIO.setup(config.INA_PIN, GPIO.OUT)
    GPIO.setup(config.INB_PIN, GPIO.OUT)
    GPIO.setup(config.FAN_PWM_PIN, GPIO.OUT)
    GPIO.setup(config.FLOW_SENSOR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    _initialized = True


def cleanup() -> None:
    global _initialized
    if HAS_GPIO and _initialized:
        try:
            GPIO.cleanup()
        except Exception:
            pass
    _initialized = False


class PwmOut:
    def __init__(self, pin: int, freq: int):
        self.pin = pin
        self.duty = 0.0
        self._pwm = None
        if available():
            setup()
            self._pwm = GPIO.PWM(pin, freq)
            self._pwm.start(0)

    def set_duty(self, duty: float) -> None:
        self.duty = max(0.0, min(100.0, float(duty)))
        if self._pwm is not None:
            self._pwm.ChangeDutyCycle(self.duty)

    def stop(self) -> None:
        self.set_duty(0)
        if self._pwm is not None:
            try:
                self._pwm.stop()
            except Exception:
                pass


def set_motor_dir(forward: bool = True) -> None:
    if not available():
        return
    GPIO.output(config.INA_PIN, GPIO.HIGH if forward else GPIO.LOW)
    GPIO.output(config.INB_PIN, GPIO.LOW if forward else GPIO.HIGH)
