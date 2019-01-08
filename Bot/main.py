from discord.ext import commands
import discord
# noinspection PyUnresolvedReferences
import utils
# noinspection PyUnresolvedReferences
import config
from collections import deque
from datetime import datetime
import traceback
import os
import asyncpg


class OSL(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=self.prefix,
            status=discord.Status.idle,
            activity=discord.Activity(type=discord.ActivityType.watching, name="Booting..."),
            reconnect=True,
            case_insensitive=True
        )
        self.osl = 514593990704889856
        self.add_check(self.cmd_check)
        self.blacklist = {}
        self.prepared = False
        self.logs = deque(maxlen=5000)
        self.config = config
        self.log("Initialized.")
        self.load_extension("jishaku")
        self.log("Loaded jishaku.")

    async def is_owner(self, user):
        return user.id in self.config.owners

    # Error handlers

    async def on_error(self, event_method, *args, **kwargs):
        exc = traceback.format_exc().split("\n")[-2]
        self.log(f"Error in {event_method}: {exc}")
        await self.http.send_message(514884538703282201, f"Error in {event_method}:```\n{traceback.format_exc()}\n```")

    async def on_command_error(self, ctx, exc):
        if isinstance(exc, commands.CommandOnCooldown):
            await ctx.send(f"Command is on cool down. Try again in {exc.retry_after:.0f}s.")
            self.log(f"{ctx.author}: Command on cool down. Retry {exc.retry_after:.0f}s")
            return
        elif isinstance(exc, utils.Blacklisted):
            await ctx.send(exc)
        elif isinstance(exc, (commands.NotOwner, commands.CheckFailure, commands.MissingPermissions)):
            await ctx.send("You aren't allowed to do that.")
        elif isinstance(exc, commands.UserInputError):
            await ctx.invoke(self.get_command("help"), *ctx.command.qualified_name.split(" "))
        else:
            await ctx.send("An error occurred while performing this command.")
            exc = getattr(exc, "original", exc)
            await self.http.send_message(
                514884538703282201,
                ("```ini\n"
                 "[Error Occurred]\n"
                 f"Time: {datetime.utcnow().strftime('%m/%d:%y @ %H:%M:%S')}\n"
                 f"Invoker: {ctx.author}\n"
                 f"Channel: #{ctx.channel}\n"
                 f"Invocation: {ctx.message.content}\n\n"
                 "[Exception]\n"
                 f"{''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))}\n"
                 "```")
            )
        ctx.command.reset_cooldown(ctx)
        self.log(f"{ctx.author}: {ctx.message}")

    # misc

    def log(self, msg):
        self.logs.append(f"[{datetime.utcnow().strftime('%H:%M:%S')}] {msg}")
        print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] {msg}")

    async def prefix(self, bot, message):
        if self.prepared:
            return commands.when_mentioned_or("!", "osl ")(bot, message)
        return "nothing is ready yet tm"

    async def cmd_check(self, ctx):
        if ctx.guild is None:
            raise commands.NoPrivateMessage()
        if ctx.author.id in self.blacklist:
            raise utils.Blacklisted()
        return True

    # events

    def run(self):
        for module in os.listdir("modules"):
            if module.endswith(".py"):
                try:
                    self.load_extension(f"modules.{module[:-3]}")
                    self.log(f"Loaded {module}")
                except Exception as e:
                    self.log(f"Failed to load {module} [{type(e).__name__}: {e}]")
        self.log("Modules prepared, beginning database preperations.")
        loop = self.loop
        try:
            loop.run_until_complete(self.start())
        except KeyboardInterrupt:
            loop.run_until_complete(self.logout())

    async def start(self):
        # noinspection PyAttributeOutsideInit
        self.db = await asyncpg.create_pool(**self.config.database)
        self.log("Connected to the database.")

        with open("setup.sql") as f:
            await self.db.execute(f.read())

        for userid, reason in await self.db.fetch("SELECT userid, reason FROM blacklist;"):
            self.log(f"User id {userid} is blacklisted for {reason}")
            self.blacklist[userid] = reason

        self.log("Databse initialized. Beginning connection to Discord.")
        await self.login(self.config.token)
        await self.connect()

    async def on_connect(self):
        self.log("Successfully connected. Finalizing.")

    async def on_ready(self):
        for user in self.blacklist.keys():
            if not self.get_user(user):
                self.blacklist.pop(user)
        self.log("Setup complete. Now listening to commands.")
        self.prepared = True
        await self.change_presence(status=discord.Status.online, activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="osl help"
        ))

    async def logout(self):
        self.log("Flushing to database.")
        await self.db.execute("DELETE FROM blacklist;")
        await self.db.executemany("INSERT INTO blacklist VALUES ($1, $2);", self.blacklist.items())
        await self.db.close()
        self.log("Shutting down...")
        for extension in tuple(self.extensions):
            try:
                self.unload_extension(extension)
            except:
                pass
        for cog in tuple(self.cogs):
            try:
                self.remove_cog(cog)
            except:
                pass
        for voice in self.voice_clients:
            try:
                await voice.disconnect()
            except:
                pass
        if self.ws is not None and self.ws.open:
            await self.ws.close()
        await self.http.close()


if __name__ == "__main__":
    osl = OSL()
    osl.run()
