from ..fun import (
    format_chat,
    chat_name,
    quick_answer,
    try_wait,
    try_run_decorator,
)

import asyncio
import html
import logging
import sys
import traceback

from os import execl
from typing import Callable, Iterable, Union


from pyrogram import filters
from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineQuery,
)

log = logging.getLogger(__name__)


# Default sub-commands
class SubCommandsFunctions:
    def __init__(self, cfg):
        self.cfg = cfg
        self.list = {
            "explode": self.explode,
            "restart": self.restart,
            "spam": self.spam,
            "broadcast": self.spam,
        }
        # Check overrides and enable prefixed commands
        for cmd in self.list:
            if self.cfg.commands.get(cmd):
                log.info(f"\"{cmd}\" was a default command, it was overwritten.")
            elif self.cfg.prefix:
                self.cfg.bot.on_message(
                    filters.user(self.cfg.admins) & filters.command(cmd, prefixes=self.cfg.prefix),
                )(self.list[cmd])
                log.info(f"Registered \"{cmd}\" default sub-command.")

        # Enable prefixed custom sub-commands
        for cmd in self.cfg.commands:
            if self.cfg.prefix:
                self.cfg.bot.on_message(
                    filters.user(self.cfg.admins) & filters.command(cmd, prefixes=self.cfg.prefix)
                )(self.cfg.commands[cmd])
                log.info(f"Registered \"{cmd}\" sub-command.")

        # Command handler
        @self.cfg.bot.on_message(filters.user(self.cfg.admins) & filters.command(self.cfg.name))
        async def command_sudo(bot, m):
            await ((
                self.get(m.command[1])
            ) if len(m.command) > 1 else self.default_reply)(bot, m)

        # Default reply to non-sudoers
        @self.cfg.bot.on_message(filters.command(self.cfg.name))
        async def _(bot, m):
            await m.reply("Woodo?")

    def get(self, name):
        return (
            self.cfg.commands.get(name) or
            self.list.get(name) or
            self.not_recognized
        )

    async def explode(self, bot, m):
        raise Exception("Test.")

    async def restart(self, bot, m):
        sender = m.from_user or m.sender_chat
        await m.reply("Restarting the bot.")
        log.info(f"[{sender.id}] {chat_name(sender)} restarted the bot.")
        await self.cfg.log(f"{format_chat(sender)} restarted the bot.")
        log.info("Restarting the bot...")
        execl(sys.executable, sys.executable, *sys.argv)

    async def spam(self, bot, m):
        if not self.cfg.get_chats:
            await m.reply("No list of users provided.")
            return
        if not (
                m.reply_to_message and
                (m.reply_to_message.text or m.reply_to_message.media)
        ):
            await m.reply(
                "Reply to the message you want to broadcast.\n"
                "Once you send the message, you won't be able to edit it."
            )
            return
        chats = tuple(self.cfg.get_chats())
        count = 0
        i = 0
        message_link = f"<a href=\"{m.reply_to_message.link}\">this message</a>"
        r = await m.reply(f"Sending {message_link} ({i}/{len(chats)})...")
        for u in chats:
            i += 1
            if await try_wait(m.reply_to_message.copy, u):
                count += 1
            await asyncio.sleep(1)
            await try_wait(r.edit, f"Sending {message_link} ({i}/{len(chats)})...")
            await asyncio.sleep(1)
        await r.edit(f"Sent {message_link} to {count}/{len(chats)} chats.")

    async def not_recognized(self, bot, m):
        await m.reply(f"Command <code>{m.command[1]}</code> not recognized.")

    async def default_reply(self, bot, m):
        await m.reply("Woodo!")


class SudoConfig:
    def __init__(
        self,
        bot,
        name: Union[str, list[str]] = "sudo",
        prefix: Union[str, list[str]] = None,
        admins: list[int] = [],
        log_chat: list[Union[int, str, list[int]]] = None,
        # User defined sub-commands
        commands: dict[str, Callable] = {},
        # Function returning bot's users
        get_chats: Callable = None,
        # Enable error handling on the go instead of calling handle_errors()
        error_message: str = None,
    ):
        self.bot = bot
        self.name = name
        self.admins = admins
        if isinstance(log_chat, Iterable):
            self.log_chat, self.log_mid = log_chat[0], log_chat[1]
        else:
            self.log_chat, self.log_mid = log_chat, None
        self.commands = commands
        self.prefix = prefix
        self.get_chats = get_chats
        if error_message:
            self.handle_errors(error_message)

        self.fun = SubCommandsFunctions(self)

        log.info("Ready.")

    async def log(self, text: str):
        if self.log_chat:
            await try_wait(
                self.bot.send_message,
                self.log_chat,
                text,
                reply_to_message_id=self.log_mid,
            )
        else:
            log.info(f"message: {text}")

    def handle_errors(
        self,
        text: str = "An error occurred.",
        text_short: str = "An error occurred.",
    ):
        log.info("Enabling error handling...")

        async def report_error(bot, item, exception: Exception = None):
            # Report an error to the log chats
            traceback.print_exc()
            output = item
            user, chat = None, None
            if isinstance(item, Message):
                await item.reply(text)
                output = item.text or item.caption or "[Media]"
                user = item.from_user or item.sender_chat
                chat = item.chat
            elif isinstance(item, CallbackQuery):
                await item.answer(text, show_alert=True)
                output = item.data
                user = item.from_user
                chat = item.message.chat if item.message else "somewhere"
            elif isinstance(item, InlineQuery):
                await quick_answer(item, text_short, "h")
                output = item.query
                user = item.from_user
                chat = item.chat_type
            exc = traceback.format_exc()
            if len(exc) > 3500:
                exc = f"{exc[:200]}...\n\n...\n\n...{exc[-300:]}"
            await self.log(
                f"An exception occurred to {format_chat(user)} in"
                f" {format_chat(chat)}:\n\n"
                f"<pre language=\"log\">{html.escape(exc)}</pre>\n\n"
                f"{type(item).__name__}:\n"
                f"<code>{html.escape(output)}</code>"
            )

        self.bot.on_message = try_run_decorator(
            self.bot.on_message, report_error)
        self.bot.on_callback_query = try_run_decorator(
            self.bot.on_callback_query, report_error)
        self.bot.on_inline_query = try_run_decorator(
            self.bot.on_inline_query, report_error)
