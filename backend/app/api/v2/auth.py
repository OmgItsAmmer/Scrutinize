import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.core.config import Settings
from app.core.deps import get_app_settings, get_current_user, get_db_session
from app.models.user import ProjectMember, User
from app.schemas.auth import (
    GoogleLoginRequest,
    LoginRequest,
    PendingVerificationResponse,
    SignupRequest,
    TokenResponse,
    UserResponse,
    VerifyRequest,
)
from app.services.auth_service import AuthService
from app.services.email_service import EmailDeliveryError
from app.services.project_service import ProjectService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=PendingVerificationResponse, status_code=201)
def signup(body: SignupRequest, session: Session = Depends(get_db_session), settings: Settings = Depends(get_app_settings)):
    raise HTTPException(
        status_code=400,
        detail="Password authentication is disabled. Please use Google authentication.",
    )


@router.post("/verify", response_model=TokenResponse)
def verify(body: VerifyRequest, session: Session = Depends(get_db_session), settings: Settings = Depends(get_app_settings)):
    raise HTTPException(
        status_code=400,
        detail="Password authentication is disabled. Please use Google authentication.",
    )


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, session: Session = Depends(get_db_session), settings: Settings = Depends(get_app_settings)):
    raise HTTPException(
        status_code=400,
        detail="Password authentication is disabled. Please use Google authentication.",
    )


@router.post("/google", response_model=TokenResponse)
def google_login(
    body: GoogleLoginRequest,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
):
    if settings.environment == "development" and body.id_token.startswith("mock_token_"):
        email = body.id_token.removeprefix("mock_token_")
    else:
        try:
            resp = httpx.get(
                f"https://oauth2.googleapis.com/tokeninfo?id_token={body.id_token}",
                timeout=10.0,
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=400, detail="Invalid Google ID token.")
            payload = resp.json()
        except Exception as exc:
            if isinstance(exc, HTTPException):
                raise exc
            raise HTTPException(
                status_code=400,
                detail=f"Failed to verify Google token: {str(exc)}",
            ) from exc

        aud = payload.get("aud")
        if settings.google_client_id and aud != settings.google_client_id:
            raise HTTPException(status_code=400, detail="Google token audience mismatch.")

        email = payload.get("email")
        if not email:
            raise HTTPException(
                status_code=400,
                detail="Google token did not contain an email address.",
            )

    auth = AuthService(session, settings)
    user = auth.login_or_create_google_user(email)

    membership = session.exec(
        select(ProjectMember).where(ProjectMember.user_id == user.id)
    ).first()
    if membership is None:
        project = ProjectService(session).create_project("My First Project", {}, allow_duplicate_name=True)
        session.add(ProjectMember(user_id=user.id, project_id=project.id, role="owner"))
        session.commit()

    return TokenResponse(access_token=auth.token_for(user))


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)):
    return UserResponse(id=str(user.id), email=user.email)

