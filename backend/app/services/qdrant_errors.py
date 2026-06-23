from qdrant_client.http.exceptions import ApiException


def format_qdrant_error(exc: BaseException) -> str:
    """Qdrant ApiException often has an empty str(); build a useful message."""
    if isinstance(exc, ApiException):
        status = getattr(exc, "status_code", None)
        body = getattr(exc, "body", None) or getattr(exc, "content", None)
        parts = ["Qdrant request failed"]
        if status is not None:
            parts.append(f"HTTP {status}")
        if body:
            parts.append(str(body))
        message = ": ".join(parts)
        if status == 403:
            message += (
                ". Qdrant Cloud needs QDRANT_API_KEY, or use "
                "QDRANT_URL=http://localhost:6333 for local Docker Qdrant."
            )
        return message
    return str(exc) or repr(exc)


def describe_worker_error(exc: BaseException) -> str:
    """Best-effort message for job failure UI and logs."""
    chain: BaseException | None = exc
    while chain is not None:
        if isinstance(chain, ApiException):
            return format_qdrant_error(chain)
        message = str(chain).strip()
        if message:
            return message
        chain = chain.__cause__
    return repr(exc)
