# Copyright (c) 2025 YOUR_GITHUB_USERNAME
# Licensed under the MIT License.
# This file is part of Mikasa Music


import asyncio
import signal
import importlib
import os
from contextlib import suppress

from aiohttp import web

from anony import (anon, app, config, db, logger,
                   stop, thumb, userbot, yt)
from anony.plugins import all_modules


async def idle():
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGABRT):
        with suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop_event.set)
    await stop_event.wait()


async def _health(_request):
    return web.json_response({"status": "ok", "service": config.BOT_NAME})


async def start_health_server():
    application = web.Application()
    application.router.add_get("/", _health)
    application.router.add_get("/health", _health)
    runner = web.AppRunner(application)
    await runner.setup()
    port = int(os.getenv("PORT", "10000"))
    await web.TCPSite(runner, "0.0.0.0", port).start()
    logger.info(f"Health server listening on 0.0.0.0:{port}")
    return runner

async def main():
    health_runner = await start_health_server()
    await db.connect()
    await app.boot()
    await userbot.boot()
    if not userbot.clients:
        saved_session = await db.get_assistant_session()
        if saved_session:
            await userbot.add_runtime_session(saved_session)
    await anon.boot()
    await thumb.start()

    for module in all_modules:
        importlib.import_module(f"anony.plugins.{module}")
    logger.info(f"Loaded {len(all_modules)} modules.")

    if config.COOKIES_URL:
        await yt.save_cookies(config.COOKIES_URL)

    sudoers = await db.get_sudoers()
    app.sudoers.update(sudoers)
    app.bl_users.update(await db.get_blacklisted())
    logger.info(f"Loaded {len(app.sudoers)} sudo users.")

    await idle()
    await health_runner.cleanup()
    asyncio.create_task(stop())


if __name__ == "__main__":
    try:
        asyncio.get_event_loop().run_until_complete(main())
    except KeyboardInterrupt:
        pass
