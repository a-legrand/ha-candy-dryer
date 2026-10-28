"""Binary sensors of the Candy dryer."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import CandyDryerConfigEntry
from .entity import CandyDryerEntity
from .protocol import DryerStatus


@dataclass(frozen=True, kw_only=True)
class CandyDryerBinarySensorDescription(BinarySensorEntityDescription):
    """Binary sensor reading one flag of the status."""

    is_on_fn: Callable[[DryerStatus], bool]


BINARY_SENSORS = (
    CandyDryerBinarySensorDescription(
        key="door",
        device_class=BinarySensorDeviceClass.DOOR,
        is_on_fn=lambda status: not status.door_closed,
    ),
    CandyDryerBinarySensorDescription(
        key="clean_filter",
        translation_key="clean_filter",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=lambda status: status.clean_filter,
    ),
    CandyDryerBinarySensorDescription(
        key="water_tank_full",
        translation_key="water_tank_full",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=lambda status: status.water_tank_full,
    ),
    CandyDryerBinarySensorDescription(
        key="remote_control",
        translation_key="remote_control",
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda status: status.remote_control,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CandyDryerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        CandyDryerBinarySensor(coordinator, description)
        for description in BINARY_SENSORS
    )


class CandyDryerBinarySensor(CandyDryerEntity, BinarySensorEntity):
    """Binary sensor reading one flag of the status."""

    entity_description: CandyDryerBinarySensorDescription

    @property
    def is_on(self) -> bool | None:
        """Flag from the status."""
        return self.entity_description.is_on_fn(self.status) if self.status else None
