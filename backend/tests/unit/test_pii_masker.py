"""PII masking for outbound model contexts (SRS NFR-PRI-02/03, design spec 7.2)."""

from app.ai.pii_masker import mask_text


def test_masks_a_single_email_to_a_numbered_placeholder():
    assert mask_text("Liên hệ abc.def@example.com.vn để được hỗ trợ.") == \
        "Liên hệ [EMAIL-1] để được hỗ trợ."


def test_masks_multiple_emails_with_independent_numbering():
    out = mask_text("a@b.com và c@d.com")
    assert out == "[EMAIL-1] và [EMAIL-2]"


def test_masks_vietnamese_phone_numbers_numbered():
    out = mask_text("SĐT 0912 345 678 và +84 912345679")
    assert "[PHONE-1]" in out and "[PHONE-2]" in out


def test_does_not_touch_plain_text_or_already_masked_placeholders():
    raw = "mã vé TK-20260902, ngày 2024, vui lòng kiểm tra [EMAIL-1]"
    assert mask_text(raw) == raw


def test_masks_email_and_phone_in_the_same_text():
    out = mask_text("email a@b.com, gọi 0388.123.456")
    assert out == "email [EMAIL-1], gọi [PHONE-1]"


def test_mask_is_idempotent():
    once = mask_text("a@b.com +84 912 345 678")
    assert mask_text(once) == once
