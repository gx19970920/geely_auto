<div align="center">

<img src="logo.png" alt="Geely Auto Logo" width="140" height="140" />

# 吉利汽车 (Geely Auto) for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://github.com/hacs/integration)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.1.0+-blue.svg?style=for-the-badge&logo=home-assistant)](https://www.home-assistant.io/)
[![Version](https://img.shields.io/badge/version-v0.3.0-brightgreen.svg?style=for-the-badge)](https://github.com/gx19970920/geely_auto/releases)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg?style=for-the-badge)](LICENSE)

*专为“吉利汽车”App 打造的 Home Assistant 车辆智能集成，支持全系吉利燃油/混动/插混车型状态监控、吉分资产、每日自动签到与全自动令牌续期。*

</div>

---

## 🌟 核心特性 (Features)

- 🚗 **全面车辆遥测 (Vehicle Telemetry)**
  - 剩余燃油百分比及油量（L）
  - 续航里程（km）与累计总里程（km）
  - 车辆引擎运行状态、启停状态
  - 中控门锁、四门状态、后备箱锁及开闭状态
  - 四门车窗开闭状态（二值传感器）
  - 小蓄电池状态与供电电压
  - 最近上报时间戳与网络信号
- 🏷️ **车辆自定义名称 (Custom Vehicle Nickname)**
  - 自动从吉利 App 中同步您为爱车设置的专属昵称（如“大白”、“我的爱车”），并优雅替换系统预设的默认车型名（如“星越L (燃油版)”）。
- 🪙 **“吉分”资产与明细 (Geely Points Sensor)**
  - 实时同步吉利 App 中的可用“吉分”积分余额。
  - 支持传感器属性查看积分流水、即将过期积分与账户统计。
- 📅 **一键每日签到 (Daily Check-in Button)**
  - 实体面板集成“每日签到”按键（Button 实体）。
  - 支持与 Home Assistant 自动化工作流联动（如设定每日早上 8 点自动执行签到，领取吉分）。
- 🔄 **全自动 Token 续签 Webhook (Seamless Auto-Renewal)**
  - 专为手机/自动化抓包打造的 Webhook 接收端点。
  - 当外部守护进程（如 Tasker、抓包脚本或自动化容器）捕获到新 Token 时，单次 HTTP POST 即可实时无感热更新集成凭证，永不过期。

---

## 🚘 支持车型 (Supported Models)

所有通过**吉利汽车 App** 进行车机绑定的车型均原生支持，包括但不限于：

- **星越系列**：星越L（燃油版 / Hi·F / Hi·P / 智擎）、星越S
- **博越系列**：博越L、博越COOL、新博越
- **缤字系列**：缤越、缤瑞COOL
- **帝豪系列**：第4代帝豪、帝豪L Hi·P
- **其他车型**：豪越L、嘉际L、ICON等吉利品牌全系智能网联车型

---

## 📦 安装指南 (Installation)

### 方式一：通过 HACS 安装（推荐）

1. 打开 Home Assistant 中的 **HACS**。
2. 点击右上角菜单，选择 **“自定义存储库 (Custom repositories)”**。
3. 在存储库地址输入：`https://github.com/gx19970920/geely_auto`，类别选择 **“集成 (Integration)”**，点击添加。
4. 在 HACS 列表中找到 **Geely Auto (吉利汽车)**，点击 **“下载”**。
5. **重启 Home Assistant**。

### 方式二：手动安装

1. 从 [Releases](https://github.com/gx19970920/geely_auto/releases) 页面下载最新的 `geely_auto.zip`。
2. 解压并将 `geely_auto` 文件夹上传至 Home Assistant 的 `custom_components` 目录下：
   ```text
   /config/custom_components/geely_auto/
   ```
3. **重启 Home Assistant**。

---

## ⚙️ 配置与使用 (Configuration)

### 1. 添加集成

1. 前往 **设置** -> **设备与服务** -> **添加集成**。
2. 搜索 **Geely Auto** 或 **吉利汽车**。
3. 配置凭据：
   - **Token 凭据接入**：输入从抓包或手机端提取到的 `Access Token`（JWT），即可完成车辆自动绑定。
   - **全自动更新**：集成支持通过内网 Webhook 接收最新 Token，免去手动维护烦恼。
   - **演示模式 (Demo Mode)**：勾选“演示模式”供开发者离线调试与效果体验。

### 2. 配置选项 (Options)

集成支持动态选项设置：
- **自定义代理端点 (Checkin Proxy URL)**：配置签到或远控转发代理服务地址，缺省为 `http://127.0.0.1:8899`。
- **自定义车辆昵称覆盖**：可随时手动修改车辆在 HA 面板中展示的友好名称。

---

## 📊 实体与传感器一览 (Entities)

| 平台 | 实体名称 | 标识符 / Unique ID | 说明 |
| :--- | :--- | :--- | :--- |
| `sensor` | 燃油余量 | `sensor.<car>_fuel_level` | 剩余油量（L） |
| `sensor` | 剩余燃油百分比 | `sensor.<car>_fuel_level_pct` | 燃油百分比（%） |
| `sensor` | 续航里程 | `sensor.<car>_distance_to_empty` | 预计可用续航（km） |
| `sensor` | 累计里程 | `sensor.<car>_odometer` | 车辆总行驶里程（km） |
| `sensor` | 吉分 | `sensor.geely_points` | 吉利 App 可用吉分积分余额 |
| `sensor` | 最近上报时间 | `sensor.<car>_last_updated` | 车辆云端最新同步时间 |
| `binary_sensor` | 引擎状态 | `binary_sensor.<car>_engine_status` | 发动机运转 / 熄火 |
| `binary_sensor` | 中控门锁 | `binary_sensor.<car>_central_locking` | 全部车门落锁状态 |
| `binary_sensor` | 车窗状态 | `binary_sensor.<car>_<door>_window` | 对应车窗打开 / 关闭 |
| `binary_sensor` | 后备箱 | `binary_sensor.<car>_trunk` | 尾门打开 / 关闭 |
| `button` | 每日签到 | `button.<car>_daily_checkin` | 点击一键执行 App 每日签到 |

---

## 🔒 安全与隐私保障 (Privacy & Safety)

1. **严格脱敏**：本项目开源代码经过多轮深度扫描与脱敏审查，**不包含**任何作者或第三方的真实手机号、车架号（VIN）、用户账号 ID 或真实网关私钥。
2. **只读保护与安全隔离**：本项目严格遵守 Home Assistant 安全原则，遥测数据全部为只读轮询；关键控制动作（如签到）通过独立代理或严格校验保护。
3. **数据直连**：所有通信均在您的 Home Assistant 宿主机与吉利官方云端 API 之间直接进行，绝不经过任何第三方中转服务器。

---

## ⚠️ 免责声明 (Disclaimer)

- 本项目为个人开源爱好开发，**非吉利汽车官方发布或背书产品**。
- “吉利”、“Geely”等商标及相关知识产权均归浙江吉利控股集团有限公司所有。
- 使用本集成产生的网络请求需遵循吉利汽车服务协议，开发者不对因使用本集成导致的任何账号异常、风控或车辆问题承担责任。

---

## 📄 开源许可证 (License)

本项目采用 [Apache-2.0 License](LICENSE) 许可证开源。欢迎提交 Issue 与 Pull Request！
