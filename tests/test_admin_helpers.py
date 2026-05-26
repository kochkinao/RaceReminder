import pytest
from types import SimpleNamespace

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


def test_safe_admin_text_escapes_html() -> None:
    assert admin._safe_admin_text("<b>x</b> & y") == "&lt;b&gt;x&lt;/b&gt; &amp; y"


def test_build_admin_send_item_escapes_text_payload() -> None:
    message = SimpleNamespace(
        text="/admin_send 123 <b>unsafe</b>",
        caption=None,
        reply_to_message=None,
        photo=None,
        video=None,
        document=None,
        from_user=SimpleNamespace(id=42),
    )

    item = admin._build_admin_send_item(message, batch_id=1)

    assert item.chat_id == 123
    assert item.text == "&lt;b&gt;unsafe&lt;/b&gt;"
