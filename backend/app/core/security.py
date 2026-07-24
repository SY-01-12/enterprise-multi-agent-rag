import bcrypt
from datetime import timedelta, datetime
from jose import jwt, JWTError
from app.core.config import get_settings


settings = get_settings()
#密码加密
def hash_password(password: str) -> str :
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode('utf-8')

#密码解密
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

#JWT创建
def create_access_token(user_id:int,username:str) -> str:
    expire = datetime.now() + timedelta(minutes=settings.JWT_EXPIRE_TIME)
    payload = {
        'sub': str(user_id),
        'username':str(username),
        'exp': expire
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

#JWT解析
def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        raise