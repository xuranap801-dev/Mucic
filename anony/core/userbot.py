# Copyright (c) 2025 YOUR_GITHUB_USERNAME
# Licensed under the MIT License.
# This file is part of Mikasa Music


from pyrogram import Client

from anony import config, logger


class Userbot(Client):
    def __init__(self):
        """
        Initializes the userbot with multiple clients.

        This method sets up clients for the userbot using predefined session strings.
        Each client is assigned a unique name based on the key in the `clients` dictionary.
        """
        self.clients = []
        clients = {"one": "SESSION1", "two": "SESSION2", "three": "SESSION3"}
        for key, string_key in clients.items():
            name = f"AnonyUB{key[-1]}"
            session = getattr(config, string_key)
            setattr(
                self,
                key,
                Client(
                    name=name,
                    api_id=config.API_ID,
                    api_hash=config.API_HASH,
                    session_string=session,
                ),
            )

    async def boot_client(self, num: int, ub: Client):
        """
        Boot a client and perform initial setup.
        Args:
            num (int): The client number to boot (1, 2, or 3).
            ub (Client): The userbot client instance.
        Raises:
            SystemExit: If the client fails to send a message in the log group.
        """
        clients = {
            1: self.one,
            2: self.two,
            3: self.three,
        }
        client = clients[num]
        await client.start()
        try:
            await client.send_message(config.LOGGER_ID, "Assistant Started")
        except Exception:
            raise SystemExit(f"Assistant {num} failed to send message in log group.")

        client.id = ub.me.id
        client.name = ub.me.first_name
        client.username = ub.me.username
        client.mention = ub.me.mention
        self.clients.append(client)
        if config.SUPPORT_CHANNEL and "your_support_" not in config.SUPPORT_CHANNEL:
            try:
                await ub.join_chat(config.SUPPORT_CHANNEL)
            except Exception:
                pass
        logger.info(f"Assistant {num} started as @{client.username}")

    async def boot(self):
        """
        Asynchronously starts the assistants.
        """
        if config.SESSION1:
            await self.boot_client(1, self.one)
        if config.SESSION2:
            await self.boot_client(2, self.two)
        if config.SESSION3:
            await self.boot_client(3, self.three)

    async def add_runtime_session(self, session: str) -> bool:
        """Start the first available assistant slot from an owner-generated session."""
        for num, key in ((1, "one"), (2, "two"), (3, "three")):
            slot = getattr(self, key)
            if any(client is slot for client in self.clients):
                continue
            slot = Client(
                name=f"AnonyUB{num}",
                api_id=config.API_ID,
                api_hash=config.API_HASH,
                session_string=session,
            )
            setattr(self, key, slot)
            await self.boot_client(num, slot)
            return True
        return False

    async def exit(self):
        """
        Asynchronously stops the assistants.
        """
        if config.SESSION1:
            await self.one.stop()
        if config.SESSION2:
            await self.two.stop()
        if config.SESSION3:
            await self.three.stop()
        logger.info("Assistants stopped.")
