"""Idempotent initial data (SRS 14.3). Safe to run on every boot; never deletes data."""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal, engine
from app.models.enums import (
    AiResultType,
    AiStatus,
    TicketCategory,
    TicketPriority,
    TicketStatus,
    TeamRole,
    UserRole,
)
from app.models.team import SupportTeam, TeamMember
from app.models.ticket import AiResult, SlaPolicy, Ticket
from app.models.user import User

logger = logging.getLogger(__name__)

# Non-secret sample content only; no customer PII in seed.
_TEAM_SPECS = [
    {
        "name": "Team Kỹ thuật",
        "manager": ("Nguyễn Văn Hùng", "hung.manager@example.com"),
        "agents": [
            ("Trần Thị Lan", "lan.agent@example.com"),
            ("Lê Văn Minh", "minh.agent@example.com"),
        ],
    },
    {
        "name": "Team Tài khoản & Thanh toán",
        "manager": ("Phạm Thu Hà", "ha.manager@example.com"),
        "agents": [
            ("Hoàng Văn Đạt", "dat.agent@example.com"),
            ("Vũ Thị Ngọc", "ngoc.agent@example.com"),
        ],
    },
]

_SLA_MINUTES = {
    TicketPriority.URGENT.value: (15, 240),
    TicketPriority.HIGH.value: (60, 480),
    TicketPriority.MEDIUM.value: (240, 1440),
    TicketPriority.LOW.value: (480, 2880),
}

_SAMPLE_TICKETS = [
    {
        "subject": "Không đăng nhập được vào tài khoản",
        "requester_name": "Mai Văn Sơn",
        "requester_email": "son.customer@example.com",
        "priority": TicketPriority.HIGH.value,
        "category": TicketCategory.ACCOUNT.value,
        "team_name": "Team Tài khoản & Thanh toán",
        "status": TicketStatus.IN_PROGRESS.value,
    },
    {
        "subject": "Website chậm khi truy cập buổi sáng",
        "requester_name": "Đỗ Thu Trang",
        "requester_email": "trang.customer@example.com",
        "priority": TicketPriority.MEDIUM.value,
        "category": TicketCategory.TECHNICAL.value,
        "team_name": "Team Kỹ thuật",
        "status": TicketStatus.OPEN.value,
    },
    {
        "subject": "Hóa đơn tháng 8 bị tính sai phí",
        "requester_name": "Ngô Văn Khải",
        "requester_email": "khai.customer@example.com",
        "priority": TicketPriority.URGENT.value,
        "category": TicketCategory.BILLING.value,
        "team_name": "Team Tài khoản & Thanh toán",
        "status": TicketStatus.PENDING.value,
    },
    {
        "subject": "Hướng dẫn xuất báo cáo doanh thu",
        "requester_name": "Trịnh Thu Hương",
        "requester_email": "huong.customer@example.com",
        "priority": TicketPriority.LOW.value,
        "category": TicketCategory.GENERAL.value,
        "team_name": "Team Tài khoản & Thanh toán",
        "status": TicketStatus.RESOLVED.value,
    },
    {
        "subject": "Lỗi không tải được file đính kèm",
        "requester_name": "Lý Văn Thành",
        "requester_email": "thanh.customer@example.com",
        "priority": TicketPriority.MEDIUM.value,
        "category": TicketCategory.TECHNICAL.value,
        "team_name": "Team Kỹ thuật",
        "status": TicketStatus.OPEN.value,
    },
    {
        "subject": "Câu hỏi về gói dịch vụ Premium",
        "requester_name": "Đinh Thu Vân",
        "requester_email": "van.customer@example.com",
        "priority": TicketPriority.MEDIUM.value,
        "category": TicketCategory.GENERAL.value,
        "team_name": "Team Kỹ thuật",
        "status": TicketStatus.CLOSED.value,
    },
]


async def run_seed(session_factory: async_sessionmaker | None = None) -> None:
    settings = get_settings()
    factory = session_factory or AsyncSessionLocal
    async with factory() as session:
        admin = await _ensure_admin(session, settings)
        team_by_name: dict[str, SupportTeam] = {}
        user_by_email: dict[str, User] = {admin.email: admin}

        for spec in _TEAM_SPECS:
            team, mgr = await _ensure_team(session, spec, user_by_email)
            team_by_name[spec["name"]] = team

        sla_by_priority: dict[str, SlaPolicy] = await _ensure_sla_policies(session)

        await _ensure_tickets(
            session, _SAMPLE_TICKETS, team_by_name, user_by_email, sla_by_priority
        )

        await session.commit()
    logger.info("seed complete")


async def _ensure_admin(session: AsyncSession, settings) -> User:
    existing = (
        await session.execute(select(User).where(User.email == settings.seed_admin_email.lower()))
    ).scalar_one_or_none()
    if existing:
        return existing
    if not settings.seed_admin_password:
        raise RuntimeError("SEED_ADMIN_PASSWORD must be provided via env (SRS 14.3)")
    admin = User(
        full_name="Quản trị viên hệ thống",
        email=settings.seed_admin_email.lower(),
        password_hash=hash_password(settings.seed_admin_password),
        role=UserRole.ADMIN.value,
        is_active=True,
    )
    session.add(admin)
    await session.flush()
    logger.info("seeded admin %s", admin.email)
    return admin


async def _ensure_team(session: AsyncSession, spec: dict, user_by_email: dict) -> tuple[SupportTeam, User]:
    team = (
        await session.execute(select(SupportTeam).where(SupportTeam.name == spec["name"]))
    ).scalar_one_or_none()
    if team is None:
        team = SupportTeam(name=spec["name"], description=spec["name"])
        session.add(team)
        await session.flush()

    mgr_email, agents = spec["manager"][1].lower(), spec["agents"]
    mgr = user_by_email.get(mgr_email)
    if mgr is None:
        mgr = (
            await session.execute(select(User).where(User.email == mgr_email))
        ).scalar_one_or_none()
        if mgr is None:
            mgr = User(
                full_name=spec["manager"][0],
                email=mgr_email,
                password_hash=hash_password(f"{mgr_email.split('@')[0]}@Dev123"),
                role=UserRole.MANAGER.value,
                is_active=True,
            )
            session.add(mgr)
            await session.flush()
        user_by_email[mgr_email] = mgr

    await _ensure_membership(session, team.id, mgr.id, TeamRole.MANAGER.value)

    for full_name, email in agents:
        email = email.lower()
        agent = user_by_email.get(email)
        if agent is None:
            agent = (
                await session.execute(select(User).where(User.email == email))
            ).scalar_one_or_none()
            if agent is None:
                agent = User(
                    full_name=full_name,
                    email=email,
                    password_hash=hash_password(f"{email.split('@')[0]}@Dev123"),
                    role=UserRole.AGENT.value,
                    is_active=True,
                )
                session.add(agent)
                await session.flush()
            user_by_email[email] = agent
        await _ensure_membership(session, team.id, agent.id, TeamRole.MEMBER.value)

    return team, mgr


async def _ensure_membership(session: AsyncSession, team_id, user_id, team_role: str) -> None:
    existing = (
        await session.execute(
            select(TeamMember).where(
                TeamMember.team_id == team_id, TeamMember.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    if existing:
        return
    session.add(TeamMember(team_id=team_id, user_id=user_id, team_role=team_role, is_active=True))
    await session.flush()


async def _ensure_sla_policies(session: AsyncSession) -> dict[str, SlaPolicy]:
    by_priority: dict[str, SlaPolicy] = {}
    for priority, (fr, res) in _SLA_MINUTES.items():
        existing = (
            await session.execute(select(SlaPolicy).where(SlaPolicy.priority == priority))
        ).scalars().all()
        policy = existing[0] if existing else SlaPolicy(
            name=f"SLA {priority}",
            priority=priority,
            first_response_minutes=fr,
            resolution_minutes=res,
            pause_on_pending=False,
            effective_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
            is_active=True,
        )
        if not existing:
            session.add(policy)
            await session.flush()
        by_priority[priority] = policy
    return by_priority


async def _ensure_tickets(session, samples, team_by_name, user_by_email, sla_by_priority) -> None:
    from app.models.user import User as _User

    # Deterministic ticket codes so repeated seeds are idempotent.
    for i, sample in enumerate(samples, start=1):
        code = f"TK-DEMO{i:04d}"  # demo codes; real codes come from generate_ticket_code()
        existing = (
            await session.execute(select(Ticket).where(Ticket.ticket_code == code))
        ).scalar_one_or_none()
        if existing:
            continue
        team = team_by_name[sample["team_name"]]
        # First active member of the team becomes the assignee for demo tickets.
        member_row = (
            await session.execute(
                select(TeamMember).where(
                    TeamMember.team_id == team.id, TeamMember.is_active.is_(True)
                ).limit(1)
            )
        ).scalar_one_or_none()
        assignee = None
        if member_row is not None:
            assignee = (
                await session.execute(select(_User).where(_User.id == member_row.user_id))
            ).scalar_one_or_none()

        sla = sla_by_priority[sample["priority"]]
        ticket = Ticket(
            ticket_code=code,
            requester_name=sample["requester_name"],
            requester_email=sample["requester_email"],
            subject=sample["subject"],
            description=f"Nội dung mẫu cho ticket {code}.",
            category=sample["category"],
            priority=sample["priority"],
            status=sample["status"],
            team_id=team.id,
            assigned_to=assignee.id if assignee else None,
            sla_policy_id=sla.id,
            version=1,
        )
        session.add(ticket)
        await session.flush()

        if i == 3 and assignee is not None:
            # One pending-review AI classification sample per spec (S0 deliverable).
            # requested_by is NOT NULL, so we only insert when an assignee exists.
            session.add(
                AiResult(
                    ticket_id=ticket.id,
                    requested_by=assignee.id,
                    result_type=AiResultType.CLASSIFICATION.value,
                    status=AiStatus.PENDING_REVIEW.value,
                    model_name="seed-mock",
                    prompt_version="classify-v1",
                    input_hash="seed-sample-hash",
                    confidence=0.92,
                    original_output={
                        "category": sample["category"],
                        "priority": sample["priority"],
                        "confidence": 0.92,
                        "reason": "Mẫu seed.",
                    },
                )
            )


if __name__ == "__main__":
    import asyncio

    asyncio.run(run_seed())
