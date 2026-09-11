"""MesoTech Cooling sunucusu.

Flask varsa onu kullanır; yoksa standart kütüphane HTTP + JSON.
Dashboard Socket.IO yoksa /api/system/status ile yoklama yapar.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import config
from anomaly_detector import AnomalyDetector
from pump_controller import HybridPumpController
from sensor_manager import SensorManager

os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("logs/system.log"), logging.StreamHandler()],
)
logger = logging.getLogger("mesotech")

sensors = SensorManager()
pump = HybridPumpController()
anomaly = AnomalyDetector()

system_state = {
    "running": True,
    "manual_override": False,
    "target_delta_t": config.PID_SETPOINT_TOUT,
    "manual_pump_speed": 50.0,
    "manual_fan_speed": 40.0,
    "alarm_triggered": False,
    "emergency_stop": False,
    "start_time": datetime.now().isoformat(),
    "fault": "none",
}
system_data: dict = {}
_lock = threading.Lock()
_water = 0.0
_energy_kwh = 0.0
ROOT = Path(__file__).resolve().parent


def _critical(msgs: list[str]) -> bool:
    blob = " ".join(msgs).upper()
    return any(k in blob for k in config.CRITICAL_KEYWORDS)


def control_loop() -> None:
    logger.info("Kontrol döngüsü başladı")
    global _water, _energy_kwh
    while True:
        try:
            with _lock:
                emergency = system_state["emergency_stop"]
                running = system_state["running"]
                manual = system_state["manual_override"]
                man_pump = system_state["manual_pump_speed"]
                man_fan = system_state["manual_fan_speed"]
            last_pump = float(system_data.get("pump_speed") or 0)
            last_fan = float(system_data.get("fan_speed") or 0)
            raw = sensors.get_all_data(last_pump, last_fan)
            t_in, t_out = raw.get("temp_in"), raw.get("temp_out")
            flow = float(raw.get("flow_rate") or 0.0)
            level = float(raw.get("level") or 70.0)

            if emergency or not running:
                pump.stop()
                p_speed, f_speed = 0.0, 0.0
            elif manual:
                p_speed = pump.set_speed_manual(man_pump, man_fan)
                f_speed = pump.fan_speed
            else:
                p_speed, f_speed = pump.update(t_in, t_out, flow, raw.get("t_amb"))

            msgs = anomaly.detect(t_in, t_out, flow, p_speed, level)
            if _critical(msgs):
                with _lock:
                    system_state["alarm_triggered"] = True
                    system_state["running"] = False
                    system_state["emergency_stop"] = True
                pump.stop()
                p_speed, f_speed = 0.0, 0.0
                msgs.append("SİSTEM GÜVENLİ MODA ALINDI")
                logger.critical("Alarm: %s", "; ".join(msgs))

            power = float(raw.get("power_w") or (42 + 1.15 * p_speed + 0.95 * f_speed))
            if running and not emergency:
                _water += (config.TAP_L_PER_H / 3600.0) * config.UPDATE_INTERVAL
                _energy_kwh += max(0.0, config.CHILLER_REF_W - power) * config.UPDATE_INTERVAL / 3.6e6

            payload = {
                "temp_in": 0.0 if t_in is None else t_in,
                "temp_out": 0.0 if t_out is None else t_out,
                "sensor_ok": t_in is not None and t_out is not None,
                "delta_t": 0.0 if t_in is None or t_out is None else t_in - t_out,
                "flow_rate": flow,
                "pump_speed": p_speed,
                "fan_speed": f_speed,
                "power_w": power,
                "level": level,
                "water_saved_l": _water,
                "energy_saved_kwh": _energy_kwh,
                "co2_saved_kg": _energy_kwh * config.CO2_KG_PER_KWH,
                "anomalies": msgs,
                "system_state": dict(system_state),
                "timestamp": datetime.now().isoformat(),
            }
            with _lock:
                system_data.clear()
                system_data.update(payload)
            time.sleep(config.UPDATE_INTERVAL)
        except Exception:
            logger.exception("Döngü hatası")
            time.sleep(2)


def handle_control(data: dict) -> tuple[dict, int]:
    action = data.get("action")
    if not action:
        return {"status": "error", "message": "action yok"}, 400
    if action == "emergency_stop":
        with _lock:
            system_state["emergency_stop"] = True
            system_state["running"] = False
        pump.stop()
        return {"status": "success", "message": "Sistem durdu"}, 200
    if action == "reset_system":
        with _lock:
            system_state["emergency_stop"] = False
            system_state["running"] = True
            system_state["alarm_triggered"] = False
            system_state["manual_override"] = False
            system_state["fault"] = "none"
        sensors.plant.inject("none")
        pump.integral = 0.0
        pump.prev_meas = None
        return {"status": "success", "message": "Sistem sıfırlandı"}, 200
    if action == "set_target_delta":
        target = max(18.0, min(35.0, float(data.get("value", 25.0))))
        with _lock:
            system_state["target_delta_t"] = target
        pump.set_target_out(target)
        return {"status": "success", "message": f"Hedef çıkış {target:.1f}°C"}, 200
    if action == "set_manual_mode":
        enabled = bool(data.get("enabled", False))
        speed = max(0.0, min(100.0, float(data.get("speed", 50.0))))
        with _lock:
            system_state["manual_override"] = enabled
            system_state["manual_pump_speed"] = speed
        if enabled:
            pump.set_speed_manual(speed)
        return {"status": "success", "message": f"Manuel {'açık' if enabled else 'kapalı'}"}, 200
    if action == "set_manual_speed":
        if not system_state["manual_override"]:
            return {"status": "error", "message": "Önce manuel mod"}, 400
        speed = max(0.0, min(100.0, float(data.get("speed", 50.0))))
        with _lock:
            system_state["manual_pump_speed"] = speed
        pump.set_speed_manual(speed)
        return {"status": "success", "message": f"Pompa {speed:.0f}%"}, 200
    if action == "set_fault":
        kind = str(data.get("value", "none"))
        if kind not in {"none", "dirty", "blockage", "sensor"}:
            return {"status": "error", "message": "geçersiz arıza"}, 400
        sensors.plant.inject(kind)
        with _lock:
            system_state["fault"] = kind
        return {"status": "success", "message": f"Arıza: {kind}"}, 200
    return {"status": "error", "message": "geçersiz action"}, 400


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        logger.info("%s - %s", self.address_string(), fmt % args)

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            html = (ROOT / "templates" / "dashboard.html").read_bytes()
            self._send(200, html, "text/html; charset=utf-8")
            return
        if path == "/api/system/status":
            with _lock:
                payload = json.dumps(system_data).encode()
            self._send(200, payload, "application/json")
            return
        if path == "/api/system/stats":
            start = datetime.fromisoformat(system_state["start_time"])
            body = json.dumps(
                {
                    "model_stats": anomaly.get_stats(),
                    "system_state": system_state,
                    "uptime": (datetime.now() - start).total_seconds(),
                }
            ).encode()
            self._send(200, body, "application/json")
            return
        self._send(404, b'{"error":"not found"}', "application/json")

    def do_POST(self):
        path = urlparse(self.path).path
        if path != "/api/system/control":
            self._send(404, b'{"error":"not found"}', "application/json")
            return
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b"{}"
        try:
            data = json.loads(raw.decode() or "{}")
        except json.JSONDecodeError:
            self._send(400, b'{"status":"error","message":"json"}', "application/json")
            return
        body, code = handle_control(data)
        self._send(code, json.dumps(body).encode(), "application/json")


def run_stdlib() -> None:
    httpd = ThreadingHTTPServer((config.WEB_HOST, config.WEB_PORT), Handler)
    logger.info("HTTP %s:%s (stdlib)", config.WEB_HOST, config.WEB_PORT)
    httpd.serve_forever()


def run_flask() -> None:
    from flask import Flask, jsonify, render_template, request

    app = Flask(__name__, template_folder=str(ROOT / "templates"))

    @app.route("/")
    def home():
        return render_template("dashboard.html")

    @app.route("/api/system/status")
    def status():
        return jsonify(system_data)

    @app.route("/api/system/stats")
    def stats():
        start = datetime.fromisoformat(system_state["start_time"])
        return jsonify(
            {
                "model_stats": anomaly.get_stats(),
                "system_state": system_state,
                "uptime": (datetime.now() - start).total_seconds(),
            }
        )

    @app.route("/api/system/control", methods=["POST"])
    def control():
        body, code = handle_control(request.get_json(silent=True) or {})
        return jsonify(body), code

    app.run(host=config.WEB_HOST, port=config.WEB_PORT, debug=False, use_reloader=False)


if __name__ == "__main__":
    t = threading.Thread(target=control_loop, daemon=True)
    t.start()
    time.sleep(0.2)
    try:
        try:
            import flask  # noqa: F401

            run_flask()
        except ImportError:
            run_stdlib()
    except KeyboardInterrupt:
        logger.info("Durduruldu")
    finally:
        pump.cleanup()
        sensors.cleanup()
