from app.services.file_rules import extension_allowed, parse_allowed_extensions, within_size


def test_parse_allowed_extensions_strips_and_lowercases():
    assert parse_allowed_extensions("PDF,png,JPG,jpeg,txt,docx") == {"pdf", "png", "jpg", "jpeg", "txt", "docx"}


def test_extension_allowed_case_insensitive():
    allowed = parse_allowed_extensions("pdf,png,jpg,jpeg,txt,docx")
    assert extension_allowed("report.PDF", allowed)
    assert extension_allowed("anh.JPG", allowed)
    assert not extension_allowed("virus.exe", allowed)
    assert not extension_allowed("noext", allowed)


def test_within_size_boundary():
    assert within_size(10 * 1024 * 1024, 10 * 1024 * 1024)  # exactly at the cap is allowed
    assert not within_size(10 * 1024 * 1024 + 1, 10 * 1024 * 1024)
    assert within_size(0, 10 * 1024 * 1024)
