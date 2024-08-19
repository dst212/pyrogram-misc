from ..fun import (
    format_chat,
    chat_name,
    reply_to_buttons,
    button_args,
    can_delete,
    countdown,
    edit_copy,
)

import asyncio

from typing import Iterable

from pyrogram import filters
from pyrogram.errors import MessageNotModified
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)


def init(*args, **kwargs):
    return Init(*args, **kwargs)


class Init:
    def __init__(
        self,
        bot,
        sudo,
        support_chat: (int | Iterable[int]),
        # Feedback-related stuff
        name: (str | list[str]) = "feedback",
        str_help: str = (
            "Provide a feedback alongside the command.\n\n"
            "Examples:\n"
            "<code>/feedback can you add cookies?</code>\n"
            "<code>/feedback the bot exploded, [feature] stopped working</code>\n\n"
            "You may reply with /feedback to a message to forward it too.\n\n"
            "<i>Bot developers are human beings too.\n"
            "Don't harass them. Be kind and respectful, please.</i>"
        ),
        str_sending: str = "Sending the feedback...",
        str_sent: str = (
            "The feedback was sent, thank you!\n"
            "You may get a reply. Please, be patient."
        )
    ):
        cbname = name[0] if isinstance(name, Iterable) else name
        # Feedback-related stuff
        support_topic = None
        if isinstance(support_chat, Iterable):
            support_chat, support_topic = support_chat[0], support_chat[1]

        def admin_reply_button(chat: int, message: int):
            return InlineKeyboardMarkup([[
                InlineKeyboardButton("↖️ Reply", callback_data=f"{sudo.name} send {chat} {message}")
            ]])

        def sent_message_buttons(chat: int, message: int):
            return InlineKeyboardMarkup([[
                InlineKeyboardButton("↖️ Reply", callback_data=f"{sudo.name} send {chat} {message}"),
                InlineKeyboardButton("❌ Delete", callback_data=f"{sudo.name} askdel {chat} {message}"),
            ]])

        def askdel_buttons(chat: int, message: int):
            return InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ Go back", callback_data=f"{sudo.name} btn {chat} {message}"),
                InlineKeyboardButton("❌ Delete (confirm)", callback_data=f"{sudo.name} del {chat} {message}"),
            ]])

        def reply_button(msg_id: int, text: str = "↖️ Reply"):
            return InlineKeyboardMarkup([[
                InlineKeyboardButton(text, callback_data=f"{cbname} {msg_id}"),
            ]])

        # Quick reply
        @bot.on_message(reply_to_buttons & filters.user(sudo.admins) & filters.chat(support_chat) & filters.regex(r"^(?!\/)"))
        async def _(bot, m):
            args = button_args(m.reply_to_message, f"{sudo.name} ")[1:]
            if len(args) < 3:
                m.continue_propagation()
            match args[0]:
                case "send":
                    target = await bot.get_users(int(args[1]))
                    # Send the message to the target user
                    sent = await m.copy(
                        target.id,
                        reply_to_message_id=int(args[2]),
                    )
                    # Determine if the message is a plain text message or a media
                    msg_btn = await edit_copy(
                        bot,
                        m,
                        support_chat,
                        prefix=f"<b>{format_chat(m.from_user)} to {format_chat(target)}</b>\n\n",
                        reply_to_message_id=m.reply_to_message_id,
                        reply_markup=sent_message_buttons(sent.chat.id, sent.id),
                    )
                    if await can_delete(m):
                        await m.delete()
                    await sent.edit_reply_markup(reply_button(msg_btn.id))
                case _:
                    m.continue_propagation()

        # Callback queries
        from_sudoer = filters.create(lambda _, __, q: q.from_user.id in sudo.admins)

        # Restore original buttons of the message
        @bot.on_callback_query(
            from_sudoer & filters.regex(fr"^{sudo.name} btn [0-9]+ [0-9]+$"))
        async def _(bot, c):
            await c.edit_message_reply_markup(sent_message_buttons(*c.data.split(" ")[2:]))

        # Tell how to actually reply
        @bot.on_callback_query(
            from_sudoer & filters.regex(fr"^{sudo.name} send [0-9]+ [0-9]+$"))
        async def _(bot, c):
            user_name = chat_name(await bot.get_chat(int(c.data.split(" ")[2])))
            await c.answer(f"Reply to this to send a message to {user_name}.")

        # Ask for message deletion
        @bot.on_callback_query(
            from_sudoer & filters.regex(fr"^{sudo.name} askdel [0-9]+ [0-9]+$"))
        async def _(bot, c):
            await c.edit_message_reply_markup(askdel_buttons(*c.data.split(" ")[2:]))

        # Delete a sent message
        @bot.on_callback_query(
            from_sudoer & filters.regex(fr"^{sudo.name} del [0-9]+ [0-9]+$"))
        async def _(bot, c):
            await bot.delete_messages(*[int(i) for i in c.data.split(" ")[2:]])
            await c.edit_message_reply_markup(InlineKeyboardMarkup([[
                InlineKeyboardButton("✖️ Deleted", callback_data=f"{sudo.name} deleted {c.from_user.id}"),
            ]]))

        # Show who deleted the message
        @bot.on_callback_query(
            from_sudoer & filters.regex(fr"^{sudo.name} deleted [0-9]+$"))
        async def _(bot, c):
            user = await bot.get_users(int(c.data.split(" ")[2]))
            user_name = "You" if user.id == c.from_user.id else chat_name(user)
            await c.answer(f"{user_name} deleted this message.", show_alert=True)

        # Feedback commands (user-end)
        @bot.on_message(~filters.private & filters.command(name))
        async def _(bot, m):
            await countdown(m.reply, 3, "Use this command privately ({}).")
            try:
                await m.delete()
            except Exception:
                pass

        # Send feedback by command
        @bot.on_message(filters.private & (filters.command(name)))
        async def _(bot, m):
            if len(m.command) == 1 and not m.reply_to_message:
                await m.reply(str_help)
                return
            r = await m.reply(str_sending)
            sent = await edit_copy(
                bot,
                m,
                support_chat,
                prefix=f"<b>Feedback from {format_chat(m)}:</b>\n\n",
                reply_to_message_id=support_topic,
                reply_markup=admin_reply_button(m.chat.id, m.id),
            )
            if m.reply_to_message:
                await m.reply_to_message.copy(support_chat, reply_to_message_id=sent.id)
            await r.edit(str_sent)

        # Send feedback by replying
        @bot.on_message(filters.private & reply_to_buttons & filters.regex(r"^(?!\/)"))
        async def _(bot, m):
            r = m.reply_to_message
            rtmi = button_args(r, f"{cbname} ")[1:]
            prefix = ""
            try:
                rtmi = int(rtmi[0])
            except (ValueError, IndexError):
                m.continue_propagation()
            # Avoid sending messages in the main topic if the original message was deleted
            if rtmi == support_topic or (await bot.get_messages(support_chat, rtmi)).empty:
                rtmi = support_topic
                text = r.text.html if r.text else f"[media]\n{r.caption.html}" if r.caption else "[media]"
                prefix = f"<b>In reply to:</b>\n\n{text}\n\n<b>From {format_chat(m)}:</b>\n\n"
            await r.edit_reply_markup(reply_button(rtmi, "🔄 Sending..."))
            try:
                await edit_copy(
                    bot,
                    m,
                    support_chat,
                    prefix=prefix,
                    reply_to_message_id=rtmi,
                    reply_markup=admin_reply_button(m.chat.id, m.id),
                )
                await r.edit_reply_markup(reply_button(rtmi, "✅ Sent!"))
                await asyncio.sleep(1)
                await r.edit_reply_markup(reply_button(rtmi))
            except MessageNotModified:
                pass
            except Exception as e:
                await r.edit_reply_markup(reply_button(rtmi, "❌ Error"))
                raise e

        # Tell the users how to reply
        @bot.on_callback_query(filters.regex(fr"^{cbname}"))
        async def _(bot, c):
            await c.answer(
                "You can reply to a message containing the \"↖️ Reply\" button to"
                " directly forward your message to the support, without the need"
                f" of the /{cbname} command.",
                show_alert=True,
            )
