"""GeeTest captcha HTTP views for Geely Auto integration.

Includes:
- Captcha HTML page view (embedded HTML, zero external asset dependency)
- Captcha result callback view
- GeeTest API proxy view (for CORS bypass if browser direct access is restricted)
"""

from __future__ import annotations

import gzip
import logging
from typing import TYPE_CHECKING

import aiohttp
from aiohttp import web
from homeassistant.components.http import HomeAssistantView

from .const import CAPTCHA_ID, DOMAIN, GEETEST_HOST

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


# ==================== Captcha Page View ====================


class GeelyCaptchaPageView(HomeAssistantView):
    """Serve GeeTest captcha web page."""

    url = "/api/geely_auto/captcha"
    name = "api:geely_auto:captcha"
    requires_auth = False

    async def get(self, request: web.Request) -> web.Response:
        """Return captcha HTML page with injected flow_id and captcha_id."""
        flow_id = request.query.get("flow_id", "")
        html = CAPTCHA_HTML.replace("__FLOW_ID__", flow_id)
        html = html.replace("__CAPTCHA_ID__", CAPTCHA_ID)
        return web.Response(text=html, content_type="text/html")


# ==================== Captcha Callback View ====================


class GeelyCaptchaCallbackView(HomeAssistantView):
    """Receive captcha verification result callback from browser."""

    url = "/api/geely_auto/captcha_callback"
    name = "api:geely_auto:captcha_callback"
    requires_auth = False

    async def post(self, request: web.Request) -> web.Response:
        """Handle captcha results and advance the config flow."""
        hass: HomeAssistant = request.app["hass"]
        try:
            data = await request.json()
        except Exception:
            return self.json_message("Invalid JSON", status_code=400)

        flow_id = data.get("flow_id")
        captcha_data = data.get("captcha_data")

        if not flow_id or not captcha_data:
            return self.json_message("Missing data", status_code=400)

        required_keys = ["lot_number", "captcha_output", "pass_token", "gen_time"]
        if not all(k in captcha_data for k in required_keys):
            return self.json_message("Invalid captcha data", status_code=400)

        # Store captcha result for config flow to consume
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN].setdefault("captcha_results", {})
        hass.data[DOMAIN]["captcha_results"][flow_id] = captcha_data

        # Advance config flow to next step
        try:
            result = await hass.config_entries.flow.async_configure(flow_id=flow_id)
            _LOGGER.debug(
                "Config flow advanced: %s",
                result.get("type") if isinstance(result, dict) else result,
            )
        except Exception as err:
            _LOGGER.error(
                "Failed to advance config flow %s: %s (%s)",
                flow_id,
                err,
                type(err).__name__,
            )
            return self.json_message(
                f"{type(err).__name__}: {err}",
                status_code=500,
            )

        return self.json({"success": True})


# ==================== GeeTest API Proxy View ====================


class GeeTestProxyView(HomeAssistantView):
    """Proxy GeeTest requests to captcha4.geely.com to avoid CORS restrictions."""

    url = "/api/geely_auto/gt/{path:.*}"
    name = "api:geely_auto:gt"
    requires_auth = False

    async def get(self, request: web.Request, path: str) -> web.Response:
        """Proxy GET requests."""
        return await self._proxy(request, path, "GET")

    async def post(self, request: web.Request, path: str) -> web.Response:
        """Proxy POST requests."""
        return await self._proxy(request, path, "POST")

    async def _proxy(
        self, request: web.Request, path: str, method: str
    ) -> web.Response:
        """Forward requests to captcha4.geely.com."""
        path = path.removeprefix("undefined")

        query_string = request.query_string
        target_url = f"https://{GEETEST_HOST}/{path}"
        if query_string:
            target_url += f"?{query_string}"

        proxy_base = f"{request.scheme}://{request.host}/api/geely_auto/gt"

        headers = {
            "User-Agent": request.headers.get(
                "User-Agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            ),
            "Accept": request.headers.get("Accept", "*/*"),
            "Accept-Language": request.headers.get(
                "Accept-Language", "zh-CN,zh;q=0.9,en;q=0.8"
            ),
            "Accept-Encoding": "gzip",
            "Referer": f"https://{GEETEST_HOST}/",
        }

        body = await request.read() if method == "POST" else None
        if method == "POST":
            content_type_hdr = request.headers.get("Content-Type")
            if content_type_hdr:
                headers["Content-Type"] = content_type_hdr

        try:
            connector = aiohttp.TCPConnector(ssl=False)
            async with (
                aiohttp.ClientSession(connector=connector) as session,
                session.request(
                    method,
                    target_url,
                    data=body,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp,
            ):
                resp_body = await resp.read()
                content_type, charset = _parse_content_type(
                    resp.headers.get("Content-Type"), path
                )
                content_encoding = resp.headers.get("Content-Encoding", "")

                if content_encoding == "gzip":
                    resp_body = gzip.decompress(resp_body)

                if "callback=" in query_string and "load" in path:
                    resp_body = _rewrite_geetest_body(
                        resp_body, proxy_base, f"/{path}?{query_string}"
                    )

                return web.Response(
                    body=resp_body,
                    status=resp.status,
                    content_type=content_type,
                    charset=charset,
                    headers={
                        "Access-Control-Allow-Origin": "*",
                        "Cache-Control": "no-cache",
                    },
                )
        except Exception as err:
            _LOGGER.error("GeeTest proxy error: %s", err)
            return web.Response(
                text=f"Proxy error: {err}",
                status=502,
                content_type="text/plain",
            )


def _parse_content_type(header: str | None, path: str) -> tuple[str, str | None]:
    """Determine clean content_type and charset for web.Response."""
    charset: str | None = None
    raw = header or "application/octet-stream"
    if ";" in raw:
        parts = raw.split(";", 1)
        content_type = parts[0].strip()
        if "charset=" in parts[1]:
            charset = parts[1].split("charset=", 1)[1].strip().split(";")[0].strip()
    else:
        content_type = raw

    clean_path = path.split("?", maxsplit=1)[0]
    if clean_path.endswith(".js"):
        content_type = "application/javascript"
        charset = "utf-8"
    elif clean_path.endswith(".css"):
        content_type = "text/css"
        charset = "utf-8"
    return content_type, charset


def _rewrite_geetest_body(body: bytes, proxy_base: str, request_path: str) -> bytes:
    """Rewrite GeeTest JSONP responses to replace captcha domain with proxy."""
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        return body

    proxy_host = proxy_base.split("//", 1)[1]
    text = text.replace(f"https://{GEETEST_HOST}", proxy_base)
    text = text.replace(f"http://{GEETEST_HOST}", proxy_base)
    text = text.replace(f"//{GEETEST_HOST}", f"//{proxy_host}")
    text = text.replace(GEETEST_HOST, proxy_host)

    if "/load" in request_path and '"static_servers"' in text:
        text = text.replace('"static_servers"', '"static_path": "/", "static_servers"')

    return text.encode("utf-8")


def ensure_captcha_views(hass: HomeAssistant) -> None:
    """Register captcha views idempotently."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get("captcha_view_registered"):
        return
    domain_data.setdefault("captcha_results", {})
    for view in (
        GeelyCaptchaPageView(),
        GeelyCaptchaCallbackView(),
        GeeTestProxyView(),
    ):
        try:
            hass.http.register_view(view)
        except Exception as err:
            _LOGGER.error("Failed to register view %s: %s", view.url, err)
    domain_data["captcha_view_registered"] = True


# ==================== Embedded HTML Template ====================

CAPTCHA_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>吉利汽车 - 安全验证</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: #f0f2f5;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }
        .container {
            background: #ffffff;
            border-radius: 16px;
            padding: 36px 32px;
            max-width: 440px;
            width: 92%;
            box-shadow: 0 10px 30px rgba(0,0,0,0.08);
            border: 1px solid #eef0f3;
        }
        h2 { text-align: center; color: #1f2937; margin-bottom: 8px; font-size: 22px; font-weight: 600; }
        .subtitle { text-align: center; color: #6b7280; font-size: 14px; margin-bottom: 24px; }
        #captcha { display: flex; justify-content: center; margin: 20px 0; min-height: 50px; }
        .status {
            text-align: center; padding: 12px 16px; border-radius: 10px;
            margin-top: 16px; font-size: 14px; line-height: 1.5;
        }
        .status.success { background: #ecfdf5; color: #065f46; border: 1px solid #a7f3d0; }
        .status.error { background: #fef2f2; color: #991b1b; border: 1px solid #fecaca; }
        .status.info { background: #eff6ff; color: #1e40af; border: 1px solid #bfdbfe; }
        .result-box { display: none; margin-top: 20px; }
        .result-box.show { display: block; }
        .btn {
            display: block; width: 100%; padding: 12px; border: none;
            border-radius: 10px; font-size: 15px; font-weight: 500; cursor: pointer; margin-top: 12px;
            background: #2563eb; color: #ffffff; transition: background 0.2s;
        }
        .btn:hover { background: #1d4ed8; }
        #debug-log {
            margin-top: 16px; padding: 10px; background: #f9fafb;
            border: 1px solid #e5e7eb; border-radius: 6px; font-family: monospace;
            font-size: 11px; color: #4b5563; max-height: 120px; overflow-y: auto;
            display: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <h2>吉利汽车 安全验证</h2>
        <p class="subtitle">请完成滑块验证码，用于 Home Assistant 安全登录</p>

        <div id="captcha"></div>

        <div id="status-loading" class="status info">正在安全加载验证码...</div>

        <div id="auto-result-box" class="result-box">
            <div id="auto-status" class="status info">正在提交验证结果...</div>
        </div>

        <div id="error-box" class="result-box">
            <div class="status error" id="error-msg">验证失败</div>
            <button class="btn" onclick="location.reload()">重新加载</button>
        </div>

        <div id="debug-log"></div>
    </div>

    <script src="https://captcha4.geely.com/www/gt4.js"></script>
    <script>
        var CAPTCHA_ID = "__CAPTCHA_ID__";
        var flowId = "__FLOW_ID__";
        var debugEl = document.getElementById("debug-log");

        function debugLog(msg) {
            console.log("[GeeTest]", msg);
            debugEl.style.display = "block";
            var line = document.createElement("div");
            line.textContent = new Date().toLocaleTimeString() + " " + msg;
            debugEl.appendChild(line);
            debugEl.scrollTop = debugEl.scrollHeight;
        }

        function showError(msg) {
            document.getElementById("status-loading").style.display = "none";
            document.getElementById("error-box").className = "result-box show";
            document.getElementById("error-msg").textContent = msg;
        }

        function onCaptchaSuccess(data) {
            var autoBox = document.getElementById("auto-result-box");
            var autoStatus = document.getElementById("auto-status");
            document.getElementById("status-loading").style.display = "none";
            autoBox.className = "result-box show";
            autoStatus.textContent = "正在提交验证结果...";

            fetch("/api/geely_auto/captcha_callback", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ flow_id: flowId, captcha_data: data })
            })
            .then(function(resp) {
                if (resp.ok) {
                    autoStatus.className = "status success";
                    autoStatus.textContent = "验证成功！请返回 Home Assistant 继续完成登录。";
                    debugLog("验证结果已提交");
                    setTimeout(function() { window.close(); }, 2000);
                } else {
                    return resp.text().then(function(t) { throw new Error(t); });
                }
            })
            .catch(function(err) {
                autoStatus.className = "status error";
                autoStatus.textContent = "提交失败: " + err.message;
                debugLog("提交失败: " + err.message);
            });
        }

        var captchaServer = "captcha4.geely.com";
        var initFn = (typeof initGeetest === "function") ? initGeetest
                   : (typeof initGeetest4 === "function") ? initGeetest4
                   : null;

        if (initFn) {
            var opts = {
                captchaId: CAPTCHA_ID,
                language: "zho",
                protocol: "https://",
                apiServers: [captchaServer],
                onError: function(e) {
                    debugLog("onError: " + JSON.stringify(e));
                    showError("验证码加载失败: " + (e.msg || e.desc || JSON.stringify(e)));
                }
            };

            try {
                initFn(opts, function(captchaObj) {
                    debugLog("initGeetest 回调已触发");
                    document.getElementById("status-loading").style.display = "none";
                    captchaObj.appendTo("#captcha");
                    captchaObj.onReady(function() { debugLog("验证码就绪"); });
                    captchaObj.onSuccess(function() {
                        var result = captchaObj.getValidate();
                        debugLog("验证成功: lot_number=" + result.lot_number);
                        onCaptchaSuccess(result);
                    });
                    captchaObj.onError(function(e) { debugLog("onError: " + JSON.stringify(e)); });
                    captchaObj.onFail(function(e) { debugLog("onFail: " + JSON.stringify(e)); });
                    captchaObj.onClose(function() { debugLog("验证码弹窗已关闭"); });
                });
            } catch(e) {
                debugLog("异常: " + e.message);
                showError("验证码初始化异常: " + e.message);
            }
        } else {
            showError("GeeTest SDK 加载失败, 请检查网络");
            debugLog("gt4.js 未能加载 initGeetest");
        }
    </script>
</body>
</html>"""
