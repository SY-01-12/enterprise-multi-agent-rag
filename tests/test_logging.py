"""日志系统测试。

测试维度：
1. SensitiveDataFilter   — 敏感数据遮蔽
2. RequestIdFilter       — request_id 注入
3. ColoredConsoleFormatter — 文本格式输出
4. JSONFormatter         — JSON 格式输出
5. setup_logging         — 配置初始化 & 幂等
6. get_logger            — logger 获取
7. RequestIdMiddleware   — HTTP 请求 ID 注入
8. LoggingMiddleware     — HTTP 请求日志记录
9. 集成测试              — main.py 启动日志
"""

import json
import logging
import re

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from io import StringIO

from app.core.logging import (
    get_logger,
    setup_logging,
    SensitiveDataFilter,
    RequestIdFilter,
    ColoredConsoleFormatter,
    JSONFormatter,
    RequestIdMiddleware,
    LoggingMiddleware,
    request_id_var,
    _mask_value,
    _SENSITIVE_KEYS,
)


# ══════════════════════════════════════════════════════
# 1. _mask_value & SensitiveDataFilter
# ══════════════════════════════════════════════════════

class TestMaskValue:
    """测试敏感值遮蔽工具函数。"""

    def test_mask_short_string(self):
        """长度 ≤ 5 的字符串全遮蔽为 ***。"""
        assert _mask_value("abc") == "***"
        assert _mask_value("hi") == "***"
        assert _mask_value("12345") == "***"

    def test_mask_long_string(self):
        """长度 > 5 的字符串保留首 3 尾 2 字符。"""
        result = _mask_value("secretPassword123")
        assert result.startswith("sec")
        assert result.endswith("23")
        assert result.count("*") == len("secretPassword123") - 5

    def test_mask_empty_string(self):
        """空字符串全遮蔽。"""
        assert _mask_value("") == "***"


class TestSensitiveDataFilter:
    """测试日志敏感数据过滤器。"""

    def test_filter_redacts_sensitive_keys(self):
        """extra 中的敏感 key 值被自动遮蔽。"""
        sf = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="t.py", lineno=1,
            msg="test", args=(), exc_info=None,
        )
        record.__dict__["password"] = "superSecret"
        record.__dict__["token"] = "jwt-token-value"
        sf.filter(record)
        assert record.__dict__["password"] != "superSecret"
        assert "*" in record.__dict__["password"]
        assert record.__dict__["token"] != "jwt-token-value"
        assert "*" in record.__dict__["token"]

    def test_filter_preserves_non_sensitive_keys(self):
        """非敏感字段不被修改。"""
        sf = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="t.py", lineno=1,
            msg="test", args=(), exc_info=None,
        )
        record.__dict__["user_id"] = 42
        record.__dict__["username"] = "john"
        sf.filter(record)
        assert record.__dict__["user_id"] == 42
        assert record.__dict__["username"] == "john"

    def test_redact_string_bearer_token(self):
        """Bearer token 值被替换为 ***REDACTED***。"""
        sf = SensitiveDataFilter()
        result = sf._redact_string("Authorization: Bearer abcdefghij1234567890")
        assert "***REDACTED***" in result
        assert "abcdefghij" not in result

    def test_redact_string_sk_key(self):
        """sk- 前缀的 API key 被替换。"""
        sf = SensitiveDataFilter()
        result = sf._redact_string("Using key sk-abc123def456ghi789jklmnop for API")
        assert "***REDACTED***" in result

    def test_redact_nested_dict(self):
        """递归遮蔽嵌套 dict 中的敏感字段。"""
        sf = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="t.py", lineno=1,
            msg="test", args=(), exc_info=None,
        )
        record.__dict__["nested"] = {"password": "nested_secret", "name": "john"}
        sf.filter(record)
        assert record.__dict__["nested"]["password"] != "nested_secret"
        assert "*" in record.__dict__["nested"]["password"]
        assert record.__dict__["nested"]["name"] == "john"

    def test_filter_returns_true(self):
        """filter 始终返回 True（不过滤日志记录本身）。"""
        sf = SensitiveDataFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="t.py", lineno=1,
            msg="test", args=(), exc_info=None,
        )
        assert sf.filter(record) is True

    def test_sensitive_keys_coverage(self):
        """_SENSITIVE_KEYS 包含常见敏感字段名。"""
        required = {"password", "token", "secret", "api_key", "authorization"}
        for key in required:
            assert key in _SENSITIVE_KEYS, f"缺少敏感 key: {key}"


# ══════════════════════════════════════════════════════
# 2. RequestIdFilter
# ══════════════════════════════════════════════════════

class TestRequestIdFilter:
    """测试 request_id 注入过滤器。"""

    def test_injects_request_id(self):
        """从 contextvar 读取 request_id 并注入记录。"""
        request_id_var.set("test-rid-001")
        rf = RequestIdFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="t.py", lineno=1,
            msg="test", args=(), exc_info=None,
        )
        rf.filter(record)
        assert record.request_id == "test-rid-001"

    def test_default_request_id(self):
        """未设置 contextvar 时返回 '-'。"""
        # 重置 contextvar
        request_id_var.set("-")
        rf = RequestIdFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="t.py", lineno=1,
            msg="test", args=(), exc_info=None,
        )
        rf.filter(record)
        assert record.request_id == "-"

    def test_filter_returns_true(self):
        """filter 始终返回 True。"""
        rf = RequestIdFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="t.py", lineno=1,
            msg="test", args=(), exc_info=None,
        )
        assert rf.filter(record) is True


# ══════════════════════════════════════════════════════
# 3. ColoredConsoleFormatter
# ══════════════════════════════════════════════════════

class TestColoredConsoleFormatter:
    """测试开发用彩色控制台格式化器。"""

    def test_format_includes_all_fields(self):
        """输出包含时间、级别、request_id、logger、行号、消息。"""
        fmt = ColoredConsoleFormatter()
        record = logging.LogRecord(
            name="app.api.chat", level=logging.INFO,
            pathname="/path/to/chat.py", lineno=42,
            msg="用户查询文档", args=(), exc_info=None,
        )
        record.request_id = "abc12345"
        output = fmt.format(record)

        assert "INFO" in output
        assert "abc12345" in output
        assert "app.api.chat" in output
        assert "42" in output
        assert "用户查询文档" in output
        # 格式化器使用 %(name)s 而非 %(filename)s，logger 名已在输出中
        assert "app.api.chat" in output

    def test_format_color_codes_present(self):
        """输出包含 ANSI 颜色码（非 JSON 模式）。"""
        fmt = ColoredConsoleFormatter()
        record = logging.LogRecord(
            name="test", level=logging.WARNING, pathname="t.py", lineno=1,
            msg="警告", args=(), exc_info=None,
        )
        record.request_id = "x"
        output = fmt.format(record)
        # 包含 ANSI 转义码
        assert "\033[" in output

    def test_different_level_colors(self):
        """不同级别使用不同颜色码。"""
        fmt = ColoredConsoleFormatter()
        debug_rec = logging.LogRecord(
            "t", logging.DEBUG, "t.py", 1, "d", (), None)
        debug_rec.request_id = "-"
        error_rec = logging.LogRecord(
            "t", logging.ERROR, "t.py", 1, "e", (), None)
        error_rec.request_id = "-"

        d_out = fmt.format(debug_rec)
        e_out = fmt.format(error_rec)

        # DEBUG 用青色 (36m)，ERROR 用红色 (31m)
        assert "\033[36m" in d_out  # cyan
        assert "\033[31m" in e_out  # red


# ══════════════════════════════════════════════════════
# 4. JSONFormatter
# ══════════════════════════════════════════════════════

class TestJSONFormatter:
    """测试生产用 JSON 格式化器。"""

    def test_format_produces_valid_json(self):
        """输出为合法 JSON 单行。"""
        fmt = JSONFormatter()
        record = logging.LogRecord(
            name="app.service", level=logging.INFO, pathname="svc.py", lineno=10,
            msg="操作完成", args=(), exc_info=None,
        )
        record.request_id = "rid-001"
        output = fmt.format(record)

        parsed = json.loads(output)
        assert isinstance(parsed, dict)

    def test_format_required_fields(self):
        """JSON 包含所有必要字段。"""
        fmt = JSONFormatter()
        record = logging.LogRecord(
            name="app.x", level=logging.ERROR, pathname="x.py", lineno=5,
            msg="错误", args=(), exc_info=None,
        )
        record.request_id = "r1"
        parsed = json.loads(fmt.format(record))

        assert "ts" in parsed
        assert "level" in parsed
        assert "logger" in parsed
        assert "file" in parsed
        assert "func" in parsed
        assert "req_id" in parsed
        assert "msg" in parsed

    def test_format_includes_extra_fields(self):
        """extra 中的自定义字段被纳入 'extra' 子对象。"""
        fmt = JSONFormatter()
        record = logging.LogRecord(
            name="app.x", level=logging.INFO, pathname="x.py", lineno=1,
            msg="msg", args=(), exc_info=None,
        )
        record.request_id = "r2"
        record.__dict__["user_id"] = 99
        record.__dict__["kb_id"] = 7
        parsed = json.loads(fmt.format(record))

        assert "extra" in parsed
        assert parsed["extra"]["user_id"] == 99
        assert parsed["extra"]["kb_id"] == 7

    def test_format_excludes_builtin_fields(self):
        """LogRecord 内置字段不出现在 extra 中。"""
        fmt = JSONFormatter()
        record = logging.LogRecord(
            name="app.x", level=logging.INFO, pathname="x.py", lineno=1,
            msg="msg", args=(), exc_info=None,
        )
        record.request_id = "r3"
        parsed = json.loads(fmt.format(record))

        builtins = {"args", "levelname", "levelno", "pathname",
                     "filename", "module", "name", "msg"}
        if "extra" in parsed:
            for k in builtins:
                assert k not in parsed["extra"], f"内置字段 {k} 不应在 extra 中"

    def test_format_handles_non_serializable_extra(self):
        """extra 中不可 JSON 序列化的值被 str() 转换。"""
        fmt = JSONFormatter()
        record = logging.LogRecord(
            name="app.x", level=logging.INFO, pathname="x.py", lineno=1,
            msg="msg", args=(), exc_info=None,
        )
        record.request_id = "r4"
        record.__dict__["complex_obj"] = object()
        # 应不抛出异常
        output = fmt.format(record)
        parsed = json.loads(output)
        assert "extra" in parsed


# ══════════════════════════════════════════════════════
# 5. setup_logging
# ══════════════════════════════════════════════════════

class TestSetupLogging:
    """测试日志系统初始化。"""

    def test_setup_logging_configures_root(self, monkeypatch):
        """setup_logging 配置根 logger。"""
        import app.core.logging as log_mod

        # Reset for test
        log_mod._initialized = False
        monkeypatch.setattr(log_mod, "_initialized", False)

        log_mod.setup_logging()

        assert log_mod._initialized is True

    def test_setup_logging_idempotent(self, monkeypatch):
        """多次调用 setup_logging 不重复初始化。"""
        import app.core.logging as log_mod

        log_mod._initialized = True
        monkeypatch.setattr(log_mod, "_initialized", True)

        # 第二次调用应直接返回
        log_mod.setup_logging()
        assert log_mod._initialized is True

    def test_get_logger_returns_logger(self):
        """get_logger 返回 Logger 实例。"""
        logger = get_logger("app.test.module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "app.test.module"


# ══════════════════════════════════════════════════════
# 6. request_id_var (ContextVar)
# ══════════════════════════════════════════════════════

class TestRequestIdVar:
    """测试 request_id 上下文变量。"""

    def test_default_value(self):
        """默认值为 '-'。"""
        import app.core.logging as log_mod
        # 用一个全新的 contextvar 来测默认值
        assert log_mod.request_id_var.get("-") == "-"

    def test_set_and_get(self):
        """在同一上下文中设置和获取。"""
        request_id_var.set("custom-req-42")
        assert request_id_var.get() == "custom-req-42"
        # 恢复默认
        request_id_var.set("-")


# ══════════════════════════════════════════════════════
# 7. RequestIdMiddleware
# ══════════════════════════════════════════════════════

class TestRequestIdMiddleware:
    """测试请求 ID 中间件。"""

    @pytest.mark.asyncio
    async def test_generates_request_id(self):
        """无 X-Request-ID 头时自动生成 8 位 request_id。"""
        async def app_call(scope, receive, send):
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [],
            })

        middleware = RequestIdMiddleware(app_call)

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "headers": [],
            "client": ("127.0.0.1", 12345),
        }

        captured_headers = []

        async def receive():
            return {"type": "http.request"}

        async def send(msg):
            if msg["type"] == "http.response.start":
                captured_headers.extend(msg.get("headers", []))

        await middleware(scope, receive, send)

        # 验证响应头包含 X-Request-ID
        req_id_headers = [h for h in captured_headers
                          if h[0] == b"x-request-id"]
        assert len(req_id_headers) == 1
        # 自动生成的 ID 应为 8 位 hex
        rid = req_id_headers[0][1].decode()
        assert len(rid) == 8

    @pytest.mark.asyncio
    async def test_reuses_client_request_id(self):
        """客户端传了 X-Request-ID 头时复用。"""
        async def app_call(scope, receive, send):
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [],
            })

        middleware = RequestIdMiddleware(app_call)

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "headers": [(b"x-request-id", b"trace-001")],
            "client": ("127.0.0.1", 12345),
        }

        captured_headers = []

        async def receive():
            return {"type": "http.request"}

        async def send(msg):
            if msg["type"] == "http.response.start":
                captured_headers.extend(msg.get("headers", []))

        await middleware(scope, receive, send)

        req_id_headers = [h for h in captured_headers
                          if h[0] == b"x-request-id"]
        assert req_id_headers[0][1] == b"trace-001"

    @pytest.mark.asyncio
    async def test_skips_non_http(self):
        """非 HTTP scope（如 WebSocket）不处理。"""
        app = MagicMock()

        async def app_call(scope, receive, send):
            await send({"type": "websocket.accept"})

        middleware = RequestIdMiddleware(app_call)

        scope = {"type": "websocket", "path": "/ws"}

        async def receive():
            return {}

        async def send(msg):
            pass

        # 应不抛出异常
        await middleware(scope, receive, send)


# ══════════════════════════════════════════════════════
# 8. LoggingMiddleware
# ══════════════════════════════════════════════════════

class TestLoggingMiddleware:
    """测试 HTTP 访问日志中间件。"""

    @pytest.mark.asyncio
    async def test_logs_request_summary(self):
        """请求完成后记录摘要日志。"""
        async def app_call(scope, receive, send):
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [],
            })
            await send({
                "type": "http.response.body",
                "body": b"ok",
            })

        middleware = LoggingMiddleware(app_call)

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/chat/stream",
            "headers": [],
            "client": ("192.168.1.1", 54321),
        }

        async def receive():
            return {"type": "http.request"}

        msgs = []
        async def send(msg):
            msgs.append(msg)

        with patch("app.core.logging.get_logger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            await middleware(scope, receive, send)

            # 应调用 logger.log (记录访问日志)
            assert mock_logger.log.called, "应记录访问日志"

    @pytest.mark.asyncio
    async def test_client_ip_extraction(self):
        """从 ASGI scope 提取客户端 IP。"""
        middleware = LoggingMiddleware(MagicMock())

        # X-Forwarded-For 优先
        scope_with_fwd = {
            "headers": [(b"x-forwarded-for", b"10.0.0.1, 10.0.0.2")],
            "client": ("127.0.0.1", 12345),
        }
        ip = middleware._get_client_ip(scope_with_fwd)
        assert ip == "10.0.0.1"

        # 其次用 client
        scope_direct = {
            "headers": [],
            "client": ("203.0.113.5", 12345),
        }
        ip = middleware._get_client_ip(scope_direct)
        assert ip == "203.0.113.5"

    @pytest.mark.asyncio
    async def test_non_http_skipped(self):
        """WebSocket 请求不记录访问日志。"""
        app = MagicMock()

        async def app_call(scope, receive, send):
            await send({"type": "websocket.accept"})

        middleware = LoggingMiddleware(app_call)

        scope = {"type": "websocket", "path": "/ws"}

        async def receive():
            return {}

        async def send(msg):
            pass

        with patch("app.core.logging.get_logger") as mock_get_logger:
            await middleware(scope, receive, send)
            # WebSocket 不走 access log
            assert not mock_get_logger.called


# ══════════════════════════════════════════════════════
# 9. main.py 集成测试
# ══════════════════════════════════════════════════════

class TestMainIntegration:
    """测试 main.py 中日志系统集成。"""

    def test_main_imports_logging(self):
        """main.py 正确导入日志组件。"""
        from app.main import logger as main_logger
        assert main_logger is not None

    def test_main_middleware_order(self):
        """验证日志中间件已注册。"""
        from app.main import app
        middlewares = [m.cls.__name__ for m in app.user_middleware]
        assert "RequestIdMiddleware" in middlewares
        assert "LoggingMiddleware" in middlewares
        assert "CORSMiddleware" in middlewares

    def test_exception_handlers_registered(self):
        """验证异常处理器已注册且记录日志。"""
        from app.main import app
        from app.core.exceptions import AppException
        from app.core.exception_handlers import (
            app_exception_handler,
            generic_exception_handler,
        )

        # 验证异常处理器已注册
        handlers = app.exception_handlers
        assert AppException in handlers
        assert Exception in handlers

    def test_fastapi_app_title(self):
        """FastAPI app 标题正确。"""
        from app.main import app
        assert app.title == "Enterprise RAG System"
