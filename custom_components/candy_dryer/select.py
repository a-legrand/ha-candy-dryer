"""Choice of the program started by the Start / Pause button, its duration and delay."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .coordinator import CandyDryerConfigEntry
from .entity import CandyDryerEntity
from .programs import DELAYS, PROGRAMS, PROGRAMS_BY_KEY, TIME_LEVEL_MINUTES

DEFAULT_DURATION = "default"
DURATION_OPTIONS = {
    f"min_{minutes}": level for level, minutes in TIME_LEVEL_MINUTES.items()
}
DURATION_KEYS = {level: option for option, level in DURATION_OPTIONS.items()}

PROGRAM_CHOICE = SelectEntityDescription(
    key="program_choice",
    translation_key="program_choice",
    options=[program.key for program in PROGRAMS],
)
DURATION_CHOICE = SelectEntityDescription(
    key="duration_choice", translation_key="duration_choice"
)
DELAY_CHOICE = SelectEntityDescription(
    key="delay_choice", translation_key="delay_choice", options=list(DELAYS)
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CandyDryerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the program, duration and delay choices."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            CandyDryerProgramSelect(coordinator, PROGRAM_CHOICE),
            CandyDryerDurationSelect(coordinator, DURATION_CHOICE),
            CandyDryerDelaySelect(coordinator, DELAY_CHOICE),
        ]
    )


class CandyDryerChoiceSelect(CandyDryerEntity, SelectEntity, RestoreEntity):
    """Choice kept across restarts, which can be made while the dryer is off."""

    @property
    def available(self) -> bool:
        """A choice can be made before switching the dryer on."""
        return self.coordinator.data is not None

    async def async_added_to_hass(self) -> None:
        """Restore the last choice."""
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None:
            self._restore(last.state)

    def _restore(self, option: str) -> None:
        raise NotImplementedError


class CandyDryerProgramSelect(CandyDryerChoiceSelect):
    """Program to start: standard programs of the dial, then extra ones."""

    @property
    def current_option(self) -> str:
        """Chosen program."""
        return self.coordinator.selected_program.key

    def _restore(self, option: str) -> None:
        if option in PROGRAMS_BY_KEY:
            self.coordinator.selected_program = PROGRAMS_BY_KEY[option]

    async def async_select_option(self, option: str) -> None:
        """Choose a program, and drop a duration it does not accept."""
        program = PROGRAMS_BY_KEY[option]
        self.coordinator.selected_program = program
        if self.coordinator.selected_time_level not in program.time_levels:
            self.coordinator.selected_time_level = None
        # The duration choices depend on the program.
        self.coordinator.async_update_listeners()


class CandyDryerDurationSelect(CandyDryerChoiceSelect):
    """Duration of a timed program; other programs only have their default."""

    @property
    def options(self) -> list[str]:
        """Durations accepted by the chosen program."""
        levels = self.coordinator.selected_program.time_levels
        return [DEFAULT_DURATION, *(DURATION_KEYS[level] for level in levels)]

    @property
    def current_option(self) -> str:
        """Chosen duration."""
        level = self.coordinator.time_level_to_send
        return DURATION_KEYS[level] if level else DEFAULT_DURATION

    def _restore(self, option: str) -> None:
        # Checked against the program when used: both choices are restored
        # in no particular order.
        self.coordinator.selected_time_level = DURATION_OPTIONS.get(option)

    async def async_select_option(self, option: str) -> None:
        """Choose a duration."""
        self.coordinator.selected_time_level = DURATION_OPTIONS.get(option)
        self.coordinator.async_update_listeners()


class CandyDryerDelaySelect(CandyDryerEntity, SelectEntity):
    """Delay of the next start, back to an immediate start once used.

    Not restored: a forgotten delay must not hold a later start back.
    """

    @property
    def available(self) -> bool:
        """A delay can be chosen before switching the dryer on."""
        return self.coordinator.data is not None

    @property
    def current_option(self) -> str:
        """Chosen delay."""
        minutes = self.coordinator.selected_delay_minutes
        return next(option for option, value in DELAYS.items() if value == minutes)

    async def async_select_option(self, option: str) -> None:
        """Choose the delay of the next start."""
        self.coordinator.selected_delay_minutes = DELAYS[option]
        self.async_write_ha_state()
