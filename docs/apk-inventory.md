# APK 静态库存

## 已验证事实

- 文件名：`base.apk`
- 大小：`194883536` bytes
- SHA-256：`F8CE578D43D6FC6880368D07B8276C0726EFB7887D8316D26BD59B70F68975C2`
- ZIP 条目数：`9327`
- DEX：仅有 `classes.dex`，未发现分包 DEX
- AndroidManifest.xml 未压缩大小：`160212` bytes
- 原生库数量：`69`
- 已观察到：`libZeekrSecurity.so`、`libgeelymain_safe.so`、`libgeelymainv2_safe.so`、`libgeelyuser_safe.so`、`libkiwicrash.so`、`libkiwi_dumper.so`。

## 证据边界

上述只是 APK ZIP 容器级事实。它们不能证明任何生产域名、请求路径、请求头、签名输入或远程命令格式。当前未安装 JADX、apktool 或 aapt；在没有已脱敏的动态成功样本时，不通过反编译结果猜测生产协议。
