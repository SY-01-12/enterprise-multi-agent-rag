from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db
from app.schema.user import UserResponse, UserCreate
from app.services.auth_service import UserAlreadyExistsError, UserDataBaseError, create_user, get_user_by_username
from app.core.security import verify_password, create_access_token
from app.schema.token import TokenResponse

settings = get_settings()

router = APIRouter(
    prefix = '/api/auth',
    tags = ['认证']
)

#注册接口
@router.post('/register',response_model=UserResponse,summary='用户注册')
async def register(user_data: UserCreate,db:AsyncSession = Depends(get_db)):
    try:
        user = await create_user(user_data,db)
    except UserAlreadyExistsError as e:
        raise HTTPException(status_code=400,detail=str(e))
    except UserDataBaseError as e:
        raise HTTPException(status_code=500,detail='服务器内部错误，请稍后重试')

    return user

#登录接口
@router.post('/login',response_model=TokenResponse,summary='用户登录')
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    try:
        user = await get_user_by_username(form_data.username, db)
    except Exception:
        raise HTTPException(status_code=500, detail='服务器内部错误，请稍后重试')

    # 校验用户是否存在
    if not user:
        raise HTTPException(status_code=400, detail='用户名或密码错误')

    # 校验密码是否一致
    if not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=400, detail='用户名或密码错误')

    # 创建 JWT
    token = create_access_token(user.id, user.username)
    return TokenResponse(access_token=token, token_type='bearer', expires_in=settings.JWT_EXPIRE_TIME)