from pydantic import BaseModel, Field, field_validator


class EmailRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized.count("@") != 1 or "." not in normalized.rsplit("@", 1)[1]:
            raise ValueError("Enter a valid email address")
        return normalized


class SignupRequest(EmailRequest):
    password: str = Field(min_length=8, max_length=128)


class VerifyRequest(EmailRequest):
    otp: str = Field(pattern=r"^\d{6}$")


class LoginRequest(EmailRequest):
    password: str


class PendingVerificationResponse(BaseModel):
    status: str = "awaiting_verification"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: str


class GoogleLoginRequest(BaseModel):
    id_token: str

