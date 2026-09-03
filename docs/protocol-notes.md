# 协议笔记（2026-09-03 第二轮：抓包取证后）

## 证据来源

- 实时 MITM 抓包：云手机（root，Android 15）+ 系统 CA bind-mount + adb reverse 代理隧道 + mitmproxy。
- 静态分析：base.apk（360 加固壳，主 dex 99MB 字符串可读）。
- 本地缓存：App MMKV（root 只读提取）中的车辆状态/列表缓存。

## 两条 API 栈

### 栈 A：x-ca 网关（api-gw-toc / app.geely.com / geely-user-api / iov-service）

认证头（已在抓包中验证）：

| 头 | 说明 |
|---|---|
| `token` | 36 位 UUID 型会话 token |
| `txCookie` | 含 `IOV_ACCOUNT_SESSIONID` 与 `usersig`（腾讯 IM 型） |
| `gl_user_id` | 19 位数字账号 ID |
| `x-ca-version/x-ca-key/x-ca-nonce/x-ca-timestamp/x-ca-signature/x-ca-signature-headers` | 阿里云 API 网关签名（HmacSHA256，Base64，44 字符） |
| `x-ca-appcode` | 每业务不同：`GEELY_APPCODE_MAIN`(key 204397973)、`geely_buff_geely_buf_prod`(key 204853712)、`geely-app-user` |
| `content-md5` | POST 时出现 |
| `deviceSN` | 16 位十六进制设备号 |

已验证端点（200 OK）：

| 端点 | 方法 | 说明 |
|---|---|---|
| `GET api-gw-toc.geely.com/home/recommend/getOpenPage` | GET | 首页配置 |
| `GET api-gw-toc.geely.com/v1/app/domainWhiteList` | GET | 域名白名单 |
| `GET api-gw-toc.geely.com/appVersion/checkUpdate` | GET | 版本检查 |
| `GET api-gw-toc.geely.com/my/getMyCenterCounts` | GET | 我的页计数 |
| `POST api-gw-toc.geely.com/api/v1/config/getList` | POST | 配置（请求体含 vin） |
| `POST geely-user-api.geely.com/api/v1/device/bind` | POST | 设备绑定（请求体含 mobile） |
| `GET iov-service-geely.geely.com/api/carControl/needConfirm` | GET | 车控确认标记 |
| `GET app.geely.com/api/v2/home/loveCarDetail` | GET(H2) | 爱车详情（请求头含 `x-refresh-token: true`） |
| `GET app.geely.com/api/v1/growthSystem/badge/carControlAction` | GET(H2) | 车控徽标 |

### 栈 B：TSP/GRIC（gric-api / gric-hf-api）

认证头（已在 favorite-vehicles 抓包中验证，名称全部大写）：

| 头 | 说明 |
|---|---|
| `AUTHORIZATION` | JWT（RS256，1.1KB；`sub`=accountId；与 MMKV `MODULE_LOGIN_ACCESS_TOKEN` 同源） |
| `X-API-SIGNATURE-VERSION` | `2.1` |
| `X-API-SIGNATURE-NONCE` | UUID |
| `X-TIMESTAMP` | 13 位毫秒 |
| `X-SIGNATURE` | Base64 32 字节（HMAC-SHA256 输出长度）——**算法未验证** |
| `X-DEVICE-ID` | UUID |
| `X-TENANT-ID` / `X-SALES-PLATFORM` / `X-APP-ID` | `GEELY` / `GEELY` / `GEELYCNCH001M0001 <!-- nosec-secret-scan (static app id) -->` |
| `X-PLATFORM` / `X-DEVICE-BRAND` / `X-DEVICE-MODEL` / `X-DEVICE-OS-VERSION` / `X-APP-VERSION` | 设备元数据 |
| `X-TSP-PLATFORM` | `2` |
| `X-VEHICLE-IDENTIFIER` | Base64（加密 VIN，App 侧加密） |
| `X-VEHICLE-SERIES` | Base64("KX11-A3-ICE") |
| `X-VEHICLE-BRAND` | `GEELY` |

证书锁定：gric-api / gric-hf-api 的部分连接拒绝 MITM 证书（握手中断）；主进程部分客户端未锁定（messageCount 抓取成功）。锁定逻辑疑似位于 `:dkservice` 进程（数字钥匙 SDK）。

已验证端点：

| 端点 | 方法 | 说明 |
|---|---|---|
| `GET gric-api.geely.com/ms-vehicle-core/api/v1.0/vehicle/favorite-vehicles` | GET | **车辆列表**（响应含 VIN/车型/TSP 主机） |
| `GET gric-hf-api.geely.com/ms-app-message-center/api/v1.0/car/message/messageCount` | GET(H2) | 消息计数 |

静态候选端点（dex 字符串，未实时验证）：

- `GET /ms-vehicle-status/api/v2.0/vehicle/status/latest`（车辆状态，最关键）
- `GET /ms-vehicle-capability-set/api/app/v1/vehicle/capability/available`
- `/ms-vehicle-core/.../set-default-vehicle|set-nick-name|set-plate-number|enterprise-vehicles`（写操作，禁止）
- `/auth/lid/token`、`/user-service/device/code`、`/device-platform/user/session/update`（登录/会话）
- `/geelyTCAccess/tcservices/vehicle/status/*`（行程历史）、`/remote-control/*`（写操作，禁止）

## 车辆状态响应 Schema（来自 App MMKV 缓存，213 字段）

顶层分区：`basicVehicleStatus`、`vehicleClimateStatus`、`vehicleDoorCoverStatus`、
`vehicleWindowStatus`、`vehicleBatteryStatus`、`vehicleBleExtra`、`shadowTspVehicleStatus`、
`updateTime`。

关键可读字段（详见 `captures/sanitized/vehicle_status_schema.md` 与解析器）：

- `basicVehicleStatus.fuelLevelPct / fuelLevel / distanceToEmpty / preClimateActive / usageMode`
- `vehicleDoorCoverStatus.doorLockStatus{Driver,Passenger,DriverRear,PassengerRear}` 等
- `vehicleBatteryStatus.chargeSts / chargerState / stateOfCharge ...`
- 枚举语义（"0"/"1" 对应开/关）**未验证**：集成侧一律输出 unknown，不得臆测。

## 令牌体系（来自 MMKV `MOD_LOGIN`，仅字段名记录）

- `MODULE_LOGIN_ACCESS_TOKEN`：JWT RS256（gric 栈 AUTHORIZATION）
- `MODULE_LOGIN_REFRESH_TOKEN`：JWT RS256（`aud=auth_client_geely_phone`）
- 刷新端点未实时捕获；`x-refresh-token: true` 请求头机制待复现验证。

## 登录流程待办

登录发生在用户本地（未抓取）。下一步抓包目标：

1. `/auth/lid/token` 与 `/user-service/device/code` 的请求/响应（token 刷新门禁）。
2. `status/latest` 的实时成功响应（主机归属 + 查询参数 + X-SIGNATURE 样本）。
3. X-SIGNATURE v2.1 输入串与密钥来源（静态：搜 HmacSHA256 调用点；动态：dkservice hook）。

## 无 Root 约束下的能力边界（2026-09-03 起生效）

用户要求后续开发**不依赖 root**。影响评估：

| 手段 | 无 root 可用性 | 说明 |
|---|---|---|
| 代理（`settings put global http_proxy`） | ✅（adb shell 权限即可） | 已验证 App 全程存活 |
| CONNECT/SNI 主机发现 | ✅ | 见下方主机地图 |
| 系统级 CA 安装（TLS 解密） | ❌ | 需 root bind-mount；用户 CA 对 targetSdk 33 无效 |
| frida-server / 运行时 DEX dump | ❌ | 需 root；gadget 重打包会改签名，风险高 |
| App 私有目录读取（MMKV/缓存） | ❌ | 需 root |

已完成的非 root 主机发现（155 条 SNI/CONNECT，App 全程存活，无风控复发）：
核心业务主机与既有清单一致（api-gw-toc、app.geely.com、gric-api、gric-hf-api、
iov-service、geely-user-api、gtsp-app-geely-oss），无未知主机；
定位服务为高德（dualstack-arestapi / restsdk.amap.com）。

结论：无 root 约束下，TLS 明文样本（status/latest 实时响应、token 刷新）
与 X-SIGNATURE 算法的运行时取证均不可行。剩余门禁的突破路径：

1. 静态还原 jiagu 加固的隐藏 dex 后分析签名调用点（难）；
2. 用户同意后的一轮 root 抓包（历史方案已验证）；
3. frida-gadget 重打包（改 APK 签名、需重新登录、风控风险高，不推荐）。

门禁解除前，集成保持签名门禁（`UnverifiedSigner`），不做真实网络调用。

## 开源参考项目分析（2026-09-04）

| 项目 | 覆盖范围 | 对本集成的可用性 |
|---|---|---|
| [lyj5812/geely-galaxy](https://github.com/lyj5812/geely-galaxy) | 银河App（galaxy-*.geely.com），x-ca 网关签名含 APP_SECRETS 表、refresh-token 登录、GeeTest 验证码 | 算法结构同族（阿里云网关标准），但 AppKey/Secret 为银河 App 专用，不覆盖本 App 的 204397973/204853712 |
| [suyunkai/geely-galaxy-assistant](https://github.com/suyunkai/geely-galaxy-assistant) | 银河App 青龙脚本（登录/签到/MQTT） | 同上 |
| [YossiKon/geely-connect](https://github.com/YossiKon/geely-connect) | 国际版 App（com.geely.global.em / ecloudkr / zeekrlife） | **snc SignInterceptor（nj/h.java）签名算法已完整移植并生产验证**：`X-SIGNATURE = Base64(HMAC-SHA256(canonical, secret))`，canonical = 排序白名单头 `lower:value\n` + 排序query（*→%2A, %2F→/, %3F→?）+ Base64(MD5(body)) + METHOD + .com后路径。与本 App 抓包的 X-SIGNATURE（32字节 SHA256 输出）同族 |

关键差距：snc 密钥**按 App/地区派生**（国际版 SEA 密钥由模拟器从 whitebox si.a blob 解出）。
本 App（com.geely.consumer，中国版）的 gric 栈密钥需同样手段提取——即需要 root/模拟器，
无 root 路线下不可得。x-ca 栈（204397973/204853712）的 AppSecret 也不在明文 dex 中。

结论维持：无 root 下三项门禁无法解除；集成保持签名门禁形态交付，
激活步骤见 `outputs/06_HA部署指南.md`。

## 设备环境备忘

- 2026-09-03 19:00+：用户清除 App 数据并重新登录后，**风控自毁循环解除**，
  App 在纯代理（无 CA、无 frida）环境下持续存活，业务流量正常。
- `debug_app` 全局设置会导致 AMS 在启动时强杀目标 App（上一轮残留，已清除并复测正常）。
- 反复 MITM/插桩后 App 主进程出现"启动后数秒静默退出"的风控循环，重启不解除；
  疑似本地 MMKV 风控标记或服务端风控。恢复手段（需用户决策）：清除 App 数据重新登录，
  或等待风控衰减。dkservice 进程不受影响。
- 工具链：frida 16.7.19（17.x 移除内置 Java bridge，不可用）；mitmproxy 12.2.3；
  adb reverse 在该云手机可用。
