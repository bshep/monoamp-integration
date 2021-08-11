"""Constants for the House Audio Amplifier integration."""

DOMAIN = "mono_amp"

MAX_VOLUME_LIMIT = 80

PROP_MAP = {"VO": "volume", "BL": "balance", "BS": "bass", "TR": "treble"}
PROP_MAP_INV = {v: k for k, v in PROP_MAP.items()}

PROP_MAX = {"VO": int(38 * (MAX_VOLUME_LIMIT / 100)), "BL": 20, "BS": 14, "TR": 14}
