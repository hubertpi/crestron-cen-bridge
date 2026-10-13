"""Independent CEN-GWEXER capture integration."""
from homeassistant.const import Platform
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .transport import GatewayRelay

DOMAIN = "crestron_gwexer"
PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON]


async def async_setup_entry(hass, entry):
    config = {**entry.data, **entry.options}
    relay = GatewayRelay(**config, notify=lambda: async_dispatcher_send(hass, f"{DOMAIN}_{entry.entry_id}"))
    try:
        await relay.start()
    except OSError as err:
        raise ConfigEntryNotReady(f"Cannot open gateway listener: {err}") from err
    entry.runtime_data = relay
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        await relay.stop()
        raise
    entry.async_on_unload(entry.add_update_listener(async_reload))
    return True


async def async_reload(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.stop()
        return True
    return False
