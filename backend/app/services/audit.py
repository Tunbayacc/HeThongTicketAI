"""Business audit-log writer + INET coerce (design spec §5.1; SRS NFR-OBS-05)."""

import ipaddress
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


def coerce_ip(value: str | None) -> str | None:
    """Return value only if it parses as an IP (INET column); otherwise None.

    Starlette's TestClient reports the client host as 'testclient', which is not
    an IP — writing it to the INET column would raise. Invalid/absent values
    become NULL so audit rows never crash on a weird client string.
    """
    if not value:
        return None
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return None
    return value


async def write_audit(
    session: AsyncSession,
    *,
    action: str,
    entity_type: str,
    outcome: str,  # AuditOutcome.SUCCESS / AuditOutcome.FAILURE
    actor_id: Any = None,
    entity_id: Any = None,
    metadata: dict | None = None,
    ip_address: str | None = None,
) -> None:
    """Add an audit row to the caller's session (caller commits).

    metadata MUST stay PII-free (SRS FR-AUTH-10, NFR-PRI): never put the user's
    email/password or token material here.
    """
    session.add(
        AuditLog(
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            outcome=outcome,
            metadata_=metadata,
            ip_address=coerce_ip(ip_address),
        )
    )
