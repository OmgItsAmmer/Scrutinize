import base64
import hashlib
import hmac
import json
import time
from uuid import UUID


class InvalidTokenError(ValueError):
    pass


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_access_token(user_id: UUID, email: str, secret: str, expires_minutes: int) -> str:
    now = int(time.time())
    header = _encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _encode(json.dumps({"sub": str(user_id), "email": email, "iat": now, "exp": now + expires_minutes * 60}, separators=(",", ":")).encode())
    signature = _encode(hmac.new(secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest())
    return f"{header}.{payload}.{signature}"


def decode_access_token(token: str, secret: str) -> dict:
    try:
        header, payload, signature = token.split(".")
        expected = _encode(hmac.new(secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise InvalidTokenError("Invalid token signature")
        claims = json.loads(_decode(payload))
        if int(claims["exp"]) <= int(time.time()):
            raise InvalidTokenError("Token expired")
        UUID(claims["sub"])
        return claims
    except InvalidTokenError:
        raise
    except Exception as exc:
        raise InvalidTokenError("Malformed token") from exc
