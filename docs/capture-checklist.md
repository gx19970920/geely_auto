# 下一阶段抓包清单

1. 仅使用本人账号和本人车辆。
2. 分别录制 App 冷启动、Token 刷新、车辆列表、车辆主页手动刷新。
3. 本轮不录制锁车、空调、车窗、寻车或任何写操作。
4. 原始抓包只保留在 `captures/`，永不提交 Git。
5. 先运行 `scripts/sanitize_capture.py`，然后手工复核手机号、VIN、车牌、Token、Cookie、设备 ID、request ID 和坐标均已替换。
6. 只将脱敏副本放入 `tests/fixtures/`。
7. 对每个请求记录方法、域名、路径、头名称、Body schema、响应 schema、错误码以及 nonce/timestamp/签名的存在性。
