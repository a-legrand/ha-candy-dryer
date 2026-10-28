"""Polling of the dryer status."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .client import CandyConnectionError, CandyDryerClient
from .const import (
    ACTIVE_INTERVAL,
    ACTIVE_MISSED_POLLS,
    DOMAIN,
    IDLE_INTERVAL,
    LOGGER,
    OFF_INTERVAL,
    POLL_QUICKLY_AFTER_COMMAND,
)
from .programs import DEFAULT_PROGRAM, Program
from .protocol import DryerStatus, InvalidStatusError

type CandyDryerConfigEntry = ConfigEntry[CandyDryerCoordinator]


@dataclass(frozen=True)
class DryerData:
    """Last poll result: status is None when the dryer is switched off."""

    status: DryerStatus | None

    @property
    def online(self) -> bool:
        """The dryer answered."""
        return self.status is not None


class CandyDryerCoordinator(DataUpdateCoordinator[DryerData]):
    """Polls the dryer, treating an unreachable dryer as switched off."""

    config_entry: CandyDryerConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: CandyDryerConfigEntry,
        client: CandyDryerClient,
    ) -> None:
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=IDLE_INTERVAL,
        )
        self.client = client
        # Program and duration chosen in Home Assistant, sent by the Start
        # button. No duration means the program default.
        self.selected_program: Program = DEFAULT_PROGRAM
        self.selected_time_level: int | None = None
        # Delay of the next start only: back to an immediate start after it.
        self.selected_delay_minutes = 0
        self._missed_polls = 0
        self._poll_quickly_until = dt_util.utcnow()

    async def _async_update_data(self) -> DryerData:
        try:
            status = await self.client.read_status()
        except CandyConnectionError as err:
            return self._unreachable(err)
        except InvalidStatusError as err:
            raise UpdateFailed(f"Unexpected status: {err}") from err

        if self.data is not None and not self.data.online:
            LOGGER.info("Dryer is back online")
        self._missed_polls = 0
        quick = status.is_active or dt_util.utcnow() < self._poll_quickly_until
        self.update_interval = ACTIVE_INTERVAL if quick else IDLE_INTERVAL
        return DryerData(status)

    def _unreachable(self, err: CandyConnectionError) -> DryerData:
        self._missed_polls += 1
        previous = self.data
        if (
            previous is not None
            and previous.status is not None
            and previous.status.is_active
            and self._missed_polls < ACTIVE_MISSED_POLLS
        ):
            LOGGER.debug("Dryer missed a poll during a cycle: %s", err)
            return previous

        if previous is None or previous.online:
            LOGGER.info("Dryer unreachable, considered switched off: %s", err)
        self.update_interval = OFF_INTERVAL
        return DryerData(None)

    @property
    def time_level_to_send(self) -> int | None:
        """Chosen duration, if the chosen program accepts it."""
        level = self.selected_time_level
        return level if level in self.selected_program.time_levels else None

    def poll_quickly(self) -> None:
        """Poll at the active rate for a while after a command.

        The dryer still reports itself idle a few seconds after a start.
        """
        self._poll_quickly_until = dt_util.utcnow() + POLL_QUICKLY_AFTER_COMMAND
        self.update_interval = ACTIVE_INTERVAL
