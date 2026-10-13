"""Start and stop passive recordings without sending network commands."""
from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.entity import EntityCategory
from .entity import GatewayEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([CaptureButton(entry, "start", "Start capture"),
                        CaptureButton(entry, "stop", "Stop capture")])


class CaptureButton(GatewayEntity, ButtonEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:record-rec"

    def __init__(self, entry, key, name):
        super().__init__(entry, key, name)
        self.action = key

    async def async_press(self):
        getattr(self.relay.capture, self.action)()
        self.relay.notify()
