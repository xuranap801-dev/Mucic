# Owner Panel

The owner can open the private inline dashboard with `/owner`, `/panel`, or `/dashboard`.

## Dashboard buttons

- **Users**: paginated registered-user list with Telegram name links, IDs, profile details, and block/unblock controls.
- **Groups**: paginated registered-group list with group links and the bot's admin/not-admin status. Opening a group shows the human administrator count, member count, group ID, username, and bot status.
- **Broadcast**: opens the safe broadcast instructions. To send a broadcast, reply to the source message and use `/broadcast`, `/broadcast -user`, or `/broadcast -copy`.
- **Sudo**: shows the owner and configured sudo users.
- **Blacklist**: shows blocked-user and blocked-group counts and the existing blacklist commands.
- **Assistants**: shows currently online music assistants. The current login method remains `SESSION`, `SESSION2`, and `SESSION3` in `.env`.
- **Active voice chats**: lists currently active calls, current track, queue count, and owner-only Pause, Resume, Skip, and Stop controls.
- **Health**: shows process uptime, CPU/RAM/disk usage, platform/Python versions, MongoDB ping status, and assistant ping.
- **Message previews**: shows sample `Mikasa Music` start, now-playing, queue, and formatting previews using Telegram HTML styles such as bold, italic, underline, monospace, and blockquotes.
- **Games Zone**: `/games` or `/game` opens the supplied 16-game catalog with virtual-coin balances and a leaderboard. It has no real-money betting, deposits, withdrawals, or payment integration.

The display name defaults to `ᴍɪᴋᴀsᴀ ᴍᴜsɪᴄ` and can be changed through the `BOT_NAME` environment variable. Telegram's actual bot username remains the username configured through BotFather.

All dashboard callbacks are restricted to `OWNER_ID`. The panel never asks for a phone number, OTP, 2FA password, bot token, or session string. Dynamic assistant login is intentionally not included in this patch; that should be implemented as a separate security-reviewed feature.
