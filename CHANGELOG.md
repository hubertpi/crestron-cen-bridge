# Changelog

## 1.0.0

- First stable release following confirmed Cove on/off and state-feedback testing.
- Add the matching Crestron integration icon.
- Rewrite installation, upgrade, connection, gateway routing, and recording instructions around the commissioned setup.
- Remove outdated experimental notices and distinguish capture start/stop icons.
- Preserve existing entity IDs, configurable IP/port defaults, and the tested control protocol.

## 0.1.2

- Add Cove on/off commands and gateway-confirmed state.
- Serialize injected commands at complete CIP frame boundaries.
- Add command routing, feedback, and disconnect regression coverage.

## 0.1.1

- Fix configuration-form serialization and validate IPv4 addresses after submission.

## 0.1.0

- Initial independent gateway proxy, bounded captures, and diagnostics.
