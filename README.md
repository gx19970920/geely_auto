# Geely Auto for Home Assistant

`geely_auto` 是面向“吉利汽车”App 车辆云服务的独立 Home Assistant 自定义集成。

> [!IMPORTANT]
> 当前仓库只是安全的离线开发骨架。尚未获得已脱敏的成功协议样本，因此不会连接吉利云服务，也不支持真实车辆。

## 当前能力

- 类型化的 Token、车辆、能力和状态模型。
- 明确的异常分类。
- 不会联网的 `GeelyAutoApi` 协议门禁。
- 日志与抓包脱敏工具。
- Home Assistant Config Flow 会明确终止并提示需要协议样本，不会请求凭据。

## 明确不包含

- 任何未经实机抓包确认的域名、路径、请求头、AppKey、Secret 或签名算法。
- 账号密码、Token、Cookie、VIN、位置或设备标识。
- 远程控制命令或控制实体。

## 开发检查

```bash
python -m pytest
python -m ruff check .
python -m mypy custom_components scripts
python scripts/scan_secrets.py .
```

Docker 测试环境仅绑定本机：`http://127.0.0.1:18123`。启动前需先将 `HA_IMAGE` 固定为已记录的 digest。

## 风险声明

本项目不是吉利官方集成。云 API 可能随时改变。任何未来的车辆控制功能都必须单独授权、限流并通过车辆状态确认结果。
