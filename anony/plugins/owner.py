# Copyright (c) 2025 YOUR_GITHUB_USERNAME
# Licensed under the MIT License

"""Owner dashboard for Mikasa Music.

The dashboard is intentionally owner-only and uses callback buttons instead of
exposing management actions in normal group chats. User IDs are resolved to
Telegram names only when the owner opens a page; they are not written back to
MongoDB.
"""

import os
import platform
import re
import time

import psutil
from pyrogram import Client, enums, filters, types
from pyrogram.errors import PasswordHashInvalid, PhoneCodeInvalid, PhoneNumberInvalid, SessionPasswordNeeded

from anony import anon, app, boot, config, db, lang, queue, userbot


PAGE_SIZE = 8
pending_assistant_auth: dict[int, dict] = {}
pending_media: dict[int, str] = {}


def _panel_markup() -> types.InlineKeyboardMarkup:
    b = types.InlineKeyboardButton
    return types.InlineKeyboardMarkup(
        [
            [b("Users", callback_data="owner users 0"), b("Groups", callback_data="owner groups 0")],
            [b("Broadcast", callback_data="owner broadcast"), b("Sudo", callback_data="owner sudo")],
            [b("Blacklist", callback_data="owner blacklist"), b("Assistants", callback_data="owner assistants")],
            [b("Active voice chats", callback_data="owner active"), b("Health", callback_data="owner health")],
            [b("Message previews", callback_data="owner previews")],
            [b("Media settings", callback_data="owner media")],
            [b("Refresh", callback_data="owner home"), b("Close", callback_data="owner close")],
        ]
    )


def _nav_markup(section: str, page: int, total: int) -> types.InlineKeyboardMarkup:
    b = types.InlineKeyboardButton
    last = max((total - 1) // PAGE_SIZE, 0)
    row = []
    if page > 0:
        row.append(b("Previous", callback_data=f"owner {section} {page - 1}"))
    if page < last:
        row.append(b("Next", callback_data=f"owner {section} {page + 1}"))
    rows = [row] if row else []
    rows.append([b("Owner panel", callback_data="owner home")])
    return types.InlineKeyboardMarkup(rows)


def _chat_link(chat) -> str:
    if getattr(chat, "username", None):
        return f"https://t.me/{chat.username}"
    return f"tg://openmessage?chat_id={chat.id}"


def _user_link(user) -> str:
    name = getattr(user, "first_name", None) or getattr(user, "username", None) or str(user.id)
    if getattr(user, "last_name", None):
        name = f"{name} {user.last_name}"
    return f'<a href="tg://user?id={user.id}">{name}</a>'


async def _admin_count(chat_id: int) -> int:
    try:
        return sum(
            1
            async for member in app.get_chat_members(
                chat_id, filter=enums.ChatMembersFilter.ADMINISTRATORS
            )
            if not member.user.is_bot
        )
    except Exception:
        return -1


async def _bot_is_admin(chat_id: int) -> bool:
    try:
        member = await app.get_chat_member(chat_id, app.id)
        return member.status in (
            enums.ChatMemberStatus.ADMINISTRATOR,
            enums.ChatMemberStatus.OWNER,
        )
    except Exception:
        return False


async def _home_text() -> str:
    users = await db.get_users()
    chats = await db.get_chats()
    assistants = len(userbot.clients)
    blocked_users = len(app.bl_users)
    blocked_chats = len(db.blacklisted)
    return (
        "<b>Owner Control Panel</b>\n\n"
        f"Users: <code>{len(users)}</code>\n"
        f"Registered groups: <code>{len(chats)}</code>\n"
        f"Active voice chats: <code>{len(db.active_calls)}</code>\n"
        f"Assistants online: <code>{assistants}</code>\n"
        f"Blocked users: <code>{blocked_users}</code>\n"
        f"Blocked groups: <code>{blocked_chats}</code>\n\n"
        "Choose an action below."
    )


def _duration(seconds: int) -> str:
    seconds = max(0, int(seconds))
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours or parts:
        parts.append(f"{hours}h")
    if minutes or parts:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    return " ".join(parts)


async def _active_calls_page():
    b = types.InlineKeyboardButton
    calls = list(db.active_calls)
    lines = [f"<b>Active voice chats</b>  ({len(calls)} total)\n"]
    rows = []
    for chat_id in calls:
        try:
            chat = await app.get_chat(chat_id)
            current = queue.get_current(chat_id)
            items = queue.get_queue(chat_id)
            title = chat.title or str(chat_id)
            track = getattr(current, "title", None) or "Unknown track"
            state = "playing" if await db.playing(chat_id) else "paused"
            lines.append(
                f"• <a href=\"{_chat_link(chat)}\">{title}</a> — <b>{state}</b>\n"
                f"  Now: {track}\n  Queue: <code>{max(len(items) - 1, 0)}</code>"
            )
            rows.append([b(title[:28], callback_data=f"owner call {chat_id}")])
        except Exception:
            lines.append(f"• <code>{chat_id}</code> — unavailable")
    if not calls:
        lines.append("No active voice chats.")
    rows.append([b("Owner panel", callback_data="owner home")])
    return "\n".join(lines), types.InlineKeyboardMarkup(rows)


async def _health_text() -> str:
    process = psutil.Process(os.getpid())
    try:
        await db.mongo.admin.command("ping")
        mongo = "OK"
    except Exception:
        mongo = "ERROR"
    try:
        ping = f"{await anon.ping()} ms"
    except Exception:
        ping = "unknown"
    memory = process.memory_info().rss / 1024**2
    disk = psutil.disk_usage("/")
    return (
        "<b>System health</b>\n\n"
        f"Uptime: <code>{_duration(time.time() - boot)}</code>\n"
        f"CPU: <code>{psutil.cpu_percent(interval=0.1):.1f}%</code>\n"
        f"RAM: <code>{memory:.1f} MB</code>\n"
        f"Disk: <code>{disk.used / disk.total * 100:.1f}%</code>\n"
        f"Platform: <code>{platform.system()}</code>\n"
        f"Python: <code>{platform.python_version()}</code>\n"
        f"MongoDB: <b>{mongo}</b>\n"
        f"Voice assistant ping: <code>{ping}</code>"
    )


async def _users_page(page: int):
    users = await db.get_users()
    page = max(0, page)
    items = users[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]
    lines = [f"<b>Users</b>  ({len(users)} total)\n"]
    for index, user_id in enumerate(items, page * PAGE_SIZE + 1):
        try:
            user = await app.get_users(user_id)
            lines.append(f"{index}. {_user_link(user)} <code>{user_id}</code>")
            rows_button = types.InlineKeyboardButton(
                (getattr(user, "first_name", None) or str(user_id))[:35],
                callback_data=f"owner user {user_id}",
            )
        except Exception:
            lines.append(f"{index}. <code>{user_id}</code> (unavailable)")
            rows_button = types.InlineKeyboardButton(
                str(user_id), callback_data=f"owner user {user_id}"
            )
        if index == page * PAGE_SIZE + 1:
            user_rows = []
        user_rows.append([rows_button])
    if not items:
        lines.append("No registered users found.")
        user_rows = []
    nav = _nav_markup("users", page, len(users))
    return "\n".join(lines), types.InlineKeyboardMarkup(user_rows + nav.inline_keyboard)


async def _user_detail(user_id: int):
    b = types.InlineKeyboardButton
    try:
        user = await app.get_users(user_id)
        blocked = user_id in app.bl_users
        text = (
            f"<b>User profile</b>\n\n"
            f"Name: {_user_link(user)}\n"
            f"ID: <code>{user_id}</code>\n"
            f"Username: @{user.username if user.username else 'none'}\n"
            f"Status: <b>{'BLOCKED' if blocked else 'ACTIVE'}</b>"
        )
        action = "Unblock" if blocked else "Block"
        action_data = f"owner unblock {user_id}" if blocked else f"owner block {user_id}"
        markup = types.InlineKeyboardMarkup(
            [[b(action, callback_data=action_data)], [b("Back to users", callback_data="owner users 0")]]
        )
        return text, markup
    except Exception as exc:
        return f"Unable to load user <code>{user_id}</code>: {type(exc).__name__}", types.InlineKeyboardMarkup(
            [[b("Back to users", callback_data="owner users 0")]]
        )


async def _groups_page(page: int):
    chats = await db.get_chats()
    page = max(0, page)
    items = chats[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]
    rows = []
    lines = [f"<b>Registered groups</b>  ({len(chats)} total)\n"]
    for index, chat_id in enumerate(items, page * PAGE_SIZE + 1):
        try:
            chat = await app.get_chat(chat_id)
            title = chat.title or str(chat_id)
            bot_admin = "admin" if await _bot_is_admin(chat_id) else "not admin"
            lines.append(f"{index}. <a href=\"{_chat_link(chat)}\">{title}</a> — {bot_admin}")
            rows.append([types.InlineKeyboardButton(title[:35], callback_data=f"owner group {chat_id}")])
        except Exception:
            lines.append(f"{index}. <code>{chat_id}</code> (unavailable)")
    if not items:
        lines.append("No registered groups found.")
    nav = _nav_markup("groups", page, len(chats))
    return "\n".join(lines), types.InlineKeyboardMarkup(rows + nav.inline_keyboard)


async def _group_detail(chat_id: int):
    b = types.InlineKeyboardButton
    try:
        chat = await app.get_chat(chat_id)
        admins = await _admin_count(chat_id)
        bot_admin = await _bot_is_admin(chat_id)
        title = chat.title or str(chat_id)
        username = f"@{chat.username}" if chat.username else "private group"
        text = (
            f"<b><a href=\"{_chat_link(chat)}\">{title}</a></b>\n"
            f"ID: <code>{chat_id}</code>\n"
            f"Username: {username}\n"
            f"Human admins: <code>{admins if admins >= 0 else 'unknown'}</code>\n"
            f"Bot status: <b>{'ADMIN' if bot_admin else 'NOT ADMIN'}</b>\n"
            f"Members: <code>{getattr(chat, 'members_count', 'unknown')}</code>"
        )
    except Exception as exc:
        text = f"Unable to load group <code>{chat_id}</code>: {type(exc).__name__}"
    return text, types.InlineKeyboardMarkup(
        [[b("Back to groups", callback_data="owner groups 0"), b("Owner panel", callback_data="owner home")]]
    )


@app.on_message(filters.command(["owner", "panel", "dashboard"]) & filters.private & filters.user(app.owner))
async def owner_panel(_, message: types.Message):
    await message.reply_text(await _home_text(), reply_markup=_panel_markup())


@app.on_callback_query(filters.regex(r"^owner") & filters.user(app.owner))
async def owner_callbacks(_, query: types.CallbackQuery):
    data = query.data.split(maxsplit=2)
    action = data[1] if len(data) > 1 else "home"
    await query.answer()

    if action == "close":
        return await query.message.delete()
    if action == "home":
        return await query.edit_message_text(await _home_text(), reply_markup=_panel_markup())
    if action == "active":
        text, markup = await _active_calls_page()
        return await query.edit_message_text(text, reply_markup=markup)
    if action == "health":
        markup = types.InlineKeyboardMarkup(
            [[types.InlineKeyboardButton("Refresh", callback_data="owner health")],
             [types.InlineKeyboardButton("Owner panel", callback_data="owner home")]]
        )
        return await query.edit_message_text(await _health_text(), reply_markup=markup)
    if action == "call":
        chat_id = int(data[2])
        current = queue.get_current(chat_id)
        items = queue.get_queue(chat_id)
        title = getattr(current, "title", None) if current else "Nothing is playing"
        playing = await db.playing(chat_id)
        status = "Playing" if playing else "Paused"
        text = (
            f"<b>Voice chat control</b>\n\n"
            f"Group: <code>{chat_id}</code>\n"
            f"Status: <b>{status}</b>\n"
            f"Now: {title}\n"
            f"Queue items: <code>{max(len(items) - 1, 0)}</code>"
        )
        markup = types.InlineKeyboardMarkup([
            [types.InlineKeyboardButton("Pause", callback_data=f"owner pause {chat_id}"),
             types.InlineKeyboardButton("Resume", callback_data=f"owner resume {chat_id}")],
            [types.InlineKeyboardButton("Skip", callback_data=f"owner skip {chat_id}"),
             types.InlineKeyboardButton("Stop", callback_data=f"owner stop {chat_id}")],
            [types.InlineKeyboardButton("Back", callback_data="owner active")],
        ])
        return await query.edit_message_text(text, reply_markup=markup)
    if action in ("pause", "resume", "skip", "stop"):
        chat_id = int(data[2])
        try:
            if action == "pause":
                await anon.pause(chat_id)
            elif action == "resume":
                await anon.resume(chat_id)
            elif action == "skip":
                await anon.play_next(chat_id)
            else:
                await anon.stop(chat_id)
            await query.answer(f"{action.title()} completed.", show_alert=True)
        except Exception as exc:
            await query.answer(f"Control failed: {type(exc).__name__}", show_alert=True)
        current = queue.get_current(chat_id)
        items = queue.get_queue(chat_id)
        status = "Playing" if await db.playing(chat_id) else "Paused"
        text = (
            f"<b>Voice chat control</b>\n\nGroup: <code>{chat_id}</code>\n"
            f"Status: <b>{status}</b>\nNow: {getattr(current, 'title', None) if current else 'Nothing is playing'}\n"
            f"Queue items: <code>{max(len(items) - 1, 0)}</code>"
        )
        markup = types.InlineKeyboardMarkup([
            [types.InlineKeyboardButton("Pause", callback_data=f"owner pause {chat_id}"),
             types.InlineKeyboardButton("Resume", callback_data=f"owner resume {chat_id}")],
            [types.InlineKeyboardButton("Skip", callback_data=f"owner skip {chat_id}"),
             types.InlineKeyboardButton("Stop", callback_data=f"owner stop {chat_id}")],
            [types.InlineKeyboardButton("Back", callback_data="owner active")],
        ])
        return await query.edit_message_text(text, reply_markup=markup)
    if action == "user":
        text, markup = await _user_detail(int(data[2]))
        return await query.edit_message_text(text, reply_markup=markup)
    if action in ("block", "unblock"):
        user_id = int(data[2])
        if action == "block":
            await db.add_blacklist(user_id)
            app.bl_users.add(user_id)
            notice = "User blocked."
        else:
            if user_id in app.bl_users:
                app.bl_users.discard(user_id)
            await db.del_blacklist(user_id)
            notice = "User unblocked."
        await query.answer(notice, show_alert=True)
        text, markup = await _user_detail(user_id)
        return await query.edit_message_text(text, reply_markup=markup)
    if action == "users":
        page = int(data[2]) if len(data) > 2 else 0
        text, markup = await _users_page(page)
        return await query.edit_message_text(text, reply_markup=markup)
    if action == "groups":
        page = int(data[2]) if len(data) > 2 else 0
        text, markup = await _groups_page(page)
        return await query.edit_message_text(text, reply_markup=markup)
    if action == "group":
        text, markup = await _group_detail(int(data[2]))
        return await query.edit_message_text(text, reply_markup=markup)
    if action == "sudo":
        sudoers = await db.get_sudoers()
        text = "<b>Sudo users</b>\n\nOwner: <code>{}</code>\n".format(config.OWNER_ID)
        if sudoers:
            for user_id in sudoers:
                try:
                    text += f"\n- {_user_link(await app.get_users(user_id))}"
                except Exception:
                    text += f"\n- <code>{user_id}</code>"
        else:
            text += "\nNo sudo users configured."
        markup = types.InlineKeyboardMarkup([[types.InlineKeyboardButton("Back", callback_data="owner home")]])
        return await query.edit_message_text(text, reply_markup=markup)
    if action == "blacklist":
        text = (
            "<b>Blacklist management</b>\n\n"
            f"Blocked users: <code>{len(app.bl_users)}</code>\n"
            f"Blocked groups: <code>{len(db.blacklisted)}</code>\n\n"
            "Use these commands with a user ID, username or group ID:\n"
            "<code>/blacklist @user</code>\n"
            "<code>/unblacklist @user</code>"
        )
        markup = types.InlineKeyboardMarkup([[types.InlineKeyboardButton("Back", callback_data="owner home")]])
        return await query.edit_message_text(text, reply_markup=markup)
    if action == "broadcast":
        text = (
            "<b>Broadcast</b>\n\n"
            "Reply to the message you want to send, then use:\n"
            "<code>/broadcast</code> — groups only\n"
            "<code>/broadcast -user</code> — groups and users\n"
            "<code>/broadcast -copy</code> — copy instead of forward\n\n"
            "This button only opens instructions; it does not send anything."
        )
        markup = types.InlineKeyboardMarkup([[types.InlineKeyboardButton("Back", callback_data="owner home")]])
        return await query.edit_message_text(text, reply_markup=markup)
    if action == "previews":
        text = (
            "<b>✦ ᴍɪᴋᴀsᴀ ᴍᴜsɪᴄ — Message previews</b>\n\n"
            "<b>Welcome message</b>\n"
            "<blockquote>🎧 <b>✦ ᴍɪᴋᴀsᴀ ᴍᴜsɪᴄ ✦</b>\n"
            "Your group just got a new soundtrack.\n\n"
            "<i>Search it. Queue it. Feel it.</i>\n"
            "Use <code>/play &lt;song name&gt;</code> to begin.</blockquote>\n\n"
            "<b>Now playing</b>\n"
            "<blockquote>✦ <b>NOW PLAYING</b>\n"
            "🎧 <a href=\"https://youtube.com\">Song title</a>\n\n"
            "<b>Duration</b> · <code>03:42</code>\n"
            "<b>Requested by</b> · <i>the requester</i>\n\n"
            "<i>ᴍɪᴋᴀsᴀ ᴍᴜsɪᴄ • keeping your call alive</i></blockquote>\n\n"
            "<b>Queue message</b>\n"
            "<blockquote>✦ <b>ADDED TO QUEUE · #2</b>\n"
            "🎶 <u>Next song</u>\n"
            "<b>Duration</b> · <code>04:10</code>\n"
            "<i>Tap Play Now whenever you want to jump the line.</i></blockquote>\n\n"
            "<b>Supported Telegram formatting</b>: <b>bold</b>, <i>italic</i>, "
            "<u>underline</u>, <s>strike</s>, <code>monospace</code>, and blockquotes."
        )
        markup = types.InlineKeyboardMarkup(
            [[types.InlineKeyboardButton("Back", callback_data="owner home")]]
        )
        return await query.edit_message_text(text, reply_markup=markup)
    if action == "assistants":
        names = []
        for client in userbot.clients:
            names.append(f"- {getattr(client, 'mention', getattr(client, 'name', 'assistant'))} (<code>{client.id}</code>)")
        text = (
            "<b>Music assistants</b>\n\n"
            f"Online: <code>{len(userbot.clients)}</code>\n"
            + ("\n".join(names) if names else "No assistant is online.")
            + "\n\nCurrent version uses SESSION/SESSION2/SESSION3 from .env."
        )
        markup = types.InlineKeyboardMarkup([
            [types.InlineKeyboardButton("Add assistant session", callback_data="owner addassistant")],
            [types.InlineKeyboardButton("Back", callback_data="owner home")],
        ])
        return await query.edit_message_text(text, reply_markup=markup)
    if action == "addassistant":
        pending_assistant_auth.pop(query.from_user.id, None)
        pending_assistant_auth[query.from_user.id] = {"stage": "phone"}
        await query.message.reply_text(
            "<b>Add assistant session</b>\n\n"
            "Send a dedicated Telegram account phone number in international format.\n"
            "Example: <code>+919876543210</code>\n\n"
            "The phone, OTP, and optional 2FA password are used only in memory and are deleted after processing."
        )
        return await query.answer("Send the assistant phone number")
    if action == "media":
        buttons = types.InlineKeyboardMarkup([
            [types.InlineKeyboardButton("Start", callback_data="owner media_start"),
             types.InlineKeyboardButton("Help", callback_data="owner media_help")],
            [types.InlineKeyboardButton("Play", callback_data="owner media_play"),
             types.InlineKeyboardButton("Queue", callback_data="owner media_queue")],
            [types.InlineKeyboardButton("Dashboard", callback_data="owner media_dashboard"),
             types.InlineKeyboardButton("Games", callback_data="owner media_games")],
            [types.InlineKeyboardButton("Ping", callback_data="owner media_ping"),
             types.InlineKeyboardButton("Back", callback_data="owner home")],
            [types.InlineKeyboardButton("Back", callback_data="owner home")],
        ])
        return await query.edit_message_text(
            "<b>Media settings</b>\n\nChoose a command, then send one photo, video, GIF, or sticker.",
            reply_markup=buttons,
        )
    if action.startswith("media_"):
        command = action[6:]
        pending_media[query.from_user.id] = command
        return await query.answer(f"Now send media for /{command}", show_alert=True)


@app.on_callback_query(filters.regex(r"^owner") & ~filters.user(app.owner))
async def owner_denied(_, query: types.CallbackQuery):
    await query.answer("Owner only panel.", show_alert=True)


@app.on_message(filters.private & filters.text & filters.user(app.owner))
async def assistant_auth_messages(_, message: types.Message):
    state = pending_assistant_auth.get(message.from_user.id)
    if not state:
        return
    value = (message.text or "").strip()
    owner_id = message.from_user.id
    try:
        await message.delete()
    except Exception:
        pass
    client = state.get("client")
    try:
        if state["stage"] == "phone":
            if not re.fullmatch(r"\+[1-9]\d{7,14}", value):
                return await app.send_message(owner_id, "Use international format, for example <code>+919876543210</code>.")
            client = Client(
                f"assistant-generator-{owner_id}",
                api_id=config.API_ID,
                api_hash=config.API_HASH,
                in_memory=True,
            )
            await client.connect()
            sent = await client.send_code(value)
            pending_assistant_auth[owner_id] = {
                "stage": "code",
                "client": client,
                "phone": value,
                "phone_code_hash": sent.phone_code_hash,
            }
            return await app.send_message(owner_id, "Telegram OTP sent. Send it here; this message will be deleted.")
        if state["stage"] == "code":
            try:
                await client.sign_in(state["phone"], state["phone_code_hash"], value.replace(" ", ""))
            except SessionPasswordNeeded:
                state["stage"] = "2fa"
                return await app.send_message(owner_id, "Two-step verification is enabled. Send your Telegram 2FA password.")
        elif state["stage"] == "2fa":
            await client.check_password(value)
        else:
            return
        session_string = await client.export_session_string()
        await client.disconnect()
        pending_assistant_auth.pop(owner_id, None)
        if not await userbot.add_runtime_session(session_string):
            return await app.send_message(owner_id, "All assistant slots are already active. Session was not saved.")
        await db.save_assistant_session(owner_id, session_string)
        await app.send_message(
            owner_id,
            "<b>Assistant added successfully.</b>\n\n"
            "It is active now and will load automatically after the next restart. "
            "Phone, OTP, and 2FA password were not saved.",
        )
    except (PhoneNumberInvalid, PhoneCodeInvalid, PasswordHashInvalid) as exc:
        pending_assistant_auth.pop(owner_id, None)
        if client:
            try:
                await client.disconnect()
            except Exception:
                pass
        await app.send_message(owner_id, f"Authentication failed: {type(exc).__name__}. Start again from the owner panel.")
    except Exception:
        pending_assistant_auth.pop(owner_id, None)
        if client:
            try:
                await client.disconnect()
            except Exception:
                pass
        await app.send_message(owner_id, "Session generation failed. No credentials were saved.")


@app.on_message(
    (filters.private & (filters.photo | filters.video | filters.animation | filters.sticker))
    & filters.user(app.owner)
)
async def owner_media_message(_, message: types.Message):
    command = pending_media.pop(message.from_user.id, None)
    if not command:
        return
    if message.photo:
        media_type, file_id = "photo", message.photo.file_id
    elif message.video:
        media_type, file_id = "video", message.video.file_id
    elif message.animation:
        media_type, file_id = "animation", message.animation.file_id
    else:
        media_type, file_id = "sticker", message.sticker.file_id
    await db.save_command_media(command, media_type, file_id)
    await message.reply_text(f"✅ /{command} media saved as {media_type}.")
