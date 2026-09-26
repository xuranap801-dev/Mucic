# Owner Panel

The owner can open the private inline dashboard with `/owner`, `/panel`, or `/dashboard`.

## Dashboard buttons

- **Users**: paginated registered-user list with Telegram name links, IDs, profile details, and block/unblock controls.
- **Groups**: paginated registered-group list with group links and the bot's admin/not-admin status. Opening a group shows the human administrator count, member count, group ID, username, and bot status.
- **Broadcast**: opens the safe broadcast instructions. To send a broadcast, reply to the source message and use `/broadcast`, `/broadcast -user`, or `/broadcast -copy`.
- **Sudo**: shows the owner and configured sudo users.
- **Blacklist**: shows blocked-user and blocked-group counts and the existing blacklist commands.
- **Assistants**: shows currently online music assistants and includes an owner-only **Add assistant session** flow. It accepts a phone number, Telegram OTP, and optional 2FA password in private chat, keeps inputs in memory only, deletes input messages, activates the assistant immediately, and persists only the generated session in MongoDB for restart recovery. A Render `SESSION` variable is optional.
- **Active voice chats**: lists currently active calls, current track, queue count, and owner-only Pause, Resume, Skip, and Stop controls.
- **Health**: shows process uptime, CPU/RAM/disk usage, platform/Python versions, MongoDB ping status, and assistant ping.
- **Message previews**: shows sample `Mikasa Music` start, now-playing, queue, and formatting previews using Telegram HTML styles such as bold, italic, underline, monospace, and blockquotes.
- **Games Zone**: `/games` or `/game` opens the supplied 16-game catalog with virtual-coin balances and a leaderboard. It has no real-money betting, deposits, withdrawals, or payment integration.
- **Moderation**: group admins can use `/ban`, `/unban`, `/kick`, `/mute`, `/unmute`, `/lock`, and `/unlock` by replying to a user or providing a username/user ID.

The display name defaults to `ᴍɪᴋᴀsᴀ ᴍᴜsɪᴄ` and can be changed through the `BOT_NAME` environment variable. Telegram's actual bot username remains the username configured through BotFather.

All dashboard callbacks and session-generation messages are restricted to `OWNER_ID`. Phone, OTP, and 2FA values are not written to MongoDB or GitHub. The generated session is stored in the configured MongoDB database so the assistant can recover after restart; never share it or commit it to the repository.
