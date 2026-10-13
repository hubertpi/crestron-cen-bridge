"""Export explicit captures; raw payloads can contain private data."""
from homeassistant.loader import async_get_integration


async def async_get_config_entry_diagnostics(hass, entry):
    integration = await async_get_integration(hass, "crestron_gwexer")
    return {"integration_version": integration.manifest["version"],
            "schema_version": 1, **entry.runtime_data.snapshot(),
            "notes": ["Counters measure received bytes, not acknowledged delivery.",
                      "Raw TCP chunks are authoritative; candidate CIP framing and joins are unverified for this gateway.",
                      "TLS bytes can be forwarded but are not decrypted.",
                      "Captures include all traffic while recording, potentially including authentication and private data.",
                      "Captures are lost on reload. Starting replaces the previous capture."]}
