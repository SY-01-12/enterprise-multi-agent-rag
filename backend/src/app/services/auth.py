import logging
import time

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import hash_password, decode_access_token
from app.core.redis import get_redis, token_blacklist_key
from app.core.exceptions import (
    UserAlreadyExists,
    DatabaseError,
    Unauthorized,
    TokenRevoked,
    UserNotFound,
)
from app.db.session import get_db
from app.models import User
from app.schema.user import UserCreate


# 根据 user_id 进行用户查询
async def get_user_by_id(user_id: int, db: AsyncSession):
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalars().one_or_none()

# 根据 username 进行用户查询
async def get_user_by_username(username: str, db: AsyncSession):
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()

# 根据 email 进行用户查询
async def get_user_by_email(email: str, db: AsyncSession):
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()

# 创建用户
async def create_user(user_data: UserCreate, db: AsyncSession):
    try:
        if await get_user_by_username(user_data.username, db):
            raise UserAlreadyExists("用户名已存在")
        if await get_user_by_email(user_data.email, db):
            raise UserAlreadyExists("邮箱已存在")
        # 密码 hash 处理
        hashed = hash_password(user_data.password)
        # 用户信息提交
        user = User(
            username=user_data.username,
            email=user_data.email,
            password_hash=hashed,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user
    except UserAlreadyExists:
        await db.rollback()
        raise
    except SQLAlchemyError:
        await db.rollback()
        raise DatabaseError("创建用户失败，数据库异常")


"""
1. 用户登录 → 下发带 jti、exp 的 JWT；
2. 用户点击退出 → 调用`blacklist_token`，将 jti 写入 Redis 黑名单，有效期同 Token；
3. 后续携带旧 Token 请求接口 → 中间件调用`is_token_blacklisted`检测；
4. 查到在黑名单直接拦截，实现手动注销；
5. Redis 设置了过期时间，过期自动清理，不会无限堆积无效黑名单数据
"""

# 将 Token 加入黑名单
async def blacklist_token(token: str) -> None:
    try:
        payload = decode_access_token(token)
        jti = payload.get("jti", "")
        exp = payload.get("exp", 0)
        ttl = max(1, int(exp - time.time()))
        redis = await get_redis()
        await redis.setex(token_blacklist_key(jti), ttl, "1")
    except Exception:
        logging.getLogger(__name__).warning("Token blacklist failed", exc_info=True)

# 检查 Token 是否在黑名单
async def is_token_blacklisted(token: str) -> bool:
    try:
        payload = decode_access_token(token)
        jti = payload.get("jti", "")
        redis = await get_redis()
        return await redis.exists(token_blacklist_key(jti)) > 0
    except Exception:
        return False


# 获取当前用户
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    try:
        payload = decode_access_token(token)
    except JWTError:
        raise Unauthorized("Invalid authentication credentials")

    if await is_token_blacklisted(token):
        raise TokenRevoked()

    user_id = payload.get("sub")
    if user_id is None:
        raise Unauthorized("Invalid authentication credentials")

    user = await get_user_by_id(int(user_id), db)
    if user is None:
        raise UserNotFound()

    return user
