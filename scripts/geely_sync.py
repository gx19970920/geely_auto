from mitmproxy import ctx
from mitmproxy.http import Response, HTTPFlow
import urllib.request
import time
import json
import base64
import threading
import http.client
import socket
import re

HA_WEBHOOK_URL = "http://192.168.91.225:8123/api/webhook/geely_auto_update_token"
TOKEN_FILE = "/home/mitmproxy/.mitmproxy/last_token.json"
CHECKIN_STATUS_FILE = "/home/mitmproxy/.mitmproxy/checkin_status.json"

class DockerClient:
    def __init__(self, socket_path="/var/run/docker.sock"):
        self.socket_path = socket_path

    def request(self, method, path, body=None):
        class UnixConnection(http.client.HTTPConnection):
            def __init__(conn):
                super().__init__("localhost")
            def connect(conn):
                conn.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                conn.sock.connect(self.socket_path)

        conn = UnixConnection()
        headers = {"Host": "localhost"}
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode("utf-8")
        conn.request(method, path, body=data, headers=headers)
        resp = conn.getresponse()
        res_data = resp.read().decode("utf-8", errors="ignore")
        conn.close()
        return resp.status, res_data

    def exec_in_container(self, container_name, cmd):
        try:
            status, res = self.request("POST", f"/containers/{container_name}/exec", {
                "AttachStdout": True,
                "AttachStderr": True,
                "Cmd": cmd
            })
            if status != 201:
                return False, f"Create exec failed: {res}"
            exec_id = json.loads(res)["Id"]
            status, res = self.request("POST", f"/exec/{exec_id}/start", {
                "Detach": False,
                "Tty": False
            })
            return True, res
        except Exception as e:
            return False, str(e)

def decode_jwt_payload(token_str):
    try:
        raw = token_str
        if raw.lower().startswith("bearer "):
            raw = raw[7:].strip()
        parts = raw.split(".")
        if len(parts) >= 2:
            payload = parts[1]
            padded = payload + "=" * ((4 - len(payload) % 4) % 4)
            return json.loads(base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8"))
    except Exception as e:
        return {"decode_error": str(e)}
    return {}

class GeelyTokenSync:
    def __init__(self):
        self.last_token = None
        self.last_sync_time = 0
        self.is_checking_in = False
        self.docker = DockerClient()

    def _run_phone_task(self, do_sign=True):
        if self.is_checking_in:
            ctx.log.warn("[GeelySync] 手机任务已在执行中，跳过重复触发。")
            return
        self.is_checking_in = True
        action_name = "签到打卡" if do_sign else "读取签到状态"
        try:
            ctx.log.info(f"[GeelySync] 开始执行真机{action_name}流程...")
            # 1. 设置代理并唤醒解锁手机
            self.docker.exec_in_container("phone-checkin", ["adb", "shell", "settings", "put", "global", "http_proxy", "192.168.91.98:8899"])
            self.docker.exec_in_container("phone-checkin", ["adb", "shell", "input", "keyevent", "224"])
            time.sleep(1)
            self.docker.exec_in_container("phone-checkin", ["adb", "shell", "input", "swipe", "540", "1840", "540", "628", "350"])
            time.sleep(1)
            self.docker.exec_in_container("phone-checkin", ["adb", "shell", "input", "text", "970920"])
            time.sleep(1)
            self.docker.exec_in_container("phone-checkin", ["adb", "shell", "input", "keyevent", "66"])
            time.sleep(1)

            # 2. 启动吉利汽车 App
            self.docker.exec_in_container("phone-checkin", ["adb", "shell", "monkey", "-p", "com.geely.consumer", "-c", "android.intent.category.LAUNCHER", "1"])
            time.sleep(8)

            # 3. 点击【我的】标签页 (972, 2123)
            self.docker.exec_in_container("phone-checkin", ["adb", "shell", "input", "tap", "972", "2123"])
            time.sleep(3)

            # 4. 在【我的】页面上立即 dump UI 提取签到状态和吉分
            points = None
            sign_in_status = "未签到"
            try:
                self.docker.exec_in_container("phone-checkin", ["adb", "shell", "uiautomator", "dump", "/sdcard/ui_mine.xml"])
                _, xml_out = self.docker.exec_in_container("phone-checkin", ["adb", "shell", "cat", "/sdcard/ui_mine.xml"])

                # 匹配签到状态控件 tv_mine_sign_in
                m_sign = re.search(r'resource-id="com\.geely\.consumer:id/tv_mine_sign_in"[^>]*text="([^"]*)"', xml_out)
                if not m_sign:
                    m_sign = re.search(r'text="([^"]*)"[^>]*resource-id="com\.geely\.consumer:id/tv_mine_sign_in"', xml_out)
                if m_sign:
                    sign_text = m_sign.group(1).strip()
                    if "已签到" in sign_text:
                        sign_in_status = "已签到"
                    ctx.log.info(f"[GeelySync] 识别到当前签到控件文本: '{sign_text}' -> 状态: {sign_in_status}")

                # 匹配吉分 tv_mine_geely_points
                m_pts = re.search(r'resource-id="com\.geely\.consumer:id/tv_mine_geely_points"[^>]*text="([^"]*)"', xml_out)
                if not m_pts:
                    m_pts = re.search(r'text="([^"]*)"[^>]*resource-id="com\.geely\.consumer:id/tv_mine_geely_points"', xml_out)
                if m_pts and m_pts.group(1).isdigit():
                    points = int(m_pts.group(1))
                    ctx.log.info(f"[GeelySync] 成功从 App 界面获取到吉分: {points}")
            except Exception as pe:
                ctx.log.warn(f"[GeelySync] 提取界面数据异常: {pe}")

            # 5. 如果要求签到且当前未签到，则点击右上角签到按钮 (893, 468)
            if do_sign and sign_in_status == "未签到":
                ctx.log.info("[GeelySync] 执行点击签到按钮 (893, 468)...")
                self.docker.exec_in_container("phone-checkin", ["adb", "shell", "input", "tap", "893", "468"])
                time.sleep(3)
                # 轻按返回键关闭签到成功弹窗
                self.docker.exec_in_container("phone-checkin", ["adb", "shell", "input", "keyevent", "4"])
                time.sleep(1)
                sign_in_status = "已签到"
                ctx.log.info("[GeelySync] 签到点击完成，更新状态为: 已签到")

            # 6. 返回桌面并熄灭屏幕，恢复直连
            self.docker.exec_in_container("phone-checkin", ["adb", "shell", "input", "keyevent", "3"])
            self.docker.exec_in_container("phone-checkin", ["adb", "shell", "input", "keyevent", "223"])
            self.docker.exec_in_container("phone-checkin", ["adb", "shell", "settings", "put", "global", "http_proxy", ":0"])

            # 7. 本地持久化签到状态
            today_str = time.strftime("%Y-%m-%d")
            status_data = {
                "sign_in_status": sign_in_status,
                "checkin_date": today_str,
                "points": points,
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            try:
                with open(CHECKIN_STATUS_FILE, "w", encoding="utf-8") as f:
                    json.dump(status_data, f, ensure_ascii=False, indent=2)
            except Exception as fe:
                ctx.log.warn(f"[GeelySync] 保存签到状态文件异常: {fe}")

            # 8. 同步至 Home Assistant Webhook
            # 优先用内存 token，若无则从文件读取（容器重启后 self.last_token 为 None）
            token_for_ha = self.last_token
            if not token_for_ha:
                try:
                    with open(TOKEN_FILE, "r", encoding="utf-8") as tf:
                        token_data = json.load(tf)
                        token_for_ha = token_data.get("token")
                        ctx.log.info("[GeelySync] 内存 token 为空，从文件读取 token 成功")
                except Exception as te:
                    ctx.log.warn(f"[GeelySync] 从文件读取 token 失败: {te}")
            if token_for_ha:
                try:
                    payload = json.dumps({
                        "token": token_for_ha,
                        "geely_points": points,
                        "sign_in_status": sign_in_status,
                        "checkin_date": today_str,
                        "custom_name": "星越L·东方曜"
                    }).encode("utf-8")
                    req = urllib.request.Request(
                        HA_WEBHOOK_URL,
                        data=payload,
                        headers={"Content-Type": "application/json"},
                        method="POST"
                    )
                    with urllib.request.urlopen(req, timeout=5) as resp:
                        ctx.log.info(f"[GeelySync] 签到与吉分数据已同步至 HA Webhook: status={sign_in_status}, points={points}")
                except Exception as we:
                    ctx.log.warn(f"[GeelySync] 同步至 HA 失败: {we}")
            else:
                ctx.log.warn(f"[GeelySync] 无可用 token，跳过 HA Webhook 推送 (status={sign_in_status})")

            ctx.log.info(f"[GeelySync] 真机{action_name}流程执行完毕！")
        except Exception as e:
            ctx.log.error(f"[GeelySync] 真机流程异常: {e}")
        finally:
            self.is_checking_in = False

    def request(self, flow: http.HTTPFlow):
        # 1. 监听 Home Assistant 发来的触发签到请求
        if flow.request.path.startswith("/api/trigger_checkin"):
            ctx.log.info("[GeelySync] 收到来自 Home Assistant 的签到触发请求！")
            threading.Thread(target=self._run_phone_task, args=(True,), daemon=True).start()
            flow.response = Response.make(
                200,
                json.dumps({"status": "success", "message": "吉利汽车签到任务已触发并正在执行"}).encode("utf-8"),
                {"Content-Type": "application/json; charset=utf-8"}
            )
            return

        # 2. 监听读取签到状态的请求 (触发真机读取)
        if flow.request.path.startswith("/api/read_checkin_status"):
            ctx.log.info("[GeelySync] 收到来自 Home Assistant 的读取签到状态请求！")
            threading.Thread(target=self._run_phone_task, args=(False,), daemon=True).start()
            flow.response = Response.make(
                200,
                json.dumps({"status": "success", "message": "吉利汽车读取签到状态任务已触发并在后台执行"}).encode("utf-8"),
                {"Content-Type": "application/json; charset=utf-8"}
            )
            return

        # 3. 监听查询最新签到状态缓存的请求
        if flow.request.path.startswith("/api/checkin_status"):
            try:
                with open(CHECKIN_STATUS_FILE, "r", encoding="utf-8") as f:
                    content = f.read()
                flow.response = Response.make(200, content.encode("utf-8"), {"Content-Type": "application/json; charset=utf-8"})
            except Exception as e:
                flow.response = Response.make(200, json.dumps({"sign_in_status": "未签到", "checkin_date": time.strftime("%Y-%m-%d"), "error": str(e)}).encode("utf-8"), {"Content-Type": "application/json; charset=utf-8"})
            return

        # 4. 监听查询最新 Token 信息的请求
        if flow.request.path.startswith("/api/last_token"):
            try:
                with open(TOKEN_FILE, "r", encoding="utf-8") as f:
                    content = f.read()
                flow.response = Response.make(200, content.encode("utf-8"), {"Content-Type": "application/json; charset=utf-8"})
            except Exception as e:
                flow.response = Response.make(500, json.dumps({"error": str(e)}).encode("utf-8"), {"Content-Type": "application/json"})
            return

        # 3. 正常抓取吉利网络请求
        host = flow.request.pretty_host.lower()
        if "geely.com" in host or "zeekrlife.com" in host:
            auth = flow.request.headers.get("authorization") or flow.request.headers.get("Authorization")
            has_token = bool(auth and "eyJ" in str(auth))
            msg = f"[GeelySync] Request: {flow.request.method} {host}{flow.request.path[:60]} (has_token: {has_token})"
            ctx.log.info(msg)

            if has_token:
                token_str = str(auth).strip()
                now = time.time()

                # 持久化 Token 记录
                try:
                    payload = decode_jwt_payload(token_str)
                    info = {
                        "token": token_str,
                        "jwt_payload": payload,
                        "captured_from": host,
                        "request_url": flow.request.url,
                        "request_headers": dict(flow.request.headers),
                        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now))
                    }
                    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
                        json.dump(info, f, ensure_ascii=False, indent=2)
                except Exception as e:
                    ctx.log.error(f"[GeelySync] 保存 Token 文件异常: {e}")

                if token_str == self.last_token and (now - self.last_sync_time) < 300:
                    ctx.log.info("[GeelySync] Same token within 5min, skip duplicate sync.")
                    return

                ctx.log.info(f"===> Captured valid Geely token (from: {host}), syncing to HA...")
                try:
                    data = token_str.encode("utf-8")
                    req = urllib.request.Request(
                        HA_WEBHOOK_URL,
                        data=data,
                        headers={"Content-Type": "text/plain; charset=utf-8"},
                        method="POST"
                    )
                    with urllib.request.urlopen(req, timeout=5) as resp:
                        res_body = resp.read().decode("utf-8", errors="ignore")
                        succ_msg = f"===> [SUCCESS] Synced to HA! Status: {resp.status}, Response: {res_body}"
                        ctx.log.info(succ_msg)
                        self.last_token = token_str
                        self.last_sync_time = now
                except Exception as e:
                    err_msg = f"===> [FAILED] Push to HA exception: {e}"
                    ctx.log.error(err_msg)

    def response(self, flow: HTTPFlow):
        host = flow.request.pretty_host.lower()
        if "geely.com" in host or "zeekrlife.com" in host:
            path = flow.request.path.lower()
            # 拦截 H5 签到 API 响应，自动更新签到状态并推送至 HA
            if "sign" in path and flow.response and flow.response.status_code in (200, 201):
                try:
                    resp_text = flow.response.text
                    today_str = time.strftime("%Y-%m-%d")
                    if resp_text and any(kw in resp_text for kw in (
                        "signSuccess", "sign_success", "已签到", "签到成功",
                        '"code":0', '"code": 0', '"result":true'
                    )):
                        ctx.log.info(f"[GeelySync] 拦截到 H5 签到成功响应: {flow.request.path[:60]}")
                        status_data = {
                            "sign_in_status": "已签到",
                            "checkin_date": today_str,
                            "points": None,
                            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "source": "h5_api_intercept"
                        }
                        with open(CHECKIN_STATUS_FILE, "w", encoding="utf-8") as f:
                            json.dump(status_data, f, ensure_ascii=False, indent=2)
                        token_for_ha = self.last_token
                        if not token_for_ha:
                            try:
                                with open(TOKEN_FILE, "r", encoding="utf-8") as tf:
                                    token_data = json.load(tf)
                                    token_for_ha = token_data.get("token")
                            except Exception:
                                pass
                        if token_for_ha:
                            try:
                                ha_payload = json.dumps({
                                    "token": token_for_ha,
                                    "sign_in_status": "已签到",
                                    "checkin_date": today_str,
                                    "custom_name": "星越L·东方曜"
                                }).encode("utf-8")
                                req = urllib.request.Request(
                                    HA_WEBHOOK_URL,
                                    data=ha_payload,
                                    headers={"Content-Type": "application/json"},
                                    method="POST"
                                )
                                with urllib.request.urlopen(req, timeout=5) as resp:
                                    ctx.log.info("[GeelySync] H5签到成功状态已自动推送至 HA")
                            except Exception as we:
                                ctx.log.warn(f"[GeelySync] H5签到状态推送至 HA 失败: {we}")
                except Exception as re_e:
                    ctx.log.warn(f"[GeelySync] 拦截 H5 签到响应异常: {re_e}")
            if "vehicle" in path:
                try:
                    text = flow.response.text
                    if text and ("model" in text or "series" in text or "vin" in text or "alias" in text or "nick" in text or "name" in text):
                        with open("/home/mitmproxy/.mitmproxy/vehicle_response.json", "w", encoding="utf-8") as f:
                            f.write(json.dumps({"url": flow.request.url, "response": text}, ensure_ascii=False, indent=2))
                        ctx.log.info(f"[GeelySync] 抓取到车辆响应: {flow.request.path[:50]}")
                except Exception as e:
                    ctx.log.error(f"[GeelySync] 记录响应异常: {e}")

addons = [GeelyTokenSync()]
