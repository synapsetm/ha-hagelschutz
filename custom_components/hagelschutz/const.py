"""Constants for the Hagelschutz integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "hagelschutz"

CONF_DEVICE_ID: Final = "device_id"
CONF_HWTYPE_ID: Final = "hwtype_id"

API_BASE: Final = "https://meteo.netitservices.com/api/v1"

# The hail forecast is recalculated every 5 minutes; the VKF interface
# specification prescribes a poll interval of 120 seconds. Not configurable.
UPDATE_INTERVAL: Final = timedelta(seconds=120)

# Must stay well below UPDATE_INTERVAL so requests cannot pile up.
REQUEST_TIMEOUT: Final = 30

# Rate limit for the errorLogs endpoint, so a permanent fault cannot spam it.
ERROR_REPORT_INTERVAL: Final = timedelta(minutes=15)

STATE_NO_HAIL: Final = 0
STATE_HAIL: Final = 1
STATE_TEST_ALARM: Final = 2

MANUFACTURER: Final = "VKF/VKG"
MODEL: Final = "Hagelschutz – einfach automatisch"
CONFIGURATION_URL: Final = "https://meteo.netitservices.com"

# The interface description calls the field "MAC-Adresse (deviceID)" but requires
# a 12-character identifier, so the usual MAC separators have to go.
DEVICE_ID_SEPARATORS: Final = ":-. "
DEVICE_ID_LENGTH: Final = 12
