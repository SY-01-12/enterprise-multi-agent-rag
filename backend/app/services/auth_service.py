from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import hash_password
from app.models import User
from app.schema.user import UserCreate

#用户存在异常
class UserAlreadyExistsError(Exception):
    pass

#数据库异常
class UserDataBaseError(Exception):
    pass

#通过ID查询用户
async def get_user_by_id(id,db:AsyncSession):
    result = await db.execute(select(User).where(User.id == id))
    return result.scalars().one_or_none()

#通过用户名查询用户是否存在
async def get_user_by_username(username: str, db: AsyncSession):
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()

#通过邮箱查询用户
async def get_user_by_email(email: str, db: AsyncSession):
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()

#创建用户
async def create_user(user_data: UserCreate, db: AsyncSession):
    try:
        if await get_user_by_username(user_data.username, db):
            raise UserAlreadyExistsError('用户名已存在')

        if await get_user_by_email(user_data.email, db):
            raise UserAlreadyExistsError('邮箱已存在')

        hashed = hash_password(user_data.password)
        user = User(
            username = user_data.username,
            email = user_data.email,
            password_hash = hashed
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user
    except UserAlreadyExistsError as e:
        await  db.rollback()
        raise e
    except SQLAlchemyError:
        await db.rollback()
        raise UserDataBaseError('创建用户失败，数据库异常')


