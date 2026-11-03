"""Turn SIGTERM into an exception, so that a stopped pod still records how its run ended."""

import signal
from types import FrameType


class Terminated(BaseException):
    """Raised when the process receives SIGTERM, for example when Kubernetes stops a pod."""


def raise_on_sigterm() -> None:
    def _handler(signum: int, frame: FrameType | None) -> None:
        raise Terminated(f"received signal {signum}")

    signal.signal(signal.SIGTERM, _handler)
