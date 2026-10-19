# HA input contract

Read this reference when the user has not supplied enough information to build a safe projection.

## Minimum live-HA information

For a configured gateway, obtain:

- gateway serial;
- exact mapping path, normally `.storage/oneconnect_bridge/gateways/<serial>/mapping.yaml`;
- current child keys and whether the file contains user changes beyond the default probe;
- HA version and integration version;
- current gateway status and the latest OneConnect child-registration log lines.

Do not request or print `cloud/material.json`, PSK, secret, auth code, refresh token, or private certificates. These are not needed to build a mapping.

## Entity information by HA domain

| Domain | Required state/attributes |
| --- | --- |
| `light` | state, `brightness`, `rgb_color`, `color_temp_kelvin`, supported color modes |
| `switch` | state |
| `climate` | state/HVAC mode, `hvac_modes`, `current_temperature`, `temperature`, `current_humidity`, `target_humidity`, `fan_modes`, `swing_modes` |
| `cover` | state, `current_position`, supported features, open/close/stop/set-position capability |
| `fan` | state, `percentage`, `percentage_step`, `preset_mode`, `preset_modes`, `oscillating`, `direction` |
| `sensor` | state/native value, unit, device class, state class |

If a live HA connector or SSH session is available, read the entity registry and states directly. Otherwise ask the user for a redacted Developer Tools state dump or the entity registry entries. Entity IDs and ordinary state values are sufficient; secrets are not.

## Product-choice question

Ask one explicit question when product choice is absent:

> Should I use a specified Huawei product/Profile, or may I recommend the best candidate from `mainHelp.json` and its Profile? A recommendation is not cloud acceptance until `batchBind` succeeds.

If the user permits recommendation, rank candidates by exact service/characteristic coverage, readable/writable compatibility, protocol evidence, visible catalog status, and smallest unnecessary service surface.
