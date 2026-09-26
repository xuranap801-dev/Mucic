"""Additional queue and user commands ported to the current Mikasa architecture."""

from datetime import datetime, timezone
from random import shuffle
from collections import deque

from pyrogram import filters, types

from anony import app, anon, db, lang, queue
from anony.helpers import can_manage_vc


@app.on_message(filters.command("replay") & filters.group & ~app.bl_users)
@lang.language()
@can_manage_vc
async def replay(_, message: types.Message):
    if not await db.get_call(message.chat.id):
        return await message.reply_text("Nothing is playing.")
    await anon.replay(message.chat.id)
    await message.reply_text("🔂 Replaying the current track.")


@app.on_message(filters.command("shuffle") & filters.group & ~app.bl_users)
@lang.language()
@can_manage_vc
async def shuffle_queue(_, message: types.Message):
    items = list(queue.queues[message.chat.id])
    if len(items) < 2:
        return await message.reply_text("Not enough queued tracks to shuffle.")
    shuffle(items)
    queue.queues[message.chat.id] = deque(items)
    await message.reply_text(f"🔀 Shuffled {len(items)} queued tracks.")


@app.on_message(filters.command("remove") & filters.group & ~app.bl_users)
@lang.language()
@can_manage_vc
async def remove_queue_item(_, message: types.Message):
    try:
        position = int(message.command[1])
    except (IndexError, ValueError):
        return await message.reply_text("Usage: /remove <queue number>")
    items = queue.queues[message.chat.id]
    if position < 1 or position > len(items):
        return await message.reply_text("That queue position does not exist.")
    items.rotate(-(position - 1))
    removed = items.popleft()
    items.rotate(position - 1)
    await message.reply_text(f"🗑 Removed: <b>{removed.title}</b>")


@app.on_message(filters.command("move") & filters.group & ~app.bl_users)
@lang.language()
@can_manage_vc
async def move_queue_item(_, message: types.Message):
    try:
        source, target = (int(value) for value in message.command[1:3])
        items = list(queue.queues[message.chat.id])
        track = items.pop(source - 1)
        items.insert(target - 1, track)
        queue.queues[message.chat.id] = deque(items)
    except (IndexError, ValueError):
        return await message.reply_text("Usage: /move <from> <to>")
    except Exception:
        return await message.reply_text("Use valid queue positions.")
    await message.reply_text(f"↕️ Moved <b>{track.title}</b> to position {target}.")


@app.on_message(filters.command(["profile", "points", "level", "daily"]) & filters.group & ~app.bl_users)
@lang.language()
async def user_progress(_, message: types.Message):
    if not message.from_user:
        return
    collection = db.db.game_users
    query = {"chat_id": message.chat.id, "user_id": message.from_user.id}
    row = await collection.find_one(query) or {"balance": 1000, "plays": 0, "wins": 0, "daily": ""}
    action = message.command[0].lower()
    if action == "daily":
        today = datetime.now(timezone.utc).date().isoformat()
        if row.get("daily") == today:
            return await message.reply_text("⏳ Daily reward already claimed.")
        await collection.update_one(query, {"$set": {"daily": today}, "$inc": {"balance": 100, "xp": 100}}, upsert=True)
        return await message.reply_text("🎁 Daily reward: <b>+100 coins</b> and <b>+100 XP</b>.")
    if action == "profile":
        return await message.reply_text(
            f"👤 <b>{message.from_user.mention}</b>\nCoins: {row.get('balance', 1000):,}\n"
            f"Plays: {row.get('plays', 0)}\nWins: {row.get('wins', 0)}\nXP: {row.get('xp', 0)}"
        )
    if action == "level":
        return await message.reply_text(f"🎚 Level: <b>{int(row.get('xp', 0)) // 100 + 1}</b>")
    await message.reply_text(f"✨ Points: <b>{row.get('xp', 0)}</b> XP")


@app.on_message(filters.command(["leaderboard", "topusers"]) & filters.group & ~app.bl_users)
@lang.language()
async def user_leaderboard(_, message: types.Message):
    rows = [row async for row in db.db.game_users.find({"chat_id": message.chat.id}).sort("xp", -1).limit(10)]
    text = "🏆 <b>Top users</b>\n\n" + (
        "\n".join(f"{i}. {row.get('name', 'Player')} — {row.get('xp', 0)} XP" for i, row in enumerate(rows, 1))
        if rows else "No user stats yet."
    )
    await message.reply_text(text)
