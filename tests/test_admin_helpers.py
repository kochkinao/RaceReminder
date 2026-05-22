import pytest

from handlers import admin


def test_parse_admin_send_args() -> None:
    chat_id, body = admin._parse_admin_send_args("/admin_send 123456 hello world")
    assert chat_id == 123456
    assert body == "hello world"


def test_parse_admin_send_args_rejects_invalid_input() -> None:
    with pytest.raises(ValueError):
        admin._parse_admin_send_args("/admin_send")

    with pytest.raises(ValueError):
        admin._parse_admin_send_args("/admin_send abc hello")
