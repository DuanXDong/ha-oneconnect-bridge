> [!WARNING]
> 本项目是非官方 Home Assistant 自定义集成，未获得华为或 OneConnect 项目方的官方授权、认可或支持。
> 项目用于技术研究和 Home Assistant 实验环境，请遵守相关平台服务条款及适用法律。

---

<p align="center">
  <img src="custom_components/oneconnect_bridge/brand/icon.png" alt="OneConnect Bridge" width="160" />
</p>

<h1 align="center">OneConnect Bridge</h1>

<p align="center">
  <img src="https://img.shields.io/badge/Home%20Assistant-Custom%20Integration-41BDF5" alt="Home Assistant Custom Integration" />
</p>

## 项目说明

OneConnect Bridge 是一个运行在 Home Assistant 中、基于 OneConnect 技术栈并对接华为私有业务链路的 Python 网关实现。

它以标准华为父网关身份接入华为智慧生活，再将 HA 实体映射为子设备注册到华为云端；集成负责父网关配对、云端会话、子设备注册、状态同步和上下行控制，HA 侧通过每个网关独立的 YAML 配置选择华为产品模型和服务映射。

本项目的协议实现和业务边界借鉴了 [OneConnect](https://gitcode.com/ohos-oneconnect/communication_iot_connect)、OneConnect 上游文档（[docs](https://gitcode.com/ohos-oneconnect/docs)）、[ha_hwhomebridge](https://github.com/Wangxiaokang666-666/ha_hwhomebridge) C SDK 的真实运行行为，以及 [huawei-smarthome](https://github.com/xiasi0/ha-huawei-smarthome) 的账号侧云端研究结果。

## 前置条件与限制

- Home Assistant：当前按 2026.10.x 版本验证。
- Python：3.14.2+，跟随当前 Home Assistant Core 运行；不支持脱离 Home Assistant 独立运行。
- 局域网：Home Assistant 主机与华为智慧生活 App 应位于可互通的 IPv4 局域网；配置流中必须手动选择可用网卡。
- 配对网络：选定网卡必须允许 IPv4 多播和 UDP 5683 入站/出站，且 UDP 5683 不能被其他进程占用；容器、虚拟机或 VLAN 环境需要额外放行多播。
- 配对并发：同一 Home Assistant 进程同时只允许一个父网关进行局域网配对；已完成绑定的其他网关仍可保持云端在线。
- 实例数量：最多 3 个父网关实例，每个父网关最多 64 个子设备。

## 快速入门

### 1. 安装

手动安装：

```text
config/custom_components/oneconnect_bridge/
```

重启 Home Assistant。

### 2. 添加父网关

在 Home Assistant 中选择：

```text
设置 → 设备与服务 → 添加集成 → OneConnect Bridge
```

配置流中手动选择用于局域网配对的 IPv4 网卡。集成会为该实例生成独立的网关序列号，并启动配对监听。

### 3. 完成配对并上线

1. 从 Home Assistant 持久通知中取得 PIN。
2. 在华为智慧生活中添加网关。
3. 手动输入 PIN 完成局域网配对。
4. 等待父网关完成云端注册并显示在线。

父网关上线后，HA 才创建网关实体；此时可以看到在线状态、网关序列号和子设备数量。

### 4. 配置并注册子设备

每个父网关都有独立的运行时配置：

```text
.storage/oneconnect_bridge/gateways/<gateway_serial>/mapping.yaml
```

首次添加网关时，集成会从 [default_mapping.yaml](custom_components/oneconnect_bridge/default_mapping.yaml) 复制样例。样例只包含一个 `ZJ0V` 链路探针，用于确认父网关、云会话和子设备注册链路正常；它是普通用户子设备，可以直接删除。

编辑对应网关的 `mapping.yaml`：

1. 保持 `enabled: true`（如暂不注册子设备，可改为 `false`）；
2. 删除不需要的链路探针，并在 `children` 下按需添加自己的子设备；
3. 在每个子设备的 `product` 中直接填写产品身份字段，不再依赖内置产品样例；
4. 填写实际的 HA `entity_id`、服务和字段映射；
5. 点击网关设备上的“重载子设备配置”按钮。

产品配置的最小结构如下：

```yaml
product:
  prod_id: ZJ0V
  sub_prod_id: ""
  device_type: "347"
  manufacturer: "002"
  model: "MAEXTRO-S800 Grand Design"
  device_name: "尊界S800 Grand Design"
  protocol_type: 1
  setup_type: 0
  known_fields_only: true
  services:
    - st: car.ignition
      sid: ignition
```

产品身份和服务定义完全由用户侧 `mapping.yaml` 提供，集成不再预置产品目录。
`known_fields_only: true` 用于省略 ZJ0V 不需要的 `subProdId/setupType`；设备的 `fwv/hwv/swv` 始终由集成 `manifest.json` 版本生成，不由用户 YAML 配置。

重载成功后，集成会通过父网关会话注册或更新 YAML 中声明的子设备；删除的子设备也会从云端和本地材料中清理。探针保留时会占用一个子设备额度，删除后可使用完整的 64 个子设备额度。

### 5. 重新配对与删除

仅重新启动局域网配对监听，可调用：

```yaml
service: oneconnect_bridge.start_pairing
data:
  serial: <gateway_serial>
```

`start_pairing` 不会删除已有的云端身份。

如果需要删除旧网关后重新配对，请在 HA 中删除整个 OneConnect Bridge 集成。集成会依次清理子设备、revoke 父网关并删除对应持久化目录，然后重新添加集成即可。

### 6. AI 投影辅助技能

仓库提供 [OneConnect 设备投影技能](skills/oneconnect-device-projection/)，用于帮助 AI 根据 HA 实体、华为 `mainHelp.json` 全量目录和单品 Profile 生成子设备投影方案。

技能覆盖：

- HA 实体信息采集与映射建议；
- Huawei 产品和物模型查询；
- `prodId`、`deviceTypeId`、`manufacturerId`、`protType` 等注册字段包装；
- 服务、特征值、枚举、单位、范围和步进转换；
- `batchBind`/`devInfoSync` 注册失败诊断。

该技能是 AI 工具的辅助资源，不会由 Home Assistant 集成本身执行。使用时将该目录安装到所用 AI 工具的技能目录；技能默认只生成方案，只有用户明确授权时才更新 HA 侧 YAML，不修改生产代码。

## 相关项目

- [OneConnect](https://gitcode.com/ohos-oneconnect/communication_iot_connect) 上游
- OneConnect 上游文档（[docs](https://gitcode.com/ohos-oneconnect/docs)）
- [ha_hwhomebridge](https://github.com/Wangxiaokang666-666/ha_hwhomebridge)
- [huawei-smarthome](https://github.com/xiasi0/ha-huawei-smarthome)

## 许可

Apache License 2.0，详见仓库根目录的 [LICENSE](LICENSE)。
