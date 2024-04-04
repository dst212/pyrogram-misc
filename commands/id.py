from pyrogram import filters


def init(bot, name: str = "id"):
    @bot.on_message(filters.command(name))
    async def _(bot, m):
        sender_id = (m.from_user or m.sender_chat).id
        await m.reply(
            f"<b>Chat:</b> <code>{m.chat.id}</code>\n"
            f"<b>Sender:</b> <code>{sender_id}</code>\n"
            f"<b>Message:</b> <code>{m.id}</code>\n"
            + (f"<b>Reply to:</b> <code>{m.reply_to_message_id}</code>\n"
               + (f"<b>Reply to sender:</b> <code>{(m.reply_to_message.from_user or m.reply_to_message.sender_chat).id}</code>\n"
                  if m.reply_to_message.from_user else "")
                if m.reply_to_message_id else "")
            + (f"<b>Top message:</b> <code>{m.reply_to_top_message_id}</code>"
                if m.reply_to_top_message_id else "")
        )
