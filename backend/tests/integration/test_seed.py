import os

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.db.seed as seed_mod
from app.core.config import Settings
from app.models.enums import TicketPriority
from app.models.team import SupportTeam
from app.models.ticket import AiResult, SlaPolicy, Ticket
from app.models.user import User

pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    not os.getenv("INTEGRATION", ""),
    reason="set INTEGRATION=1 when a live Postgres (docker compose up -d db) is available",
)
async def test_seed_is_idempotent(anyio_backend):
    engine = create_async_engine(Settings().database_url)
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    # Run seed twice; table counts must be identical the second time (idempotent).
    await seed_mod.run_seed(factory)
    first = await _counts(engine)
    await seed_mod.run_seed(factory)
    second = await _counts(engine)
    assert first == second, "seed must be idempotent"

    # Verify seed records by stable keys, not by total row counts
    async with factory() as session:
        admin_email = Settings().seed_admin_email.lower()
        admin = (await session.execute(
            select(User).where(User.email == admin_email)
        )).scalar_one_or_none()
        assert admin is not None, f"seed admin {admin_email!r} must exist"
        assert admin.role == "ADMIN"
        assert admin.is_active is True

        for team_name in ("Team Kỹ thuật", "Team Tài khoản & Thanh toán"):
            team = (await session.execute(
                select(SupportTeam).where(SupportTeam.name == team_name)
            )).scalar_one_or_none()
            assert team is not None, f"seed team {team_name!r} must exist"

        seed_emails = [
            "hung.manager@example.com",
            "ha.manager@example.com",
            "lan.agent@example.com",
            "minh.agent@example.com",
            "dat.agent@example.com",
            "ngoc.agent@example.com",
        ]
        for email in seed_emails:
            user = (await session.execute(
                select(User).where(User.email == email)
            )).scalar_one_or_none()
            assert user is not None, f"seed user {email!r} must exist"

        for priority in (
            TicketPriority.LOW.value,
            TicketPriority.MEDIUM.value,
            TicketPriority.HIGH.value,
            TicketPriority.URGENT.value,
        ):
            policy = (await session.execute(
                select(SlaPolicy).where(
                    SlaPolicy.priority == priority,
                    SlaPolicy.is_active.is_(True),
                )
            )).scalars().first()
            assert policy is not None, f"active SLA policy for priority {priority!r} must exist"

        for i in range(1, 7):
            code = f"TK-DEMO{i:04d}"
            ticket = (await session.execute(
                select(Ticket).where(Ticket.ticket_code == code)
            )).scalar_one_or_none()
            assert ticket is not None, f"seed ticket {code!r} must exist"

        demo3 = (await session.execute(
            select(Ticket).where(Ticket.ticket_code == "TK-DEMO0003")
        )).scalar_one_or_none()
        if demo3 is not None:
            ai_count = (await session.execute(
                select(func.count()).select_from(AiResult)
                .where(AiResult.ticket_id == demo3.id)
            )).scalar_one()
            assert ai_count >= 1, "seed ai_result for TK-DEMO0003 must exist"

    await engine.dispose()


async def _counts(engine):
    from sqlalchemy import text

    out = {}
    async with engine.connect() as conn:
        for tbl in ("users", "support_teams", "team_members", "tickets",
                    "sla_policies", "ai_results"):
            out[tbl] = (await conn.execute(text(f"SELECT count(*) FROM {tbl}"))).scalar_one()
    return out
