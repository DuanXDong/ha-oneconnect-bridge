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

通过 HACS 安装：

1. 打开 `HACS → 集成`，点击右上角菜单并选择“自定义存储库”。
2. 添加仓库地址 `https://github.com/xiasi0/ha-oneconnect-bridge`，类型选择 `Integration`。
3. 搜索并下载 `OneConnect Bridge`。
4. 重启 Home Assistant。

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

首次添加网关时，集成会从 [default_mapping.yaml](custom_components/oneconnect_bridge/default_mapping.yaml) 复制样例。编辑对应网关的 `mapping.yaml`，为子设备填写华为产品身份、启用的服务和对应 HA 实体。

仓库提供的预置子设备模型及其 H5 页面、Profile 见[预置子设备模型](docs/preconfigured-child-products.md)。

每个服务由对应的服务适配器负责特征值、范围、HA 状态读取及 HA 命令调用。适配器开放的 `contract` 字段用于填写单品的 Profile 差异。

完成配置后点击网关设备上的“重载子设备配置”。

### 5. 贡献服务适配器

服务适配器的贡献规则、真实投影验收，以及华为全量 IoT 目录和 Profile 的查询方法见 [服务适配器贡献说明](docs/service-adapter-contributing.md)。

### 6. 重新配对与删除

可调用 `oneconnect_bridge.start_pairing` 服务并传入网关序列号，以重新启动局域网配对监听。

如需重新配对，请在 HA 中删除整个 OneConnect Bridge 集成后重新添加。

## 相关项目

- [OneConnect](https://gitcode.com/ohos-oneconnect/communication_iot_connect) 上游
- OneConnect 上游文档（[docs](https://gitcode.com/ohos-oneconnect/docs)）
- [ha_hwhomebridge](https://github.com/Wangxiaokang666-666/ha_hwhomebridge)
- [huawei-smarthome](https://github.com/xiasi0/ha-huawei-smarthome)

## 许可

Apache License 2.0，详见仓库根目录的 [LICENSE](LICENSE)。
