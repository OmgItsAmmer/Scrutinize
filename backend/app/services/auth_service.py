import secrets
from datetime import UTC, datetime, timedelta

from sqlmodel import Session, select

from app.core.config import Settings
from app.core.jwt_security import create_access_token
from app.core.password_security import hash_password, verify_password
from app.models.user import User
from app.services.email_service import EmailService


class AuthService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    def get_by_email(self, email: str) -> User | None:
        return self.session.exec(select(User).where(User.email == email.strip().lower())).first()

    def signup(self, email: str, password: str) -> User:
        normalized = email.strip().lower()
        user = self.get_by_email(normalized)
        if user and user.is_verified:
            raise ValueError("An account with this email already exists")
        otp = f"{secrets.randbelow(1_000_000):06d}"
        if user is None:
            user = User(email=normalized, password_hash=hash_password(password))
        else:
            user.password_hash = hash_password(password)
        user.verification_otp = otp
        user.otp_expires_at = datetime.now(UTC) + timedelta(minutes=self.settings.otp_expiry_minutes)
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        EmailService(self.settings).send_verification_otp(normalized, otp)
        return user

    def verify(self, email: str, otp: str) -> User | None:
        user = self.get_by_email(email)
        if not user or user.is_verified or not user.verification_otp or not user.otp_expires_at:
            return None
        expires = user.otp_expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        if expires <= datetime.now(UTC) or not secrets.compare_digest(user.verification_otp, otp):
            return None
        user.is_verified = True
        user.verification_otp = None
        user.otp_expires_at = None
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user

    def login(self, email: str, password: str) -> User | None:
        user = self.get_by_email(email)
        if not user:
            verify_password(password, "pbkdf2_sha256$100000$ZHVtbXk=$ZHVtbXk=")
            return None
        return user if user.is_verified and verify_password(password, user.password_hash) else None

    def login_or_create_google_user(self, email: str) -> User:
        normalized = email.strip().lower()
        user = self.get_by_email(normalized)
        if user is None:
            user = User(email=normalized, password_hash=None, is_verified=True)
            self.session.add(user)
            self.session.commit()
            self.session.refresh(user)
        elif not user.is_verified:
            user.is_verified = True
            self.session.add(user)
            self.session.commit()
            self.session.refresh(user)
        return user

    def token_for(self, user: User) -> str:
        return create_access_token(user.id, user.email, self.settings.jwt_secret_key, self.settings.jwt_expiry_minutes)
