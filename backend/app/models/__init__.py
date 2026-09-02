# Import every model module so that Base.metadata is fully populated.
from . import audit, team, ticket, user  # noqa: F401
