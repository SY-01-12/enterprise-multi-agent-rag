from datetime import datetime
from pydantic import BaseModel, Field, model_validator

#前端注册用户所需的信息
class UserCreate(BaseModel):
    username: str = Field(...,min_length=3,max_length=50,description='用户名',example='admin')
    email: str = Field(...,pattern=r'^[a-zA-Z0-9_-]+@[a-zA-Z0-9_-]+(\.[a-zA-Z0-9_-]+)+$',description='邮箱',example='admin@qq.com')
    password: str = Field(...,min_length=6,max_length=50,description='密码',example='123456')
    confirm_password: str = Field(...,min_length=6,max_length=50,description='确认密码',example='123456')

    # 确认密码
    @model_validator(mode='after')
    def check_password(self):
        if self.password != self.confirm_password:
            raise ValueError('密码不一致')
        return self

#规定接口返回给前端的信息
class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool
    created_at: datetime

