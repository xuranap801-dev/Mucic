"""Telegram Bot API helpers for the newer colored inline button styles."""

import aiohttp

from anony import config


def button(text: str, style: str = "primary", *, callback_data: str | None = None, url: str | None = None) -> dict:
    item = {"text": text, "style": style}
    if callback_data is not None:
        item["callback_data"] = callback_data
    if url is not None:
        item["url"] = url
    return item


def start_markup(bot_username: str, private: bool) -> dict:
    rows = [
        [button("➕ Add me to your group", "primary", url=f"https://t.me/{bot_username}?startgroup=true")],
        [button("📚 All Commands", "primary", callback_data="help")],
        [button("💬 Support Group", "success", url=config.SUPPORT_CHAT), button("📢 Channel", "primary", url=config.SUPPORT_CHANNEL)],
    ]
    if private:
        rows.append([button("🌐 Language", "primary", callback_data="language")])
    return {"inline_keyboard": rows}


def playback_markup(chat_id: int) -> dict:
    danger = "danger"
    return {"inline_keyboard": [
        [button("▷", danger, callback_data=f"controls resume {chat_id}"), button("Ⅱ", danger, callback_data=f"controls pause {chat_id}"), button("⥁", danger, callback_data=f"controls replay {chat_id}"), button("▹▹|", danger, callback_data=f"controls skip {chat_id}"), button("□", danger, callback_data=f"controls stop {chat_id}")],
    ]}


async def send_message(chat_id: int, text: str, reply_markup: dict | None = None) -> bool:
    return await _send("sendMessage", {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "reply_markup": reply_markup})


async def edit_reply_markup(chat_id: int, message_id: int, reply_markup: dict) -> bool:
    return await _send("editMessageReplyMarkup", {"chat_id": chat_id, "message_id": message_id, "reply_markup": reply_markup})


async def _send(method: str, payload: dict) -> bool:
    if not config.BOT_TOKEN:
        return False
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"https://api.telegram.org/bot{config.BOT_TOKEN}/{method}", json=payload, timeout=20) as response:
                data = await response.json()
                return bool(data.get("ok"))
    except Exception:
        return False
