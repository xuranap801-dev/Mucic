"""Virtual-coin Games Zone adapted from the supplied game catalog.

This module intentionally has no real-money betting, payments, deposits, or
withdrawals. Balances are entertainment-only points stored in MongoDB.
"""

from secrets import randbelow

from pyrogram import filters, types

from anony import app, db, lang


GAMES = [
    ("football", "Football Penalty", "⚽", "Take a penalty shot"),
    ("basket", "Basketball Shot", "🏀", "Make the basket"),
    ("dart", "Dart Target", "🎯", "Hit the target"),
    ("bowling", "Bowling Strike", "🎳", "Roll for a strike"),
    ("mines", "Mines", "💣", "Pick a safe tile"),
    ("coinflip", "Coin Flip", "🪙", "Heads or tails"),
    ("color", "Color Prediction", "🎨", "Predict the color"),
    ("crash", "Aviator", "✈️", "Try the multiplier"),
    ("trade", "Futures Trading", "📈", "Predict the market"),
    ("spin", "Lucky Slot Spin", "🎰", "Spin the reels"),
    ("hilo", "High-Low Card", "🃏", "Predict the next card"),
    ("wheel", "Lucky Wheel", "🎡", "Spin the wheel"),
    ("dice", "Dice Game", "🎲", "Roll the dice"),
    ("quiz", "Math Quiz", "🧠", "Solve a quick quiz"),
    ("lucky", "Lucky Number", "🔢", "Pick a number"),
    ("duel", "Coin Duel", "⚔️", "Challenge another player"),
]
GAME_MAP = {slug: (name, icon, description) for slug, name, icon, description in GAMES}
BET_OPTIONS = (10, 50, 100, 500)
STARTING_BALANCE = 1000


def games_menu_markup() -> types.InlineKeyboardMarkup:
    buttons = [
        types.InlineKeyboardButton(f"{icon} {name}", callback_data=f"games open {slug}")
        for slug, (name, icon, _) in GAME_MAP.items()
    ]
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    rows.append([
        types.InlineKeyboardButton("Balance", callback_data="games balance"),
        types.InlineKeyboardButton("Leaderboard", callback_data="games leaderboard"),
    ])
    return types.InlineKeyboardMarkup(rows)


def bet_markup(slug: str) -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup([
        [types.InlineKeyboardButton(f"{bet} coins", callback_data=f"games bet {slug} {bet}") for bet in BET_OPTIONS[:2]],
        [types.InlineKeyboardButton(f"{bet} coins", callback_data=f"games bet {slug} {bet}") for bet in BET_OPTIONS[2:]],
        [types.InlineKeyboardButton("Back to games", callback_data="games menu")],
    ])


def _name(user: types.User) -> str:
    return (user.first_name or "Player")[:64]


async def _ensure_user(chat_id: int, user: types.User):
    collection = db.db.game_users
    await collection.update_one(
        {"chat_id": chat_id, "user_id": user.id},
        {"$setOnInsert": {"name": _name(user), "balance": STARTING_BALANCE, "plays": 0, "wins": 0}},
        upsert=True,
    )
    return collection


async def _balance(chat_id: int, user: types.User) -> int:
    collection = await _ensure_user(chat_id, user)
    row = await collection.find_one({"chat_id": chat_id, "user_id": user.id})
    return int(row.get("balance", STARTING_BALANCE))


def _result(slug: str, bet: int) -> tuple[bool, str, int]:
    roll = randbelow(100)
    if slug == "crash":
        multiplier = 1 + randbelow(300) / 100
        won = multiplier >= 1.75
        return won, f"Multiplier reached <b>{multiplier:.2f}x</b>", int(bet * (multiplier if won else 0))
    if slug == "quiz":
        won = roll < 55
        return won, "Quick quiz result generated.", bet * 2 if won else 0
    if slug in {"football", "basket", "dart", "bowling", "mines", "coinflip", "color", "trade", "spin", "hilo", "wheel", "dice", "lucky", "duel"}:
        won = roll < 48
        return won, "Your virtual round is complete.", bet * 2 if won else 0
    return roll < 50, "Your virtual round is complete.", bet * 2 if roll < 50 else 0


async def _play(chat_id: int, user: types.User, slug: str, bet: int) -> tuple[bool, str, int]:
    collection = await _ensure_user(chat_id, user)
    query = {"chat_id": chat_id, "user_id": user.id}
    row = await collection.find_one(query)
    balance = int(row.get("balance", STARTING_BALANCE))
    if balance < bet:
        return False, "Insufficient virtual coins.", balance
    won, result, payout = _result(slug, bet)
    new_balance = balance - bet + payout
    await collection.update_one(query, {"$set": {"name": _name(user), "balance": new_balance}, "$inc": {"plays": 1, "wins": int(won)}})
    return won, result, new_balance


@app.on_message(filters.command(["games", "game"]) & filters.group & ~app.bl_users)
@lang.language()
async def games_handler(_, message: types.Message):
    await _ensure_user(message.chat.id, message.from_user)
    await message.reply_text(
        "<b>🎮 Mikasa Game Zone</b>\n\nChoose a virtual-coin game. Coins have no cash value.",
        reply_markup=games_menu_markup(),
    )


@app.on_callback_query(filters.regex(r"^games (menu|balance|leaderboard|open|bet)"))
async def games_callback(_, query: types.CallbackQuery):
    if not query.message or not query.message.chat or not query.from_user:
        return await query.answer("Game unavailable.", show_alert=True)
    parts = query.data.split()
    chat_id = query.message.chat.id
    user = query.from_user
    await _ensure_user(chat_id, user)
    action = parts[1]
    if action == "menu":
        await query.message.edit_text("<b>🎮 Game Zone</b>\n\nChoose a virtual-coin game:", reply_markup=games_menu_markup())
        return await query.answer()
    if action == "balance":
        return await query.answer(f"Balance: {_balance(chat_id, user):,} virtual coins", show_alert=True)
    if action == "leaderboard":
        rows = [row async for row in db.db.game_users.find({"chat_id": chat_id}).sort("balance", -1).limit(10)]
        text = "<b>🏆 Game Leaderboard</b>\n\n" + ("\n".join(f"{i}. {row.get('name', 'Player')} — {row.get('balance', 0):,}" for i, row in enumerate(rows, 1)) if rows else "No players yet.")
        await query.message.edit_text(text, reply_markup=games_menu_markup())
        return await query.answer()
    if action == "open" and len(parts) == 3 and parts[2] in GAME_MAP:
        name, icon, description = GAME_MAP[parts[2]]
        await query.message.edit_text(f"<b>{icon} {name}</b>\n\n{description}\n\nBalance: <code>{await _balance(chat_id, user):,}</code> virtual coins\nChoose your stake:", reply_markup=bet_markup(parts[2]))
        return await query.answer()
    if action == "bet" and len(parts) == 4 and parts[2] in GAME_MAP:
        try:
            bet = int(parts[3])
        except ValueError:
            return await query.answer("Invalid bet.", show_alert=True)
        if bet not in BET_OPTIONS:
            return await query.answer("Invalid bet.", show_alert=True)
        won, result, balance = await _play(chat_id, user, parts[2], bet)
        status = "🎉 You won!" if won else "Better luck next time."
        await query.message.edit_text(f"<b>{status}</b>\n\n{result}\nBalance: <code>{balance:,}</code> virtual coins", reply_markup=bet_markup(parts[2]))
        return await query.answer("Win!" if won else "Round complete")
    await query.answer("Unknown game action.", show_alert=True)
