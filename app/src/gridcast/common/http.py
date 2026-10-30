"""Shared HTTP retry policy for external APIs."""

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential


def is_retryable(error: BaseException) -> bool:
    """Retry network failures, rate limiting and server errors; never client errors."""
    if isinstance(error, httpx.TransportError):
        return True
    if isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
        return status == 429 or status >= 500
    return False


api_retry = retry(
    retry=retry_if_exception(is_retryable),
    wait=wait_exponential(multiplier=2, min=2, max=60),
    stop=stop_after_attempt(5),
    reraise=True,
)
