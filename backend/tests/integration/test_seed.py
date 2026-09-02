import os

import pytest

from app.core.config import Settings

pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    not os.getenv("INTEGRATION", ""),
    reason="set INTEGRATION=1 when a live Postgres (docker compose up -d db) is available",
)
async def test_seed_is_idempotent(anyio_backend):
    from sqlalchemy import func, select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    import app.db.seed as seed_mod
    from app.models.team import SupportTeam
    from app.models.ticket import SlaPolicy, Ticket
    from app.models.user import User

    # Point an engine at the real DB for this run (migrations must already be applied).
    engine = create_async_engine(Settings().database_url)
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    # Run seed twice; counts must be identical the second time (idempotent).
    await seed_mod.run_seed(factory)
    first = await _counts(engine)
    await seed_mod.run_seed(factory)
    second = await _counts(engine)
    assert first == second, "seed must be idempotent"

    async with factory() as session:
        assert (await session.execute(select(func.count()).select_from(User))).scalar_one() >= 1
        assert (await session.execute(select(func.count()).select_from(SupportTeam))).scalar_one() == 2
        assert (await session.execute(select(func.count()).select_from(SlaPolicy))).scalar_one() == 4
        assert (await session.execute(select(func.count()).select_from(Ticket))).scalar_one() >= 6

    await engine.dispose()


async def _counts(engine):
    from sqlalchemy import text

    out = {}
    async with engine.connect() as conn:
        for tbl in ("users", "support_teams", "team_members", "tickets",
                    "sla_policies", "ai_results"):
            out[tbl] = (await conn.execute(text(f"SELECT count(*) FROM {tbl}"))).scalar_one()
    return out
