"""Base entity of the Candy dryer integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CandyDryerCoordinator
from .protocol import DryerStatus


class CandyDryerEntity(CoordinatorEntity[CandyDryerCoordinator]):
    """Entity of the dryer device, unavailable while it is switched off."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: CandyDryerCoordinator, description: EntityDescription
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Candy",
            model="Simply-Fi tumble dryer",
            name=entry.title,
        )

    @property
    def status(self) -> DryerStatus | None:
        """Current status, None while the dryer is switched off."""
        return self.coordinator.data.status if self.coordinator.data else None

    @property
    def available(self) -> bool:
        """Available while the dryer answers."""
        return super().available and self.status is not None
