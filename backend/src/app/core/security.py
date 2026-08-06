import bcrypt
import uuid
from datetime import timedelta, datetime
from jose import jwt
from app.core.config import get_settings


settings = get_settings()


# 密码 hash 处理
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

# 密码校验
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

# JWT 生成
def create_access_token(user_id: int, username: str) -> str:
    expire = datetime.now() + timedelta(minutes=settings.JWT_EXPIRE_TIME)
    payload = {
        "sub": str(user_id),
        "username": str(username),
        "jti": uuid.uuid4().hex,  # 唯一 ID，用于注销，退出登录
        "exp": expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

# JWT 解码
def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])