import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.services import ticket_code


def test_generated_code_shape_and_alphabet():
    for _ in range(50):
        code = ticket_code.generate_ticket_code()
        assert re.fullmatch(r"TK-[A-Z2-7]{8}", code)  # RFC 4648 base32: A-Z + 2-7
