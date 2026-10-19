---
name: oneconnect-device-projection
description: Design, validate, and optionally apply Home Assistant to Huawei OneConnect child-device projections using HA entity metadata, Huawei mainHelp catalog records, product Profiles, and observed batchBind behavior. Use for product selection, mapping.yaml generation, feature/enum conversion, or child-registration troubleshooting; do not use for unrelated Home Assistant configuration.
---

# OneConnect device projection

Use this skill when a user wants to expose Home Assistant entities as Huawei cloud child devices through OneConnect. The desired result is a traceable projection plan or a validated `mapping.yaml`, with every Huawei product field and conversion tied to a source.

## Operating boundary

- Keep the parent gateway identity separate from child product identity. Parent `prodId`, gateway protocol, and cloud material are not inferred from a child Profile.
- Do not modify production integration code unless the user explicitly asks for a code change. A user request to update HA configuration authorizes only the requested HA-side YAML change.
- Do not ask the user to paste passwords, tokens, PSKs, secrets, or private cloud material. If remote access is needed, use an already authorized connection and read only the necessary files.
- Treat catalog metadata as candidate evidence, Profile data as model evidence, and a real `batchBind` response as cloud acceptance evidence. Never claim that a product is cloud-registerable from `mainHelp.json` alone.
- Before changing live HA YAML, state which gateway file will change, which children will be added/removed, and whether a restart or integration reload is needed. Preserve unrelated user children.

## Workflow

1. Collect the minimum HA facts. Read [ha-input-contract.md](references/ha-input-contract.md) before asking questions.
2. Resolve product candidates. Use [catalog-profile-and-model.md](references/catalog-profile-and-model.md) and the `scripts/huawei_iot_lookup.py` helper. If the user specified a Huawei product ID or Profile URL, use it; otherwise recommend candidates and explain confidence.
3. Build the child plan. Read [registration-and-protocol.md](references/registration-and-protocol.md) for identity packaging, protocol mapping, sparse/known-field handling, and observed evidence.
4. Build conversions and YAML. Read [conversion-and-yaml.md](references/conversion-and-yaml.md) for HA source selection, enum translation, ranges, units, RGB, climate, cover, and sensor bindings.
5. Validate before applying: parse the YAML, verify every `sid` is selected, render the outbound `devInfo` field set, and check that every binding has a matching HA entity and a compatible Profile characteristic.
6. If live application is explicitly requested, update only the target gateway `mapping.yaml`, report the exact path and hash/check result, and recommend restart/reload. If registration fails, capture the concrete `failureList` and keep the failed candidate marked unverified.

## Required user-facing intake

If any item is missing, ask for it before generating a production mapping:

- HA version and whether the target is a local HA instance or a repository-only YAML.
- Gateway serial and the target mapping path, normally `.storage/oneconnect_bridge/gateways/<serial>/mapping.yaml`.
- For each source entity: `entity_id`, domain, current state, relevant attributes, unit, and device class. For climate include HVAC modes, fan modes, current/target temperature, and humidity; for cover include current position and supported actions; for fan include percentage/preset/oscillation; for light include brightness, RGB, and color temperature; for sensors include native value, unit, and device class.
- Huawei choice: product ID/Profile URL, or explicit permission for AI to recommend one from the full catalog.
- Whether the user wants a plan only, a local YAML patch, or a live HA-side update.

When the Huawei product is not specified, say that the recommendation is an AI-assisted candidate based on Profile compatibility and static catalog signals; request a real registration test before treating it as confirmed.

## Output requirements

Always return:

- a source-to-Huawei mapping table;
- selected product IDs and the Profile URLs used;
- protocol/identity assumptions and confidence level;
- conversions and enum maps, including raw Huawei values;
- unsupported or lossy capabilities;
- the generated YAML or the exact live file changed;
- validation result and the next reload/test action.

For live changes, explicitly state that the skill did not change production code unless that was separately requested.
