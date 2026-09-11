"""Kural + RobustZ / IsolationForest. Yalnızca normal örneklerle eğitilir."""

from __future__ import annotations

import threading

import numpy as np

import config

try:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler

    HAS_SK = True
except Exception:
    HAS_SK = False


class _RobustZ:
    def __init__(self):
        self.median = None
        self.mad = None

    def fit(self, X: np.ndarray) -> None:
        self.median = np.median(X, axis=0)
        self.mad = np.median(np.abs(X - self.median), axis=0) + 1e-6

    def score(self, x: np.ndarray) -> float:
        if self.median is None:
            return 0.0
        z = np.abs(x - self.median) / self.mad
        return float(-z.mean())


class AnomalyDetector:
    def __init__(self):
        self.lock = threading.Lock()
        self.normal: list[list[float]] = []
        self.trained = False
        self.thresholds = config.ANOMALY_THRESHOLDS
        self.prev_pump = 0.0
        self.backend = "sklearn" if HAS_SK else "robustz"
        if HAS_SK:
            self.scaler = StandardScaler()
            self.model = IsolationForest(n_estimators=120, contamination=0.03, random_state=42)
        else:
            self.scaler = None
            self.model = _RobustZ()
        self.threshold = -2.2
        print(f"AnomalyDetector hazır ({self.backend})")

    def _physics(self, t_in, t_out, flow, pump, level) -> list[str]:
        msgs = []
        th = self.thresholds
        if t_in is None or t_out is None:
            return ["KRİTİK SENSÖR: sıcaklık okunamadı"]
        delta = t_in - t_out
        if flow < th["flow_min"] and pump > 25:
            msgs.append(f"DÜŞÜK AKIŞ: {flow:.1f} L/dk (TIKANIKLIK veya SUSUZ)")
        if flow > th["flow_max"]:
            msgs.append(f"Yüksek akış: {flow:.1f} L/dk (olası kaçak)")
        if t_in > th["temp_max"] or t_out > th["t_out_critical"]:
            msgs.append(f"AŞIRI SICAKLIK: in={t_in:.1f} out={t_out:.1f}")
        if delta > th["delta_t_max"] and t_out > 28:
            msgs.append(f"Yüksek ΔT: {delta:.1f}°C (yetersiz soğutma)")
        if level is not None and level < th["level_min"]:
            msgs.append("KRİTİK düşük su seviyesi")
        return msgs

    def _fit_if_ready(self) -> None:
        if len(self.normal) < 80:
            return
        X = np.asarray(self.normal[-400:], dtype=float)
        if HAS_SK:
            Xs = self.scaler.fit_transform(X)
            self.model.fit(Xs)
            scores = self.model.decision_function(Xs)
            self.threshold = float(np.percentile(scores, 3))
        else:
            self.model.fit(X)
            scores = np.array([self.model.score(r) for r in X])
            self.threshold = float(np.percentile(scores, 3))
        self.trained = True

    def detect(self, temp_in, temp_out, flow_rate, pump_speed, level=70.0) -> list[str]:
        msgs = self._physics(temp_in, temp_out, flow_rate, pump_speed, level)
        physics_hit = bool(msgs)
        if temp_in is None or temp_out is None:
            self.prev_pump = pump_speed
            return msgs
        delta = temp_in - temp_out
        feat = [temp_in, temp_out, delta, flow_rate, pump_speed]
        with self.lock:
            if self.trained:
                try:
                    if HAS_SK:
                        score = float(self.model.decision_function(self.scaler.transform([feat]))[0])
                    else:
                        score = self.model.score(np.asarray(feat, dtype=float))
                    model_hit = score < self.threshold
                    if model_hit and physics_hit:
                        msgs.append("Model + fizik: sapma doğrulandı")
                    elif model_hit:
                        msgs.append("Model sapması (sarı — fizik onaylamadı)")
                except Exception as exc:
                    print(f"AI skor hatası: {exc}")
            if not physics_hit:
                self.normal.append(feat)
                if len(self.normal) > 800:
                    self.normal = self.normal[-400:]
                if len(self.normal) % 80 == 0:
                    self._fit_if_ready()
        self.prev_pump = pump_speed
        return msgs

    def get_stats(self) -> dict:
        return {
            "trained": self.trained,
            "buffer_size": len(self.normal),
            "backend": self.backend,
            "thresholds": self.thresholds,
        }
