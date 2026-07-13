# JWT security policy

Set `JWT_SECRET_KEY` to at least 48 random bytes and store it only in the deployment secret manager:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Tokens use HS256, contain the user UUID in `sub`, and default to a 24-hour lifetime (`JWT_EXPIRY_MINUTES=1440`). Rotate the secret after suspected disclosure; rotation invalidates all sessions. Always serve production traffic over HTTPS. Do not place access tokens in URLs or logs.
