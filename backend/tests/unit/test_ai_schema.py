"""AI output shapes are validated so malformed/allowlist-violating output is never
applied to a ticket (BR-11, FR-AIC-04)."""

import pytest
from pydantic import ValidationError

from app.ai.schemas import ClassificationOutput, DraftOutput, OUTPUT_SCHEMAS, SummaryOutput


def test_classification_valid_values_accepted():
    out = ClassificationOutput(category="ACCOUNT", priority="HIGH",
                               confidence=0.87, reason="Nghi ngờ vấn đề đăng nhập.")
    assert out.category == "ACCOUNT" and out.priority == "HIGH"


def test_classification_rejects_category_outside_allowlist():
    with pytest.raises(ValidationError):
        ClassificationOutput(category="BACKEND", priority="HIGH", confidence=0.9, reason="x")


def test_classification_rejects_priority_outside_allowlist():
    with pytest.raises(ValidationError):
        ClassificationOutput(category="ACCOUNT", priority="URGENTEST", confidence=0.9, reason="x")


def test_classification_rejects_confidence_out_of_range():
    with pytest.raises(ValidationError):
        ClassificationOutput(category="ACCOUNT", priority="HIGH", confidence=1.5, reason="x")


def test_summary_valid_shapes():
    out = SummaryOutput(problem="Không đăng nhập được", key_points=["Sai mật khẩu"],
                        actions_taken=["Đặt lại"], current_status="Đang chờ xác minh",
                        next_steps=["Chờ khách xác nhận"], warnings=["Cũ"])
    assert out.problem == "Không đăng nhập được"


def test_draft_valid_shapes():
    out = DraftOutput(draft="Chúng tôi đã đặt lại mật khẩu.", tone="thân thiện",
                      assumptions=[], warnings=[])
    assert out.draft.startswith("Chúng tôi")


def test_output_schema_map_covers_all_three_types():
    assert set(OUTPUT_SCHEMAS) == {"CLASSIFICATION", "SUMMARY", "DRAFT_REPLY"}
