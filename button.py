"""Button platform — start / stop / pause / resume charging commands."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CMD_PAUSE, CMD_RESUME, CMD_START, CMD_STOP, DOMAIN


@dataclass(frozen=True)
class EaseeButtonDescription(ButtonEntityDescription):
    cmd: str = ""


BUTTONS: tuple[EaseeButtonDescription, ...] = (
    EaseeButtonDescription(
        key="start",
        name="Start Charging",
        icon="mdi:play-circle",
        cmd=CMD_START,
    ),
    EaseeButtonDescription(
        key="stop",
        name="Stop Charging",
        icon="mdi:stop-circle",
        cmd=CMD_STOP,
    ),
    EaseeButtonDescription(
        key="pause",
        name="Pause Charging",
        icon="mdi:pause-circle",
        cmd=CMD_PAUSE,
    ),
    EaseeButtonDescription(
        key="resume",
        name="Resume Charging",
        icon="mdi:play-pause",
        cmd=CMD_RESUME,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coord = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [EaseeCommandButton(coord, entry, desc) for desc in BUTTONS]
    )


class EaseeCommandButton(CoordinatorEntity, ButtonEntity):
    """Sends a one-shot command to the Easee charger."""

    entity_description: EaseeButtonDescription

    def __init__(self, coordinator, entry: ConfigEntry, description: EaseeButtonDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._charger_id: str = entry.data["charger_id"]
        self._attr_unique_id = f"{self._charger_id}_{description.key}"
        self._attr_name = description.name
        self._attr_icon = description.icon

    async def async_press(self) -> None:
        await self.coordinator.client.send_command(
            self._charger_id, self.entity_description.cmd
        )
        await self.coordinator.async_request_refresh()
