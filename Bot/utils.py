from discord.ext.commands import Converter, CommandError

# Errors


class Blacklisted(CommandError):
    def __init__(self):
        super().__init__("You are blacklisted from using my commands.")

