"""Buttons sending commands to the Candy dryer."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .client import CandyError
from .coordinator import CandyDryerConfigEntry, CandyDryerCoordinator
from .entity import CandyDryerEntity
from .protocol import (
    PAUSE_COMMAND,
    RESUME_COMMAND,
    DryerStatus,
    start_command,
    stop_command,
)


@dataclass(frozen=True, kw_only=True)
class CandyDryerButtonDescription(ButtonEntityDescription):
    """Button sending one command."""

    command_fn: Callable[[CandyDryerCoordinator, DryerStatus], str]
    # Whether the command makes sense now.
    allowed_fn: Callable[[CandyDryerCoordinator, DryerStatus], bool]


def _play_pause(coordinator: CandyDryerCoordinator, status: DryerStatus) -> str:
    """Like the play/pause button of the dryer and of the Simply-Fi app."""
    if status.machine_state == "running":
        return PAUSE_COMMAND
    if status.machine_state == "paused":
        return RESUME_COMMAND
    return start_command(
        coordinator.selected_program,
        coordinator.time_level_to_send,
        coordinator.selected_delay_minutes,
    )


BUTTONS = (
    CandyDryerButtonDescription(
        key="play_pause",
        translation_key="play_pause",
        command_fn=_play_pause,
        allowed_fn=lambda coordinator, status: (
            status.machine_state in ("running", "paused")
            or (
                status.door_closed
                and not status.is_active
                # After a cycle the dryer ignores remote starts until its dial
                # is turned away from the remote position and back.
                and status.machine_state != "finished"
            )
        ),
    ),
    CandyDryerButtonDescription(
        key="stop",
        translation_key="stop",
        command_fn=lambda coordinator, status: stop_command(status.program),
        allowed_fn=lambda coordinator, status: status.is_active,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CandyDryerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the buttons."""
    coordinator = entry.runtime_data
    async_add_entities(
        CandyDryerButton(coordinator, description) for description in BUTTONS
    )


class CandyDryerButton(CandyDryerEntity, ButtonEntity):
    """Button sending one command."""

    entity_description: CandyDryerButtonDescription

    @property
    def available(self) -> bool:
        """Available when remote control is on and the command applies."""
        status = self.status
        return (
            super().available
            and status is not None
            and status.remote_control
            and self.entity_description.allowed_fn(self.coordinator, status)
        )

    async def async_press(self) -> None:
        """Send the command, then refresh the status."""
        status = self.status
        if status is None:
            raise HomeAssistantError("The dryer is switched off")
        try:
            await self.coordinator.client.send(
                self.entity_description.command_fn(self.coordinator, status)
            )
        except CandyError as err:
            raise HomeAssistantError(f"Command failed: {err}") from err
        if self.entity_description.key == "play_pause" and not status.is_active:
            # A start used the delay: the next one is immediate again.
            self.coordinator.selected_delay_minutes = 0
        self.coordinator.poll_quickly()
        await self.coordinator.async_request_refresh()
