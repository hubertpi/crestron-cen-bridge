# Crestron CEN-GWEXER

Home Assistant integration for a Crestron CEN-GWEXER wireless gateway connected to an AV3 processor. Provides Cove light on/off control with gateway state feedback, plus traffic recording for diagnostics.

The gateway connects through Home Assistant to the AV3. Existing Crestron control continues through this proxy. This is a separate integration from the Crestron iPad and DM integrations.

## Install with HACS

1. In HACS, open **Custom repositories**, add `https://github.com/hubertpi/crestron-cen-bridge`, and select **Integration**.
2. Download the latest numbered release and restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration → Crestron CEN-GWEXER**.
4. Review the connection settings below. Configure the gateway route only after the listener is running.

For an existing installation, update in HACS and restart Home Assistant. Keep the existing integration entry; no gateway changes are needed. If HACS still shows a commit-based installation, use **Update information → Redownload** and select the numbered release.

For manual installation, copy `custom_components/crestron_gwexer` from the release ZIP into `/config/custom_components/`, then restart and add the integration.

## Connection settings

All addresses and ports are editable during setup and through **Configure** afterward.

| Setting | Default | Purpose |
| --- | --- | --- |
| AV3 IPv4 address | `172.26.219.35` | Processor destination |
| AV3 CIP port | `41794` | Processor destination port |
| HA listener bind address | `0.0.0.0` | Listen on all HA interfaces |
| Dedicated HA listener port | `41796` | Gateway connects to this port |
| Allowed gateway IPv4 address | `172.26.219.38` | Accept connections only from this gateway |

The commissioned HA address is `172.26.219.10`. Use that reachable address in the gateway IP table, not `0.0.0.0`. Reserve a different listener port for each proxy integration. Saving settings reloads the proxy and disconnects its current session.

### Gateway routing

The commissioned route uses IP ID `1A`: **CEN-GWEXER → HA:41796 → AV3:41794**. Save the original `IPTABLE` output before changing another installation.

This gateway console uses raw TCP port `41795`. From Ubuntu:

```sh
nc -C 172.26.219.38 41795 | tr '\r' '\n'
```

The following commands were used on this gateway:

```text
ADDMASTER 1A 172.26.219.10 41796
IPTABLE
REMMASTER 1A 172.26.219.35
IPTABLE
```

Verify the HA entry has port `41796` before removing the direct AV3 entry. On this firmware, `ADDMASTER` printed an error even when the entry was stored, and its help showed a misleading extra `device_id` argument. Treat the resulting `IPTABLE` as authoritative; other firmware may differ. Reboot the gateway if needed to apply the stored route.

To restore the original direct route for this installation:

```text
ADDMASTER 1A 172.26.219.35 41794
IPTABLE
REMMASTER 1A 172.26.219.10
IPTABLE
```

Verify the original destination was restored before removing the HA route. While routed through HA, this control path depends on HA and the integration running.

## Entities and behavior

- **Cove:** on/off light, normally `light.crestron_cen_gwexer_cove`. No brightness control is exposed because the installed LEDs are not dimmable.
- **Proxy TCP connection:** diagnostic connectivity indicator. It confirms both TCP connections, not application-level registration.
- **Start capture / Stop capture:** diagnostic recording controls.

Cove commands and feedback are specific to the commissioned installation; this integration does not automatically discover arbitrary wireless switches. HA control and feedback were physically confirmed working. Scene-driven feedback can take a few seconds to arrive.

State follows gateway feedback, not an optimistic assumption after sending a command. It starts unknown until feedback arrives and becomes unavailable on disconnect. Operate Cove once if no initial feedback arrives after restart. Commands are sent only to the current gateway session, at complete CIP frame boundaries, and are not retried after reconnect.

## Record diagnostics

1. Press **Start capture**.
2. Operate the device being investigated, leaving a few seconds between actions.
3. Press **Stop capture**.
4. Download diagnostics from the integration entry and save the JSON.

Recordings stop at five minutes, 4,000 read events, or 2 MB. Starting a new recording replaces the previous one; reloading or restarting clears it. Recordings contain raw traffic and may include private data, so review before sharing publicly.

Only traffic traversing this gateway proxy is captured. Other AV3 connections, such as a separate lighting controller, are outside its scope. Diagnostics contain timestamps, directions, session counters, raw bytes, and best-effort frame decoding. Unknown traffic is retained; encrypted traffic is not decrypted. Byte counters measure received bytes, not acknowledged delivery.

## Development

```sh
python -m pip install -r requirements-test.txt
python -m unittest discover -s tests -v
```

Tests cover relay lifecycle, capture bounds, frame reconstruction, Cove command routing and feedback, and configuration form serialization. Setup and entity loading have also been verified with Home Assistant 2026.10.0. Bundled branding displays on Home Assistant 2026.3 or newer.

The best-effort legacy decoder was adapted from `hubertpi/crestron-cip-bridge` v0.1.25. Raw bytes remain authoritative for unmapped traffic.
