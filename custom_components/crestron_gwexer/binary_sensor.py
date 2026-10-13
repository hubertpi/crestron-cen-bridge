"""TCP connectivity, not proof of successful CIP registration."""
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.helpers.entity import EntityCategory
from .entity import GatewayEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([Connection(entry, "connection", "Proxy TCP connection")])


class Connection(GatewayEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def is_on(self):
        return self.relay.connected
