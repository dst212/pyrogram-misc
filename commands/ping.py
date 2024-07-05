import time
from pyrogram import filters


def init(bot, name: str = "ping"):
    @bot.on_message(filters.command(name))
    async def _(bot, m):
        if len(m.command) == 1:
            await m.reply("Pong")
        else:
            start = time.time()
            r = await m.reply("Pong")
            await r.edit(f"Pong ({time.time() - start:.3f}s)")
