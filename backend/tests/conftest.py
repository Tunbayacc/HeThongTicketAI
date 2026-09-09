import os

import pytest

# Disable .env loading for tests so results are deterministic.
os.environ.setdefault("AI_PROVIDER", "mock")


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    from app.core.rate_limit import limiter

    limiter.reset()
    yield
    limiter.reset()
