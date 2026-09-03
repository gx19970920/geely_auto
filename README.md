# Geely Auto for Home Assistant

`geely_auto` 是面向"吉利汽车"App 车辆云服务的独立 Home Assistant 自定义集成（HACS 形态，与 geely-galaxy 同类）。

> [!IMPORTANT]
> 集成已完成协议实证层（基于 2026-09-03 对本人账号的脱敏抓包）与 HA 实体层脚手架。
> 剩余三项门禁（车辆状态实时样本、token 刷新流程、X-SIGNATURE v2.1 签名算法）
> 解除前，Config Flow 不会创建配置条目，也不会发出任何真实网络请求。

## 当前能力

### 协议层（证据分级）
- **已验证**：车辆列表 `favorite-vehicles`（JWT + X-SIGNATURE v2.1 全套请求头）、
  用户/首页/消息中心 9 个端点、令牌体系（JWT RS256 对）。
- **静态候选**：`/ms-vehicle-status/api/v2.0/vehicle/status/latest` 等（APK 字符串，待实时验证）。
- 车辆状态响应 Schema（213 字段，来自 App 本地缓存脱敏提取）。
- 端点表带证据标签；写操作路径一律不入表。

### 客户端
- 请求头装配器（已验证头集）+ `RequestSigner` 接口；默认签名器保持门禁。
- 传输映射：401/403 → 认证错误、429 → 限流、断网/超时 → 连接错误（带退避重试）。
- 解析器：多车、`bizVehicleJson` 合并、字段缺失一律 `None`（不臆测枚举语义）。
- 真实 socket 端到端测试：除签名器外全链路真实。

### Home Assistant 接入
- `DataUpdateCoordinator` 周期轮询（300s），门禁关闭 → 实体显示"协议门禁"。
- 每车设备（vin_hash 不可逆标识）+ 燃油液位/续航/使用模式传感器。
- 未知值显示 `unknown`，绝不伪造 0 或关闭。
- 诊断输出强制脱敏；只读纪律有测试守卫（控制类平台禁止存在）。
- 中英双语实体翻译。

## 安全边界

- 不含 AppKey、Secret、签名算法实现或任何账号数据。
- 抓包原始数据仅存 `captures/raw`（gitignored），产物全部脱敏并有扫描守卫。
- 控制类平台（lock/switch/climate/button 等）被测试禁止存在。

## 开发检查

```bash
python -m pytest
python -m ruff check .
python -m mypy custom_components scripts
python scripts/scan_secrets.py .
```

## 风险声明

本项目不是吉利官方集成。云 API 可能随时改变。任何未来的车辆控制功能都必须单独授权、限流并通过车辆状态确认结果。
