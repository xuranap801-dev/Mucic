"""Basic group moderation commands for Mikasa Music."""

from pyrogram import enums, filters, types

from anony import app, lang
from anony.helpers import admin_check, utils


async def _target(message: types.Message):
    return await utils.extract_user(message)


@app.on_message(filters.command(["ban", "unban", "kick", "mute", "unmute"]) & filters.group & ~app.bl_users)
@lang.language()
@admin_check
async def moderation(_, message: types.Message):
    user = await _target(message)
    if not user:
        return await message.reply_text("Reply to a user's message or provide @username/user ID.")
    if user.id == app.id:
        return await message.reply_text("I cannot moderate myself.")
    action = message.command[0].lower()
    try:
        if action in {"ban", "kick"}:
            await app.ban_chat_member(message.chat.id, user.id)
            text = f"Banned {user.mention}."
        elif action == "unban":
            await app.unban_chat_member(message.chat.id, user.id)
            text = f"Unbanned {user.mention}."
        elif action == "mute":
            await app.restrict_chat_member(
                message.chat.id,
                user.id,
                permissions=types.ChatPermissions(can_send_messages=False),
            )
            text = f"Muted {user.mention}."
        else:
            await app.restrict_chat_member(
                message.chat.id,
                user.id,
                permissions=types.ChatPermissions(
                    can_send_messages=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True,
                ),
            )
            text = f"Unmuted {user.mention}."
        await message.reply_text(text)
    except Exception as exc:
        await message.reply_text(f"Moderation failed: {type(exc).__name__}")


@app.on_message(filters.command(["lock", "unlock"]) & filters.group & ~app.bl_users)
@lang.language()
@admin_check
async def chat_lock(_, message: types.Message):
    try:
        locked = message.command[0].lower() == "lock"
        if locked:
            permissions = types.ChatPermissions(can_send_messages=False)
        else:
            permissions = types.ChatPermissions(
                can_send_messages=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
            )
        await app.set_chat_permissions(message.chat.id, permissions)
        await message.reply_text("Group locked." if locked else "Group unlocked.")
    except Exception as exc:
        await message.reply_text(f"Chat permissions update failed: {type(exc).__name__}")
