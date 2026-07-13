# Email provider setup

Scrutinize uses Resend for signup verification codes. Create a Resend account, verify a sending domain, and create an API key. Configure `RESEND_API_KEY` and `EMAIL_FROM` in the backend environment. The sender must belong to the verified domain.

In development, omitting `RESEND_API_KEY` logs the OTP to the backend console. Production fails closed when the key is absent.

Never commit provider credentials. Rotate the key if it is exposed and keep the provider's delivery logs free of message-body retention where possible.
