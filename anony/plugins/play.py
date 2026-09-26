# Copyright (c) 2025 YOUR_GITHUB_USERNAME
# Licensed under the MIT License.
# This file is part of Mikasa Music


import asyncio
from pathlib import Path

from pyrogram import filters, types

from anony import anon, app, config, db, lang, queue, tg, yt
from anony.helpers import buttons, utils
from anony.helpers._play import checkUB


def playlist_to_queue(chat_id: int, tracks: list) -> str:
    text = "<blockquote expandable>"
    for track in tracks:
        pos = queue.add(chat_id, track)
        text += f"<b>{pos}.</b> {track.title}\n"
    text = text[:1948] + "</blockquote>"
    return text

@app.on_message(
    filters.command(["play", "playforce", "vplay", "vplayforce"])
    & filters.group
    & ~app.bl_users
)
@lang.language()
@checkUB
async def play_hndlr(
    _,
    m: types.Message,
    force: bool = False,
    m3u8: bool = False,
    video: bool = False,
    url: str = None,
    status: types.Message = None,
) -> None:
    sent = status or await m.reply_text(m.lang["play_searching"])
    await sent.edit_text(m.lang["play_searching"])
    custom = await db.get_command_media("play")
    if custom:
        try:
            if custom.get("media_type") == "photo":
                await app.send_photo(m.chat.id, custom["file_id"])
            elif custom.get("media_type") == "video":
                await app.send_video(m.chat.id, custom["file_id"])
            elif custom.get("media_type") == "animation":
                await app.send_animation(m.chat.id, custom["file_id"])
            elif custom.get("media_type") == "sticker":
                await app.send_sticker(m.chat.id, custom["file_id"])
        except Exception:
            pass
    file = None
    mention = m.from_user.mention
    media = tg.get_media(m.reply_to_message) if m.reply_to_message else None
    tracks = []

    if media:
        setattr(sent, "lang", m.lang)
        file = await tg.download(m.reply_to_message, sent)

    elif m3u8:
        file = await tg.process_m3u8(url, sent.id, video)

    elif url:
        if "playlist" in url:
            await sent.edit_text(m.lang["playlist_fetch"])
            try:
                tracks = await asyncio.wait_for(
                    yt.playlist(config.PLAYLIST_LIMIT, mention, url, video), timeout=45
                )
            except asyncio.TimeoutError:
                return await sent.edit_text("❌ Pʟᴀʏʟɪsᴛ ʀᴇǫᴜᴇsᴛ ᴛɪᴍᴇᴅ ᴏᴜᴛ. Please try one song.")

            if not tracks:
                return await sent.edit_text(m.lang["playlist_error"])

            file = tracks[0]
            tracks.remove(file)
            file.message_id = sent.id
        else:
            try:
                file = await asyncio.wait_for(yt.search(url, sent.id, video=video), timeout=30)
            except asyncio.TimeoutError:
                return await sent.edit_text("❌ YᴏᴜTᴜʙᴇ sᴇᴀʀᴄʜ ᴛɪᴍᴇᴅ ᴏᴜᴛ. Please try again.")

        if not file:
            return await sent.edit_text(
                m.lang["play_not_found"].format(config.SUPPORT_CHAT)
            )

    elif len(m.command) >= 2:
        query = " ".join(m.command[1:])
        try:
            file = await asyncio.wait_for(yt.search(query, sent.id, video=video), timeout=30)
        except asyncio.TimeoutError:
            return await sent.edit_text("❌ YᴏᴜTᴜʙᴇ sᴇᴀʀᴄʜ ᴛɪᴍᴇᴅ ᴏᴜᴛ. Please try again.")
        if not file:
            return await sent.edit_text(
                m.lang["play_not_found"].format(config.SUPPORT_CHAT)
            )

    if not file:
        return await sent.edit_text(m.lang["play_usage"])

    if file.duration_sec > config.DURATION_LIMIT:
        return await sent.edit_text(
            m.lang["play_duration_limit"].format(config.DURATION_LIMIT // 60)
        )

    if await db.is_logger():
        await utils.play_log(m, sent.link, file.title, file.duration)

    file.user = mention
    if force:
        queue.force_add(m.chat.id, file)
    else:
        position = queue.add(m.chat.id, file)

        if position != 0 or await db.get_call(m.chat.id):
            await sent.edit_text(
                m.lang["play_queued"].format(
                    position,
                    file.url,
                    file.title,
                    file.duration,
                    m.from_user.mention,
                ),
                reply_markup=buttons.play_queued(
                    m.chat.id, file.id, m.lang["play_now"]
                ),
            )
            if tracks:
                added = playlist_to_queue(m.chat.id, tracks)
                await app.send_message(
                    chat_id=m.chat.id,
                    text=m.lang["playlist_queued"].format(len(tracks)) + added,
                )
            return

    if not file.file_path:
        fname = f"downloads/{file.id}.{'mp4' if video else 'webm'}"
        if Path(fname).exists():
            file.file_path = fname
        else:
            await sent.edit_text(m.lang["play_downloading"])
            try:
                file.file_path = await asyncio.wait_for(
                    yt.download(file.id, video=video), timeout=180
                )
            except asyncio.TimeoutError:
                return await sent.edit_text(
                    "❌ Tʀᴀᴄᴋ ᴅᴏᴡɴʟᴏᴀᴅ ᴛɪᴍᴇᴅ ᴏᴜᴛ. Please try another song or URL."
                )
            if not file.file_path and "sign in to confirm" in yt.last_error.lower():
                return await sent.edit_text(
                    "❌ YᴏᴜTᴜʙᴇ ʙʟᴏᴄᴋᴇᴅ ᴛʜɪs ᴅᴏᴡɴʟᴏᴀᴅ.\n\n"
                    "Owner: add a valid Netscape cookies.txt file URL in Render as <code>COOKIES_URL</code>, then redeploy."
                )

    await anon.play_media(chat_id=m.chat.id, message=sent, media=file)
    if not tracks:
        return
    added = playlist_to_queue(m.chat.id, tracks)
    await app.send_message(
        chat_id=m.chat.id,
        text=m.lang["playlist_queued"].format(len(tracks)) + added,
    )


@app.on_message(
    filters.command(["play", "playforce", "vplay", "vplayforce"])
    & filters.private
)
@lang.language()
async def play_private(_, message: types.Message):
    await message.reply_text(
        "🎧 <b>Music playback works in groups only.</b>\n\n"
        "Add me to a group, make me an admin, add the assistant account, then use:\n"
        "<code>/play song name</code>"
    )
