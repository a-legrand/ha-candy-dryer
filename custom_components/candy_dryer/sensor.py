"""Sensors of the Candy dryer."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import CandyDryerConfigEntry
from .entity import CandyDryerEntity
from .programs import DIAL_POSITIONS
from .protocol import DRY_LEVELS, MACHINE_STATES, PHASES, DryerStatus


@dataclass(frozen=True, kw_only=True)
class CandyDryerSensorDescription(SensorEntityDescription):
    """Sensor reading one value of the status."""

    value_fn: Callable[[DryerStatus], Any]


def _end_time(status: DryerStatus) -> datetime | None:
    if not status.is_active:
        return None
    end = dt_util.now() + timedelta(minutes=status.remaining_minutes)
    # Whole minutes, so the state does not change on every poll.
    return end.replace(second=0, microsecond=0)


SENSORS = (
    CandyDryerSensorDescription(
        key="program",
        translation_key="program",
        device_class=SensorDeviceClass.ENUM,
        options=list(dict.fromkeys(DIAL_POSITIONS.values())),
        value_fn=lambda status: DIAL_POSITIONS.get(status.program),
    ),
    CandyDryerSensorDescription(
        key="phase",
        translation_key="phase",
        device_class=SensorDeviceClass.ENUM,
        options=sorted(set(PHASES.values())),
        value_fn=lambda status: status.phase,
    ),
    CandyDryerSensorDescription(
        key="remaining_time",
        translation_key="remaining_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda status: status.remaining_minutes,
    ),
    CandyDryerSensorDescription(
        key="end_time",
        translation_key="end_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_end_time,
    ),
    CandyDryerSensorDescription(
        key="dry_level",
        translation_key="dry_level",
        device_class=SensorDeviceClass.ENUM,
        options=list(DRY_LEVELS.values()),
        value_fn=lambda status: status.dry_level,
    ),
    CandyDryerSensorDescription(
        key="error_code",
        translation_key="error_code",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda status: status.error_code,
    ),
)

STATE = SensorEntityDescription(
    key="state",
    translation_key="state",
    device_class=SensorDeviceClass.ENUM,
    options=["off", *sorted(set(MACHINE_STATES.values()))],
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CandyDryerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            CandyDryerStateSensor(coordinator, STATE),
            *(CandyDryerSensor(coordinator, description) for description in SENSORS),
        ]
    )


class CandyDryerSensor(CandyDryerEntity, SensorEntity):
    """Sensor reading one value of the status."""

    entity_description: CandyDryerSensorDescription

    @property
    def native_value(self) -> Any:
        """Value from the status."""
        return self.entity_description.value_fn(self.status) if self.status else None


class CandyDryerStateSensor(CandyDryerEntity, SensorEntity):
    """Machine state, "off" when the dryer does not answer."""

    @property
    def available(self) -> bool:
        """Stays available while the dryer is switched off."""
        return self.coordinator.data is not None

    @property
    def native_value(self) -> str | None:
        """Machine state."""
        return self.status.machine_state if self.status else "off"
