import os
import signal

import pytest

from gridcast.common.signals import Terminated, raise_on_sigterm


def test_sigterm_becomes_an_exception() -> None:
    previous = signal.getsignal(signal.SIGTERM)
    raise_on_sigterm()
    try:
        with pytest.raises(Terminated):
            os.kill(os.getpid(), signal.SIGTERM)
    finally:
        signal.signal(signal.SIGTERM, previous)
