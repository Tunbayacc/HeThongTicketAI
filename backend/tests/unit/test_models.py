def _expected_tables():
    return {
        "users", "support_teams", "team_members", "tickets", "comments",
        "attachments", "ai_results", "ticket_history", "sla_policies",
        "refresh_tokens", "audit_logs",
    }


def test_models_module_registers_all_11_tables():
    import app.models  # noqa: F401  (import registers all tables)

    from app.models.base import Base

    assert set(Base.metadata.tables.keys()) == _expected_tables()


def test_tickets_has_required_columns():
    import app.models  # noqa: F401

    from app.models.base import Base

    cols = set(Base.metadata.tables["tickets"].columns.keys())
    required = {
        "id", "ticket_code", "requester_name", "requester_email", "subject",
        "description", "category", "priority", "status", "team_id",
        "assigned_to", "sla_policy_id", "first_response_due_at",
        "resolution_due_at", "first_response_at", "resolved_at", "closed_at",
        "version", "created_at", "updated_at", "archived_at",
    }
    assert required <= cols
