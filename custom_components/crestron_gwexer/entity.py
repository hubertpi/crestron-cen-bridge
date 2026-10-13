"""Entity lifecycle shared by gateway diagnostics and capture controls."""
from homeassistant.helpers.entity import Entity, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect

DOMAIN = "crestron_gwexer"


class GatewayEntity(Entity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry, key, name):
        self.entry = entry
        self.relay = entry.runtime_data
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = name
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)},
                                           name=entry.title, manufacturer="Crestron", model="CEN-GWEXER")

    async def async_added_to_hass(self):
        self.async_on_remove(async_dispatcher_connect(
            self.hass, f"{DOMAIN}_{self.entry.entry_id}", self.async_write_ha_state))
