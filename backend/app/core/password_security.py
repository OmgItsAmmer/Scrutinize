import base64
import hashlib
import os
import secrets


def hash_password(password: str) -> str:
    """Securely hash a password using PBKDF2-SHA256 with 100,000 rounds.

    Produces a formatted string containing algorithm, rounds, base64 salt, and base64 key.
    """
    salt = os.urandom(16)
    rounds = 100_000
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
    salt_b64 = base64.b64encode(salt).decode("utf-8")
    key_b64 = base64.b64encode(key).decode("utf-8")
    return f"pbkdf2_sha256${rounds}${salt_b64}${key_b64}"


def verify_password(password: str, hashed: str | None) -> bool:
    """Verify a raw password matches its stored PBKDF2 hash.

    Utilizes constant-time secrets comparison to eliminate timing channel attacks.
    """
    if not hashed:
        return False
    try:
        parts = hashed.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
            return False
        rounds = int(parts[1])
        salt = base64.b64decode(parts[2])
        key = base64.b64decode(parts[3])
        new_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
        return secrets.compare_digest(key, new_key)
    except Exception:
        return False
