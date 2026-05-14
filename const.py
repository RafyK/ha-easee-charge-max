"""Constants for the Easee Charge MAX integration."""

DOMAIN = "easee_charge_max"

# ── Easee Cloud API ──────────────────────────────────────────────────────────
API_BASE = "https://api.easee.com/api"
API_LOGIN = f"{API_BASE}/accounts/login"
API_REFRESH = f"{API_BASE}/accounts/refresh_token"
API_CHARGERS = f"{API_BASE}/chargers"
API_CHARGER_STATE   = f"{API_BASE}/chargers/{{charger_id}}/state"
API_CHARGER_CONFIG  = f"{API_BASE}/chargers/{{charger_id}}/config"
API_CHARGER_SITE    = f"{API_BASE}/chargers/{{charger_id}}/site"
API_CHARGER_SETTINGS = f"{API_BASE}/chargers/{{charger_id}}/settings"
API_CHARGER_CMD     = f"{API_BASE}/chargers/{{charger_id}}/commands/{{cmd}}"
API_CIRCUIT_SETTINGS = f"{API_BASE}/sites/{{site_id}}/circuits/{{circuit_id}}/settings"

# ── Configuration keys ────────────────────────────────────────────────────────
CONF_CHARGER_ID = "charger_id"

# ── Poll interval ─────────────────────────────────────────────────────────────
DEFAULT_SCAN_INTERVAL = 30  # seconds

# ── Current limits ────────────────────────────────────────────────────────────
MIN_CURRENT = 6    # A  (IEC 61851 minimum)
MAX_CURRENT = 32   # A  (Charge MAX rated max)

# ── Easee command strings ─────────────────────────────────────────────────────
CMD_START   = "start_charging"
CMD_STOP    = "stop_charging"
CMD_PAUSE   = "pause_charging"
CMD_RESUME  = "resume_charging"

# ── Charger op modes (chargerOpMode field in state) ───────────────────────────
OP_MODE_OFFLINE           = 0
OP_MODE_DISCONNECTED      = 1
OP_MODE_AWAITING_START    = 2
OP_MODE_CHARGING          = 3
OP_MODE_COMPLETED         = 4
OP_MODE_ERROR             = 5
OP_MODE_READY_TO_CHARGE   = 6
OP_MODE_AWAITING_AUTH     = 7
OP_MODE_DEAUTHENTICATING  = 8

OP_MODE_LABEL = {
    OP_MODE_OFFLINE:          "Offline",
    OP_MODE_DISCONNECTED:     "Disconnected",
    OP_MODE_AWAITING_START:   "Awaiting Start",
    OP_MODE_CHARGING:         "Charging",
    OP_MODE_COMPLETED:        "Completed",
    OP_MODE_ERROR:            "Error",
    OP_MODE_READY_TO_CHARGE:  "Ready to Charge",
    OP_MODE_AWAITING_AUTH:    "Awaiting Authentication",
    OP_MODE_DEAUTHENTICATING: "Deauthenticating",
}

# ── Phase mode values (phaseMode in charger settings) ────────────────────────
PHASE_MODE_1P   = 1   # lock to 1-phase
PHASE_MODE_AUTO = 2   # auto / 3-phase
PHASE_MODE_3P   = 3   # explicit 3-phase (some firmware maps this to AUTO)

PHASE_MODE_LABEL = {
    PHASE_MODE_1P:   "1-phase",
    PHASE_MODE_AUTO: "Auto (3-phase)",
}
PHASE_MODE_FROM_LABEL = {v: k for k, v in PHASE_MODE_LABEL.items()}


# Partial mapping of Easee "reasonForNoCurrent" codes to human-readable labels.
REASON_FOR_NO_CURRENT_LABEL: dict[int, str] = {
    0: "No reason",
    1: "Waiting for vehicle",
    2: "Vehicle disconnected",
    3: "RCD / ground fault",
    4: "Pilot signal error",
    5: "Charger disabled",
    6: "Overtemperature",
    7: "Phase loss / imbalance",
}
