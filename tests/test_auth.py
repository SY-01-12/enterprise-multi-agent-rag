"""Auth 模块测试。

测试维度：
1. TokenRequest / TokenResponse 模型校验
2. POST /api/auth/login — TokenRequest → TokenResponse 流程
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from app.schema.token import TokenRequest, TokenResponse


# ══════════════════════════════════════════════════════
# 1. TokenRequest / TokenResponse 模型单元测试
# ══════════════════════════════════════════════════════

class TestTokenRequest:
    """TokenRequest：前端提交用户名密码的请求体。"""

    def test_valid_request(self):
        """合法请求：username + password。"""
        req = TokenRequest(username="admin", password="123456")
        assert req.username == "admin"
        assert req.password == "123456"

    def test_missing_username_raises(self):
        """缺少 username 应抛出 ValidationError。"""
        with pytest.raises(ValueError):  # pydantic raises ValidationError (subclass of ValueError)
            TokenRequest(password="123456")

    def test_missing_password_raises(self):
        """缺少 password 应抛出 ValidationError。"""
        with pytest.raises(ValueError):
            TokenRequest(username="admin")

    def test_username_is_str_not_int(self):
        """username 为字符串，不再是旧的 user_id:int。"""
        req = TokenRequest(username="zhangsan", password="pwd")
        assert isinstance(req.username, str)
        assert not isinstance(req.username, int)


class TestTokenResponse:
    """TokenResponse：登录成功后返回给前端的 Token。"""

    def test_valid_response(self):
        resp = TokenResponse(access_token="eyJ...", token_type="bearer", expires_in=30)
        assert resp.access_token == "eyJ..."
        assert resp.token_type == "bearer"
        assert resp.expires_in == 30


# ══════════════════════════════════════════════════════
# 2. POST /api/auth/login 集成测试
# ══════════════════════════════════════════════════════

@pytest.fixture
def client():
    """创建 TestClient，override get_db 用 mock session。"""
    from app.main import app
    from app.db.session import get_db

    mock_session = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_session

    with TestClient(app) as c:
        yield c, mock_session

    app.dependency_overrides.clear()


class TestLoginEndpoint:
    """登录接口：前端发 TokenRequest → 后端返回 TokenResponse。"""

    @patch("app.api.auth.get_user_by_username")
    def test_login_success(self, mock_get_user, client):
        """正确用户名密码 → 200 + TokenResponse。"""
        c, mock_session = client

        # Mock 用户
        from app.models import User
        from app.core.security import hash_password
        mock_user = User(
            id=1,
            username="admin",
            email="admin@test.com",
            password_hash=hash_password("correct_password"),
            is_active=True,
        )
        mock_get_user.return_value = mock_user

        response = c.post("/api/auth/login", json={
            "username": "admin",
            "password": "correct_password",
        })

        assert response.status_code == 200, f"期望 200, got {response.status_code}: {response.text}"
        body = response.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        assert "expires_in" in body

    @patch("app.api.auth.get_user_by_username")
    def test_login_wrong_password(self, mock_get_user, client):
        """错误密码 → 401。"""
        c, mock_session = client

        from app.models import User
        from app.core.security import hash_password
        mock_user = User(
            id=1,
            username="admin",
            email="admin@test.com",
            password_hash=hash_password("correct_password"),
            is_active=True,
        )
        mock_get_user.return_value = mock_user

        response = c.post("/api/auth/login", json={
            "username": "admin",
            "password": "wrong_password",
        })

        assert response.status_code == 401
        assert "用户名或密码错误" in response.json()["detail"]

    @patch("app.api.auth.get_user_by_username")
    def test_login_user_not_found(self, mock_get_user, client):
        """用户不存在 → 401。"""
        c, mock_session = client

        mock_get_user.return_value = None

        response = c.post("/api/auth/login", json={
            "username": "ghost",
            "password": "whatever",
        })

        assert response.status_code == 401
        assert "用户名或密码错误" in response.json()["detail"]

    def test_login_missing_username(self, client):
        """缺少 username → 422 (pydantic 校验)。"""
        c, _ = client

        response = c.post("/api/auth/login", json={
            "password": "123456",
        })

        assert response.status_code == 422

    def test_login_missing_password(self, client):
        """缺少 password → 422 (pydantic 校验)。"""
        c, _ = client

        response = c.post("/api/auth/login", json={
            "username": "admin",
        })

        assert response.status_code == 422


# ══════════════════════════════════════════════════════
# 3. GET /api/auth/me 集成测试
# ══════════════════════════════════════════════════════

class TestGetMeEndpoint:
    """获取当前用户接口：前端带 Token 请求 → 后端返回 UserResponse。"""

    @pytest.fixture
    def valid_token(self):
        """生成一个真实的 JWT 用于测试。"""
        from app.core.security import create_access_token
        return create_access_token(user_id=1, username="admin")

    def test_me_no_token(self, client):
        """无 Token → 401。"""
        c, _ = client
        response = c.get("/api/auth/me")
        assert response.status_code == 401

    def test_me_invalid_token(self, client):
        """伪造 Token → 401。"""
        c, _ = client
        response = c.get("/api/auth/me", headers={
            "Authorization": "Bearer fake.invalid.token"
        })
        assert response.status_code == 401

    @patch("app.services.auth.get_user_by_id")
    def test_me_valid_token_user_found(self, mock_get_by_id, client, valid_token):
        """有效 Token + 用户存在 → 200 + UserResponse。"""
        c, mock_session = client

        from datetime import datetime
        from app.models import User
        mock_user = User(
            id=1,
            username="admin",
            email="admin@test.com",
            is_active=True,
            created_at=datetime(2026, 1, 1, 12, 0, 0),
        )
        mock_get_by_id.return_value = mock_user

        response = c.get("/api/auth/me", headers={
            "Authorization": f"Bearer {valid_token}"
        })

        assert response.status_code == 200, f"期望 200, got {response.status_code}: {response.text}"
        body = response.json()
        assert body["id"] == 1
        assert body["username"] == "admin"
        assert body["email"] == "admin@test.com"
        assert body["is_active"] is True
        assert "created_at" in body

    @patch("app.services.auth.get_user_by_id")
    def test_me_valid_token_user_not_found(self, mock_get_by_id, client, valid_token):
        """有效 Token 但用户已删除 → 401。"""
        c, mock_session = client

        mock_get_by_id.return_value = None

        response = c.get("/api/auth/me", headers={
            "Authorization": f"Bearer {valid_token}"
        })

        assert response.status_code == 404
        assert "用户不存在" in response.json()["detail"]
