from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    # Email is normalised (strip + lowercase) inside the service (SRS 6.4).
    email: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1, max_length=128)


class UserOut(BaseModel):
    id: str
    full_name: str
    email: str
    role: str  # AGENT | MANAGER | ADMIN
    is_active: bool


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class MeResponse(BaseModel):
    user: UserOut
