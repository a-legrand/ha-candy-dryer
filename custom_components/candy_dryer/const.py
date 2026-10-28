"""Constants for the Candy dryer integration."""

from __future__ import annotations

from datetime import timedelta
import logging

DOMAIN = "candy_dryer"
LOGGER = logging.getLogger(__package__)

CONF_KEY = "key"

# Poll quickly during a cycle, slowly when the dryer is switched off: it is
# off most of the time and each failed poll only costs a short timeout.
ACTIVE_INTERVAL = timedelta(seconds=10)
IDLE_INTERVAL = timedelta(seconds=30)
OFF_INTERVAL = timedelta(seconds=60)

# Failed polls tolerated during a cycle before the dryer is reported off, so
# that a Wi-Fi hiccup does not end the cycle in Home Assistant.
ACTIVE_MISSED_POLLS = 3

# The dryer takes a few seconds to report a cycle it was told to start.
POLL_QUICKLY_AFTER_COMMAND = timedelta(minutes=1)
