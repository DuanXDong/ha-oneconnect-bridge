# 服务适配器贡献

服务适配器将一个华为 `sid` 的服务契约转换为 HA 实体状态和命令。配置只选择服务、绑定实体，并填写该服务适配器明确开放的 `contract` 覆盖项。

## 当前预置服务

| `sid` | 默认契约来源 | 常见性 | 真实投影验证 |
| --- | --- | --- | --- |
| `switch` | [`100z` Profile](https://smarthome-drcn.dbankcdn.com/device/guide/100z/100z.json)，`binarySwitch.on` 使用 `0/1` | 常见服务；`st` 与线上值类型需按 Profile 确认 | 已验证 |
| `brightness` | [`100z` Profile](https://smarthome-drcn.dbankcdn.com/device/guide/100z/100z.json)，范围 `0..255` | 常见服务；范围不是通用契约 | 已验证 |
| `cct` | [`100z` Profile](https://smarthome-drcn.dbankcdn.com/device/guide/100z/100z.json)，范围 `2000..6500` | 常见服务；色温范围不是通用契约 | 已验证 |
| `colour` | [`100z` Profile](https://smarthome-drcn.dbankcdn.com/device/guide/100z/100z.json)，`red/green/blue` 为 `0..255` | 常见于彩灯 | 已验证 |

表中的“常见”只描述服务语义，不表示所有 Profile 使用相同的字段、范围或线上类型。Profile 差异必须由对应服务适配器验证并处理。

## 贡献规则

- 一个 `sid` 只维护一个服务适配器，统一在 `custom_components/oneconnect_bridge/business/adapters/registry.py` 注册。
- 提交前先检查注册表。已有 `sid` 的 Profile 差异，应为现有适配器增加受控 `contract` 项和测试，不能创建同名适配器。
- `contract` 只能覆盖该适配器明确开放的 Profile 差异，例如范围、步长或线上值类型。字段名称、HA 调用方式、状态读取路径和命令组装必须保留在 Python 服务适配器内。
- 每个新服务适配器的模块注释或贡献说明必须写明默认契约来源的 `prodId`、Profile URL、是否属于常见服务，以及已验证的能力范围。
- 未经真实投影验证的服务只能标记为候选，不能标记为已支持。

## 验收

每个服务适配器需要完成以下真实验证：

1. 使用来源单品完成子设备注册；
2. HA 状态变化后，华为侧收到正确的服务数据和 JSON 类型；
3. 华为侧下发命令后，正确调用目标 HA 实体；
4. 验证服务的默认契约和每个可覆盖 `contract` 变体；
5. 记录使用的 `prodId`、Profile URL、测试日期和验证结论。

## 查询华为 IoT 目录和 Profile

全量目录：

`https://smarthome-drcn.dbankcdn.com/device/guide/ver_202609_hmos/mainHelp.json`

单品 Profile：

`https://smarthome-drcn.dbankcdn.com/device/guide/{prodId}/{prodId}.json`

查询流程：

1. 在全量目录中按产品名称、`DeviceId` 或型号寻找候选单品；`DeviceId` 对应 YAML 的 `prod_id`。
2. 打开该单品 Profile，读取 `deviceTypeId`、`manufacturerId`、`deviceModel` 和 `protocolType`，用于填写产品身份。
3. 从 Profile 的 `services` 中读取 `serviceId` 作为 YAML `sid`，`serviceType` 作为 YAML `st`。
4. 读取对应 `characteristics` 的 `characteristicName`、`characteristicType`、`method`、`min`、`max`、`step`、`unit` 和 `enumList`，将服务契约和双向转换实现到服务适配器。
5. 如果 Profile 契约与已有服务适配器不同，先评估能否用该适配器开放的 `contract` 表达；不能表达时扩展现有适配器并完成真实投影验证。

目录和 Profile 只用于选择候选和实现契约；是否可注册、状态同步和命令链路仍以真实投影结果为准。
