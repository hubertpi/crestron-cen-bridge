# Crestron CEN-GWEXER — 0.1.1 experimental capture build

Independent Home Assistant integration, domain `crestron_gwexer`. It does not modify or import the iPad or DM integrations. Gateway hardware compatibility has not yet been tested.

## Installation

Copy `custom_components/crestron_gwexer` into `/config/custom_components/`, restart Home Assistant, then add **Crestron CEN-GWEXER** under Settings → Devices & services. For HACS, add `https://github.com/hubertpi/crestron-cen-bridge` as a custom repository with category **Integration**, download it, restart Home Assistant, and add **Crestron CEN-GWEXER**. This is the initial experimental source release; gateway hardware compatibility remains unverified.

Enter the processor IPv4 address and CIP destination port, the allowed gateway IPv4 address, and HA's listener address and port during setup. All five settings remain editable through Configure. Editable defaults for this installation: AV3 address `172.26.219.35`, gateway address `172.26.219.38`, listener bind address `0.0.0.0`, processor port `41794`, and HA listener port `41796`. HA is at `172.26.219.10`. The observed gateway IP ID is `1A`; retain that ID when changing its destination. The gateway address is a source IP filter, not a destination for outbound connections.

Port **41796 is a proposed dedicated HA listener**, not a verified gateway setting. Confirm it is free and reachable. Before changing the gateway configuration, record its existing IP table and check its console help for custom destination-port syntax. Preserve the existing IP ID. Intended topology: gateway → HA listener → processor. If the gateway cannot select a different destination port, or the processor initiates the session, this topology needs adjustment before use. Nothing here changes the gateway configuration automatically.

## Capture

Press **Start capture**, operate one device, press **Stop capture**, then download the integration diagnostics. To record registration, start capture before the gateway connects. A recording lasts at most five minutes, 4000 TCP read events, or 2 MB of raw payload. Starting replaces the previous recording; reload/restart loses it. Raw recordings may contain authentication or private display data; inspect before sharing publicly.

Diagnostics include direction, UTC timestamp, session number, exact TCP read bytes, and best-effort candidate CIP frames and joins. TCP read boundaries are not packet/frame boundaries. Candidate frames can span reads; decoded joins are hypotheses inherited from the iPad decoder, not verified gateway controls. Unknown or encrypted bytes remain available in raw capture. TLS is not decrypted.

The connectivity entity only confirms both TCP sockets opened. Byte counts and session counts help distinguish an empty action from a session that never traversed HA. Counts measure received bytes, not delivery acknowledgment.

The proxy permits one gateway session per entry, rejects other source IPs, forwards unchanged bytes, applies backpressure, and closes both sides when either side ends. The gateway must reconnect after interruption. There is no standalone emulation, generated keepalive, command injection, replay, or inferred light entity. If HA goes offline while the gateway points to HA, the proxied control path is unavailable; restoring the original IP table restores the original route.

## Validation

Install test dependencies with `python -m pip install -r requirements-test.txt`, then run `python -m unittest discover -s tests -v`. Tests exercise actual loopback TCP relay traffic and lifecycle, raw capture limits, and split frame reconstruction. Hardware commissioning and a full Home Assistant runtime test are still required.

Decoder adapted from `hubertpi/crestron-cip-bridge` v0.1.25, commit `3a626d64ba0d463f3821fdcf9c56f45ccdf3b014`.
