# Huawei catalog and Profile lookup

## Authoritative resources

- Full catalog: `https://smarthome-drcn.dbankcdn.com/device/guide/ver_202609_hmos/mainHelp.json`
- Product Profile: `https://smarthome-drcn.dbankcdn.com/device/guide/{prodId}/{prodId}.json`
- OpenHarmony model specification: [物模型技术规范](https://gitcode.com/ohos-oneconnect/specification/blob/master/OpenHarmony%E8%AE%BE%E5%A4%87%E7%BB%9F%E4%B8%80%E8%81%94%20%E7%89%A9%E6%A8%A1%E5%9E%8B%E6%8A%80%E6%9C%AF%E8%A7%84%E8%8C%83.md)

Use `scripts/huawei_iot_lookup.py` for repeatable lookups. It prints the catalog record and, when requested, the Profile's services and characteristics. If the CDN is unavailable, use a local cached `mainHelp.json`/Profile and label the result as cache-derived.

## What each source proves

`mainHelp.json` is a broad app/catalog index. Use it for:

- `DeviceId` / `prodId` candidate discovery;
- display name, `DeviceTypeId`, `ManufacturerId`, model, visibility/status, `template`, and Profile path;
- static hints such as `notShow`, `deviceOption`, `prodIdList`, `subProdIds`, `masterDevice`, and `slaveDevice`.

The Profile is the model source. Read:

- `deviceModel`, `deviceTypeId`, `manufacturerId`, `protocolType`;
- each service's `serviceType`, `serviceId`, and `characteristics`;
- each characteristic's `characteristicName`, `characteristicType`, `method`, `min`, `max`, `step`, `unit`, and `enumList`.

Map Profile `serviceType` to YAML `st`, and Profile `serviceId` to YAML `sid`. Map characteristic names into YAML binding field names only when the bridge adapter supports the field semantics.

## Candidate ranking

1. Exact Profile service/characteristic coverage of the HA entity.
2. Profile `method`: use `R`/reported fields for state and `W`/`RW` fields for commands.
3. Protocol evidence: use known successful values when available; do not infer a new protocol number merely from a display label.
4. Catalog visibility and topology hints. `notShow` or `notAllowAdd` are warnings, not a cloud allowlist.
5. Fewest unused services and least lossy conversion.

The static catalog cannot prove `batchBind` authorization. The final classification must use the real response: `errcode`, `successList`, and `failureList`.

## Current observed protocol conventions

These are project observations, not universal Huawei guarantees:

- Wi-Fi Profiles have been registered with `protType: 1`.
- PLC Profiles have been observed with `protType: 5`; some local adapter logic also recognizes `11`.
- The project's virtual-device candidates use `protType: 100` when the Profile says `VirtualDevice`.
- Mesh, BLE, BLE+SLE, SoftAP, and other labels need product-specific evidence; do not guess.

The Profile's `protocolType` string and the wire `protType` integer are related but not always identical. Explain the chosen conversion.
