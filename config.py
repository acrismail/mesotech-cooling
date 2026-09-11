"""MesoTech Cooling — merkezi ayarlar."""

# Donanım: SIMULATION bu makinede varsayılan. Raspberry Pi'de HARDWARE yapın.
MODE = "SIMULATION"

# DS18B20 kimlikleri (1-Wire). Boşsa ilk iki sensör sırayla atanır — riskli.
TEMP_IN_ID = ""
TEMP_OUT_ID = ""

FLOW_SENSOR_PIN = 17
FLOW_PULSES_PER_LITER = 450.0

PWM_PIN = 18
INA_PIN = 22
INB_PIN = 23
FAN_PWM_PIN = 13
PWM_FREQUENCY = 1000

PID_KP = 2.5
PID_KI = 0.18
PID_KD = 0.08
PID_SETPOINT_TOUT = 25.0  # hedef çıkış sıcaklığı °C
PID_OUTPUT_MIN = 0.0
PID_OUTPUT_MAX = 100.0
PID_I_LIMIT = 40.0

ANOMALY_THRESHOLDS = {
    "flow_min": 0.3,
    "flow_max": 120.0,
    "delta_t_min": 0.5,
    "delta_t_max": 15.0,
    "temp_max": 80.0,
    "t_out_boost": 32.0,
    "t_out_critical": 40.0,
    "level_min": 15.0,
    "pump_speed_change": 40.0,
}

UPDATE_INTERVAL = 0.5
LOG_LEVEL = "INFO"
WEB_HOST = "0.0.0.0"
WEB_PORT = 5000

CRITICAL_KEYWORDS = ("DÜŞÜK AKIŞ", "AŞIRI SICAKLIK", "SUSUZ", "TIKANIKLIK", "KRİTİK", "SENSÖR")

CHILLER_REF_W = 1300.0
TAP_L_PER_H = 1000.0
CO2_KG_PER_KWH = 0.48
