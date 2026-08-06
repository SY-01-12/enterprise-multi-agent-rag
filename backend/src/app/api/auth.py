from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import WrongCredentials
from app.db.session import get_db
from app.schema.user import UserResponse, UserCreate
from app.services.auth import create_user, get_user_by_username, get_current_user, blacklist_token
from app.core.security import verify_password, create_access_token
from app.schema.token import TokenResponse, TokenRequest
from app.models import User

router = APIRouter(
    prefix="/api/auth",
    tags=["认证"],
)

# 用户注册
@router.post("/register", response_model=UserResponse, summary="用户注册")
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    return await create_user(user_data, db)

# 用户登录
@router.post("/login", response_model=TokenResponse, summary="用户登录")
async def login(request: TokenRequest, db: AsyncSession = Depends(get_db)):
    user = await get_user_by_username(request.username, db)

    if not user:
        raise WrongCredentials("用户名或密码错误")

    if not verify_password(request.password, user.password_hash):
        raise WrongCredentials("用户名或密码错误")

    token = create_access_token(user.id, user.username)
    return TokenResponse(access_token=token, token_type="bearer", expires_in=get_settings().JWT_EXPIRE_TIME)

# 获取当前用户
@router.get("/me", response_model=UserResponse, summary="获取当前用户")
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user

# 用户登出
@router.post("/logout", summary="用户登出")
async def logout(
    authorization: str = Header(...),
):
    token = authorization.replace("Bearer ", "")
    await blacklist_token(token)
    return {"message": "登出成功"}
