# Feature conversion and mapping YAML

## Model-to-YAML translation

For every selected Profile service:

```yaml
services:
  - st: <Profile.serviceType>
    sid: <Profile.serviceId>
```

Each binding points to a service ID and contains fields:

```yaml
bindings:
  - sid: <service id>
    fields:
      <characteristic or bridge field>:
        entity_id: <HA entity_id>
        source: state | attribute | constant | command
```

The current bridge supports these practical field behaviors:

- `state`: read the HA state string;
- `attribute`: read a named HA attribute;
- `constant`: send a fixed value, normally for a required model field;
- `command`: do not send an initial state; use when a cloud action must invoke an HA service.

## Common conversions

| HA capability | Typical Huawei field | Conversion |
| --- | --- | --- |
| on/off state | `on` | `state_map` `on/off` to the Profile's raw enum/bool values |
| light brightness | `brightness` | Use Profile min/max/step. The current bridge's brightness adapter scales HA 0..255 to the Huawei field's expected percentage/range for its built-in brightness handling. Verify the Profile before assuming 0..100. |
| RGB | `red`, `green`, `blue` | Read `rgb_color` and select `component: red/green/blue` |
| color temperature | `colorTemperature` | Read `color_temp_kelvin`; respect Profile range and step |
| climate mode | `mode` | Map HA HVAC modes to raw `enumVal`; reverse-map cloud values back to HA modes |
| climate temperature | `target`/`current` | Read `temperature` or `current_temperature`; preserve unit and range |
| cover position | `target`/`current` | Map HA 0..100 position to Profile's raw position range; respect open/close semantics |
| sensor value | Profile characteristic | Read `state` and preserve the Profile unit; do not scale without evidence |

## Enum rules

The OpenHarmony model specification defines `characteristicType: enum` and `enumList` entries with `enumVal`, `descCh`, and `descEn`. Use raw `enumVal` on the wire; labels are for human-facing YAML/reporting only.

Example:

```yaml
ha_to_huawei:
  type: state_map
  map:
    "cool": 2
    "heat": 3
    "fan_only": 4
    "dry": 5
huawei_to_ha:
  type: state_map
  map:
    "2": "cool"
    "3": "heat"
    "4": "fan_only"
    "5": "dry"
```

Keep mapping keys as strings because the current parser performs reverse lookup with `str(value)`. Values may be numbers or strings according to the Profile's `enumVal` type.

## Lossless projection rule

Do not claim support for a feature merely because HA exposes it. A feature is supported only if:

1. the Huawei Profile has a matching service/characteristic;
2. the characteristic permits the required operation (`R`, `W`, or `RW`);
3. the current bridge can read/apply the chosen field name; and
4. the conversion preserves range, unit, and enum meaning.

If any condition fails, mark it unsupported or lossy and ask whether to omit it, add a command-specific mapping, or change the Huawei product candidate.
