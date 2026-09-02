"""S3 assignment policy predicates (pure, zero-DB).

Task 1 unit-tests these; assign_ticket (Task 2) and the list/detail mappers
(Task 3) consume them. `needs_reassignment` is DERIVED, never stored (Controller
decision 1): the S3 slice has no admin deactivation endpoint yet, so a stored
flag would be dead code reachable only from SQL; deriving from users.is_active
+ tickets.status means the readout is correct the moment an assignee is
(de)activated and clears itself on reassignment to an active AGENT.
"""

# Statuses that count as an *open* ticket for the reassignment pool (FR-ASG-09).
OPEN_STATUSES = frozenset({"OPEN", "IN_PROGRESS", "PENDING"})


def is_open_status(status: str) -> bool:
    return status in OPEN_STATUSES


def needs_reassignment(*, assigned_to: bool, status: str,
                       assignee_active: bool | None) -> bool:
    """An open ticket whose assignee user is disabled must be flagged for
    reassignment (FR-ASG-09). assignee_active=None => assignee row missing
    (deleted) => not flaggable. Closed/resolved tickets are out of the pool."""
    return bool(assigned_to) and is_open_status(status) and assignee_active is False


def is_valid_assignee(*, role: str, user_active: bool, membership_active: bool) -> bool:
    """A valid assignee is an active Support Agent with an active membership of
    the target team (FR-ASG-02/03)."""
    return role == "AGENT" and user_active and membership_active
