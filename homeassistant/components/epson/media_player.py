"""Support for Epson projector."""
from __future__ import annotations

import logging

from epson_projector import Projector
from epson_projector.const import (
    BACK,
    BUSY,
    CMODE,
    CMODE_LIST,
    CMODE_LIST_SET,
    DEFAULT_SOURCES,
    EPSON_CODES,
    FAST,
    INV_SOURCES,
    MUTE,
    PAUSE,
    PLAY,
    POWER,
    SOURCE,
    SOURCE_LIST,
    STATE_UNAVAILABLE as EPSON_STATE_UNAVAILABLE,
    TURN_OFF,
    TURN_ON,
    VOL_DOWN,
    VOL_UP,
    VOLUME,
)
import voluptuous as vol

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry

from .const import ATTR_CMODE, DOMAIN, SERVICE_SELECT_CMODE

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Epson projector from a config entry."""
    projector: Projector = hass.data[DOMAIN][config_entry.entry_id]
    projector_entity = EpsonProjectorMediaPlayer(
        projector=projector,
        name=config_entry.title,
        unique_id=config_entry.unique_id,
        entry=config_entry,
    )
    async_add_entities([projector_entity], True)
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SELECT_CMODE,
        {vol.Required(ATTR_CMODE): vol.All(cv.string, vol.Any(*CMODE_LIST_SET))},
        SERVICE_SELECT_CMODE,
    )


class EpsonProjectorMediaPlayer(MediaPlayerEntity):
    """Representation of Epson Projector Device."""

    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
    )

    def __init__(
        self, projector: Projector, name: str, unique_id: str | None, entry: ConfigEntry
    ) -> None:
        """Initialize entity to control Epson projector."""
        self._projector = projector
        self._entry = entry
        self._attr_name = name
        self._attr_available = False
        self._cmode = None
        self._attr_source_list = list(DEFAULT_SOURCES.values())
        self._attr_unique_id = unique_id
        if unique_id:
            self._attr_device_info = DeviceInfo(
                identifiers={(DOMAIN, unique_id)},
                manufacturer="Epson",
                model="Epson",
                name="Epson projector",
                via_device=(DOMAIN, unique_id),
            )

    async def set_unique_id(self) -> bool:
        """Set unique id for projector config entry."""
        _LOGGER.debug("Setting unique_id for projector")
        if self.unique_id:
            return False
        if uid := await self._projector.get_serial_number():
            self.hass.config_entries.async_update_entry(self._entry, unique_id=uid)
            registry = async_get_entity_registry(self.hass)
            old_entity_id = registry.async_get_entity_id(
                "media_player", DOMAIN, self._entry.entry_id
            )
            if old_entity_id is not None:
                registry.async_update_entity(old_entity_id, new_unique_id=uid)
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(self._entry.entry_id)
            )
            return True
        return False

    async def async_update(self) -> None:
        """Update state of device."""
        power_state = await self._projector.get_power()
        _LOGGER.debug("Projector status: %s", power_state)
        if not power_state or power_state == EPSON_STATE_UNAVAILABLE:
            self._attr_available = False
            return
        self._attr_available = True
        if power_state == EPSON_CODES[POWER]:
            self._attr_state = STATE_ON
            if await self.set_unique_id():
                return
            self._attr_source_list = list(DEFAULT_SOURCES.values())
            cmode = await self._projector.get_property(CMODE)
            self._cmode = CMODE_LIST.get(cmode, self._cmode)
            source = await self._projector.get_property(SOURCE)
            self._attr_source = SOURCE_LIST.get(source, self._attr_source)
            if volume := await self._projector.get_property(VOLUME):
                try:
                    self._attr_volume_level = float(volume)
                except ValueError:
                    self._attr_volume_level = None
        elif power_state == BUSY:
            self._attr_state = STATE_ON
        else:
            self._attr_state = STATE_OFF

    async def async_turn_on(self) -> None:
        """Turn on epson."""
        if self.state == STATE_OFF:
            await self._projector.send_command(TURN_ON)
            self._attr_state = STATE_ON

    async def async_turn_off(self) -> None:
        """Turn off epson."""
        if self.state == STATE_ON:
            await self._projector.send_command(TURN_OFF)
            self._attr_state = STATE_OFF

    async def select_cmode(self, cmode: str) -> None:
        """Set color mode in Epson."""
        await self._projector.send_command(CMODE_LIST_SET[cmode])

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        selected_source = INV_SOURCES[source]
        await self._projector.send_command(selected_source)

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute (true) or unmute (false) sound."""
        await self._projector.send_command(MUTE)

    async def async_volume_up(self) -> None:
        """Increase volume."""
        await self._projector.send_command(VOL_UP)

    async def async_volume_down(self) -> None:
        """Decrease volume."""
        await self._projector.send_command(VOL_DOWN)

    async def async_media_play(self) -> None:
        """Play media via Epson."""
        await self._projector.send_command(PLAY)

    async def async_media_pause(self) -> None:
        """Pause media via Epson."""
        await self._projector.send_command(PAUSE)

    async def async_media_next_track(self) -> None:
        """Skip to next."""
        await self._projector.send_command(FAST)

    async def async_media_previous_track(self) -> None:
        """Skip to previous."""
        await self._projector.send_command(BACK)

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return device specific state attributes."""
        if self._cmode is None:
            return {}
        return {ATTR_CMODE: self._cmode}
