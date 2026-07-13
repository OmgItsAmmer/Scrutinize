import logging

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)


class EmailDeliveryError(RuntimeError):
    """The configured provider could not deliver a verification email."""


class EmailService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def send_verification_otp(self, email: str, otp: str) -> None:
        if not self.settings.resend_api_key:
            if self.settings.environment == "production":
                raise RuntimeError("RESEND_API_KEY is required in production")
            logger.warning("Development OTP for %s: %s", email, otp)
            return
        try:
            response = httpx.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {self.settings.resend_api_key}"},
                json={
                    "from": self.settings.email_from,
                    "to": [email],
                    "subject": "Verify your Scrutinize account",
                    "html": (
                        f"<p>Your verification code is:</p><h1>{otp}</h1>"
                        f"<p>It expires in {self.settings.otp_expiry_minutes} minutes.</p>"
                    ),
                },
                timeout=10,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise EmailDeliveryError(
                "Verification email could not be delivered. Check the verified sender domain."
            ) from exc
