"""Configure a dedicated listener without contacting the live gateway."""
import ipaddress
import voluptuous as vol
from homeassistant import config_entries

DOMAIN = "crestron_gwexer"


def ip(value):
    try:
        return str(ipaddress.IPv4Address(value))
    except ValueError as err:
        raise vol.Invalid("Enter an IPv4 address") from err


def schema(settings):
    defaults = {"host": "172.26.219.35", "port": 41794,
                "listen_host": "0.0.0.0", "listen_port": 41796,
                "gateway_host": "172.26.219.38"}
    defaults.update(settings)
    return vol.Schema({vol.Required(k, default=v):
                       (vol.All(vol.Coerce(int), vol.Range(min=1, max=65535))
                        if k in ("port", "listen_port") else ip)
                       for k, v in defaults.items()})


def conflicts(hass, data, exclude=None):
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.entry_id == exclude:
            continue
        current = {**entry.data, **entry.options}
        if current["listen_port"] == data["listen_port"]:
            return True
    return False


class GatewayFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            if conflicts(self.hass, user_input):
                errors["base"] = "listener_conflict"
            else:
                return self.async_create_entry(title="Crestron CEN-GWEXER", data=user_input)
        return self.async_show_form(step_id="user", data_schema=schema(user_input or {}), errors=errors)

    @staticmethod
    def async_get_options_flow(config_entry):
        return GatewayOptions()


class GatewayOptions(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            if conflicts(self.hass, user_input, self.config_entry.entry_id):
                errors["base"] = "listener_conflict"
            else:
                return self.async_create_entry(title="", data=user_input)
        settings = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(step_id="init", data_schema=schema(user_input or settings), errors=errors)
