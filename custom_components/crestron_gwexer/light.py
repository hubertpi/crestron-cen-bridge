"""Cove on/off only; state comes from gateway feedback."""
from homeassistant.components.light import LightEntity, ColorMode
from homeassistant.exceptions import HomeAssistantError

from .entity import GatewayEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([CoveLight(entry, "cove", "Cove")])


class CoveLight(GatewayEntity, LightEntity):
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_color_mode = ColorMode.ONOFF

    @property
    def available(self):
        return self.relay.connected

    @property
    def is_on(self):
        return self.relay.cove_is_on

    async def async_turn_on(self, **kwargs):
        await self._command(True)

    async def async_turn_off(self, **kwargs):
        await self._command(False)

    async def _command(self, on):
        try:
            await self.relay.set_cove(on)
        except (OSError, RuntimeError, TimeoutError) as err:
            raise HomeAssistantError(f"Could not send Cove command: {err}") from err
