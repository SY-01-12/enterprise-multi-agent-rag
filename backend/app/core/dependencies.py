from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import User
from app.services.auth_service import get_user_by_id

#获取当前用户
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
async def get_current_user(
        token: str = Depends(oauth2_scheme),
        db: AsyncSession = Depends(get_db)
) -> User:
    try:
        payload = decode_access_token(token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

    user_id = payload.get('sub')
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

    user = await  get_user_by_id(user_id, db)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    return  user