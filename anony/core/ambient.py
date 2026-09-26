"""Optional ambient messages for registered groups."""

import asyncio
import random

from anony import app, config, db, logger


MESSAGES = (
    "🌸 I’m a little bored… does anyone want to listen to a song with me? 🎶",
    "🧸 Should we play something soft and cozy? ✨",
    "🐰 Music time? I’m ready whenever you are. 🎧",
    "🌙 A tiny reminder: every mood deserves a good song. 💕",
    "🍓 Who wants to add a cute song to the queue? 🎵",
    "🪽 The voice chat feels quiet… shall we fix that with music? 💫",
)


async def ambient_messages_loop() -> None:
    while True:
        await asyncio.sleep(random.randint(config.RANDOM_MESSAGE_MIN, config.RANDOM_MESSAGE_MAX))
        if not config.RANDOM_MESSAGES:
            continue
        try:
            for chat_id in await db.get_chats():
                try:
                    await app.send_message(chat_id, random.choice(MESSAGES))
                except Exception:
                    continue
        except Exception:
            logger.exception("ambient message loop failed")
