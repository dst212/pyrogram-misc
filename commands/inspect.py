import html
import requests

from pyrogram import filters


def init(bot, name: str = "inspect"):
    @bot.on_message(filters.command(name))
    async def _(bot, m):
        target = m.reply_to_message or m
        output = str(target)
        mode = m.command[1] if len(m.command) > 1 else None
        if len(output) < 4000 and mode == "here":
            await m.reply_text(
                "<pre language=\"json\">"
                f"{html.escape(output)}"
                "</pre>"
            )
        else:
            r = requests.post("https://0x0.st", data={
                "secret": "",
                "expires": "24",
            }, files={
                "file": (f"{target.chat.id}-{target.id}.json", output),
            })
            if r.status_code == 200:
                await m.reply(r.text)
            else:
                raise Exception(f"{r.status_code}: {r.text}")
