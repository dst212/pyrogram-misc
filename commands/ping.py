from pyrogram import filters


def init(bot, name: str = "ping"):
    @bot.on_message(filters.command(name))
    async def _(bot, m):
        await m.reply("Pong")
