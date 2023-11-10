from ..fun import format_chat, chat_name, quick_answer, try_sending, try_run_decorator

import html
import logging
import sys
import traceback

from os import execl
from typing import Callable, Iterable, Union


from pyrogram import filters
from pyrogram.types import (
    Message, CallbackQuery, InlineQuery,
)


def log(*_, **__):
    pass


def init(
    bot,
    name: Union[str, list[str]] = "sudo",
    admins: list[int] = [],
    log_chats: list[Union[int, str, list[int]]] = [],
    commands: dict[str, Callable] = {},
    handle_error: bool = True,
    prefix: str = None,
):
    # Set global log variable
    global log

    async def _(
        text: str,
        exclude: Iterable[Union[int, Iterable[int]]] = []
    ):
        for chat in log_chats:
            reply_to_message_id = None
            if isinstance(chat, Iterable):
                chat, reply_to_message_id = chat[0], chat[1]
            if chat not in exclude:
                await try_sending(
                    bot, chat, text, reply_to_message_id=reply_to_message_id
                )

    log = _

    # Initialize error handling and sub-commands
    logger = logging.getLogger(__name__)
    logger.info("Initializing sudo...")

    if handle_error:
        logger.info("Enabling error handling...")
        error_message = (
            "An error occurred.\n"
            "Please, contact @dst212 for further information."
        )

        async def report_error(bot, item):
            # Report an error to the log chats
            traceback.print_exc()
            output = item
            user, chat = None, None
            if isinstance(item, Message):
                await item.reply(error_message)
                output = item.text or item.caption or "[Media]"
                user = item.from_user or item.sender_chat
                chat = item.chat
            elif isinstance(item, CallbackQuery):
                await item.answer(error_message, show_alert=True)
                output = item.data
                user = item.from_user
                chat = item.message.chat if item.message else "somewhere"
            elif isinstance(item, InlineQuery):
                await quick_answer(item, "An error occurred.", "h")
                output = item.query
                user = item.from_user
                chat = item.chat_type
            exc = traceback.format_exc()
            if len(exc) > 3500:
                exc = f"{exc[:200]}...\n\n...\n\n...{exc[-300:]}"
            await log(
                f"An exception occurred to {format_chat(user)} in"
                f" {format_chat(chat)}:\n\n"
                f"<pre language=\"log\">{html.escape(exc)}</pre>\n\n"
                f"{type(item).__name__}:\n"
                f"<code>{html.escape(output)}</code>"
            )

        bot.on_message = try_run_decorator(
            bot.on_message, report_error)
        bot.on_callback_query = try_run_decorator(
            bot.on_callback_query, report_error)
        bot.on_inline_query = try_run_decorator(
            bot.on_inline_query, report_error)

    # Default sub-commands
    async def fun_explode(bot, m):
        raise Exception("Test.")

    async def fun_restart(bot, m):
        sender = m.from_user or m.sender_chat
        await m.reply("Restarting the bot.")
        logger.info(f"[{sender.id}] {chat_name(sender)} restarted the bot.")
        for chat in log_chats:
            await log(f"{format_chat(sender)} restarted the bot.")
        logger.info("Restarting the bot...")
        execl(sys.executable, sys.executable, *sys.argv)

    default = {
        "explode": fun_explode,
        "restart": fun_restart,
    }

    # Check overrides and enable prefixed commands
    for cmd in default:
        if commands.get(cmd):
            logger.info(f"\"{cmd}\" was a default command, it was overwritten.")
        elif prefix:
            bot.on_message(
                filters.user(admins) & filters.command(cmd, prefixes=prefix),
            )(default[cmd])
            logger.info(f"Registered {cmd} default sub-command.")

    # Enable prefixed custom sub-commands
    for cmd in commands:
        @bot.on_message(filters.user(admins) & filters.command(cmd))
        async def _(bot, m):
            await commands[cmd](bot, m)
        logger.info(f"Registered {cmd} sub-command.")

    async def not_recognized(bot, m):
        await m.reply(f"Command <code>{m.command[1]}</code> not recognized.")

    async def default_reply(bot, m):
        await m.reply("Woodo!")

    # Command handler
    @bot.on_message(filters.user(admins) & filters.command(name))
    async def command_sudo(bot, m):
        await ((
            commands.get(m.command[1]) or
            default.get(m.command[1]) or
            not_recognized
        ) if len(m.command) > 1 else default_reply)(bot, m)

    # Default reply to non-sudoers
    @bot.on_message(filters.command(name))
    async def _(bot, m):
        await m.reply("Woodo?")

    logger.info("Ready.")
