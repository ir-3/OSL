from discord.ext import commands


class Misc:
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def ping(self, ctx):
        """ Check my connection time to Discord. """
        await ctx.send(f":ping_pong: {self.bot.latency*1000:.0f}ms")


def setup(bot):
    bot.add_cog(Misc(bot))
