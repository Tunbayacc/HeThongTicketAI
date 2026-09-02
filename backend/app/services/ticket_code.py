"""Public-facing ticket codes: TK- + 8 RFC 4648 base32 chars (SRS 6.5, FR-PUB-03).

Base32 (A-Z, 2-7) excludes the look-alikes 0/O/1/I/L and is unambiguous when a
customer reads a code back over the phone. Codes are random, never sequential.
"""

import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.ticket import Ticket

_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"  # 32 chars: RFC 4648 base32

_PREFIX = "TK-"


def generate_ticket_code() -> str:
    return _PREFIX + "".join(secrets.choice(_ALPHABET) for _ in range(8))


async def unique_ticket_code(session: AsyncSession) -> str:
    """Return a fresh code guaranteed not to collide with an existing row.

    The tickets.ticket_code column is UNIQUE; a (vanishingly unlikely) collision
    must not surface as a 500 IntegrityError. Retry a few times, then fail loudly.
    """
    for _ in range(5):
        code = generate_ticket_code()
        exists = await session.execute(select(Ticket.id).where(Ticket.ticket_code == code))
        if exists.scalar_one_or_none() is None:
            return code
    raise AppError(500, "INTERNAL_ERROR", "Không thể tạo mã vé, vui lòng thử lại.")
