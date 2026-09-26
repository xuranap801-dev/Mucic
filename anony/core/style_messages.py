"""Apply the reference bot's consistent blockquote presentation to responses."""

from functools import wraps

from pyrogram.types import Message


def _styled(value):
    if not isinstance(value, str) or not value.strip():
        return value
    if "<blockquote" in value.lower():
        return value
    return f"<blockquote>🌸 {value}</blockquote>"


def install() -> None:
    if getattr(Message, "_mikasa_style_installed", False):
        return

    original_text = Message.reply_text

    @wraps(original_text)
    async def reply_text(self, text, *args, **kwargs):
        return await original_text(self, _styled(text), *args, **kwargs)

    Message.reply_text = reply_text

    original_edit_text = Message.edit_text

    @wraps(original_edit_text)
    async def edit_text(self, text, *args, **kwargs):
        return await original_edit_text(self, _styled(text), *args, **kwargs)

    Message.edit_text = edit_text

    for method_name in ("reply_photo", "reply_video", "reply_animation"):
        original = getattr(Message, method_name)

        @wraps(original)
        async def reply_media(self, *args, _original=original, **kwargs):
            if "caption" in kwargs:
                kwargs["caption"] = _styled(kwargs["caption"])
            return await _original(self, *args, **kwargs)

        setattr(Message, method_name, reply_media)

    Message._mikasa_style_installed = True
