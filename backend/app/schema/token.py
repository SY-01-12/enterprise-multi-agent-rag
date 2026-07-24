from pydantic import BaseModel

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int

class TokenRequest(BaseModel):
    user_id: int
    password: str