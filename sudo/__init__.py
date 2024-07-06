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
import os
try:
    import psutil
except ImportError:
    psutil = None
import sys
import time
import traceback

from typing import Callable, Iterable


from pyrogram import filters
from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineQuery,
    ChosenInlineResult,
)
from pyrogram.errors import UserNotParticipant

log = logging.getLogger(__name__)


def format_time(time) -> str:
    upt = int(time)
    upt = [upt % 60, upt // 60, 0, 0]
    upt[1], upt[2] = upt[1] % 60, upt[1] // 60
    upt[2], upt[3] = upt[2] % 24, upt[2] // 24
    return (
        (f"{upt[3]}d " if upt[3] else "")
        + (f"{upt[2]}h " if upt[2] or upt[3] else "")
        + (f"{upt[1]}m " if upt[1] or upt[2] or upt[3] else "")
        + f"{upt[0]}s"
    )


# Default sub-commands
class SubCommandsFunctions:
    def __init__(self, cfg):
        self.cfg = cfg
        self.list = {
            "explode": self.explode,
            "restart": self.restart,
            "info": self.info,
            "send": self.send,
            "spam": self.spam,
            "broadcast": self.spam,
            "copy": self.copy,
            "leave": self.leave,
        }
        self._p = psutil.Process() if psutil else None
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

    # "My job here is done" sticker
    @property
    def job_done(self):
        return "CAACAgQAAx0CWzSgSwACAu9jQbY6q1CWFVYmvd9oLvr9lTjDowADBAAC4VO0Gkg-S0vXzYliHgQ"

    # "Swossh" sticker
    @property
    def swoosh(self):
        return "CAACAgQAAx0CWzSgSwACAvBjQbY8ekRMaHdcyGcZbTjcuEpQvwACAgQAAuFTtBrgVhKngYV6YB4E"

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
        os.execl(sys.executable, sys.executable, *sys.argv)

    async def info(self, bot, m):
        create_time = self._p.create_time() if self._p else 0
        await m.reply(
            "<b>.•°• System information •°•.</b>\n\n"
            f"<i>Python path:</i> <code>{html.escape(sys.executable)}</code>\n"
            "<i>Python version:</i> "
            f"<code>{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} "
            f"({sys.implementation._multiarch})</code>\n"
            f"<i>Process:</i> [</code><code>{os.getpid()}</code><code>] "
            f"<code>{html.escape(" ".join(sys.argv))}</code>\n" +
            (f"<i>Memory:</i> <code>{round(self._p.memory_full_info().uss/1048576, 3)}MiB</code>\n"
             "\n"
             f"<i>Uptime:</i> <code>{format_time(time.time() - create_time)}</code>\n"
             f"<i>Running since {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(create_time))}.</i>"
             if self._p else "")
        )

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

    async def send(self, bot, m):
        args = m.command[1:] if m.command[0].startswith(self.cfg.name) else m.command[:]
        if len(args) > 1:
            chat, rtmi, *_ = (*args[1].split("/"), None)
            try:
                chat = await bot.get_chat(chat)
                rtmi = int(rtmi) if rtmi and rtmi.isnumeric() else None
                if m.reply_to_message and (m.reply_to_message.text or m.reply_to_message.media):
                    await m.reply_to_message.copy(chat, reply_to_message_id=rtmi)
                else:
                    await bot.send_message(chat.id, " ".join(args[2:]) or "⁭", reply_to_message_id=rtmi)
                await m.reply(f"Message sent to {format_chat(chat)}.")
                return
            except ValueError as e:
                print(e)
                pass
        await m.reply(f"Syntax:\n\n<code>/{self.cfg.name} {args[0]} "
                      "&lt;chat/reply_to_message&gt; [text]</code>")

    async def copy(self, bot, m):
        if m.reply_to_message and m.reply_to_message.from_user and m.reply_to_message.from_user.is_self:
            await m.reply_to_message.copy(
                m.chat.id,
                reply_to_message_id=int(m.command[-1]) if m.command[-1].isnumeric() else None,
            )

    async def leave(self, bot, m):
        args = m.command[1:] if m.command[0].startswith(self.cfg.name) else m.command[:]
        if len(args) > 1:
            chat = args[1]
            try:
                out = ""
                chat = await bot.get_chat(args[1])
                if "fancy" in args[2:]:
                    me = await chat.get_member("me")
                    perm = (me and me.permissions) or chat.permissions
                    if perm.can_send_other_messages:
                        await bot.send_sticker(chat.id, self.job_done)
                        await bot.send_sticker(chat.id, self.swoosh)
                        out = "Stickers sent."
                    elif perm.can_send_messages:
                        await bot.send_message(chat.id, "My job here is done.\n\n<i>*swoosh*</i>")
                        out = "Couldn't send the stickers. Sent a message instead."
                    else:
                        out = "Couldn't send any message to the chat."
                await chat.leave()
                await m.reply(f"Left {format_chat(chat)}.\n{out}")
            except UserNotParticipant:
                await m.reply("Not joined that chat.")
        else:
            await m.reply("Enter ID of channel/group to leave.")

    async def not_recognized(self, bot, m):
        await m.reply(f"Command <code>{m.command[1]}</code> not recognized.")

    async def default_reply(self, bot, m):
        await m.reply("Woodo!")


class SudoConfig:
    def __init__(
        self,
        bot,
        name: (str | list[str]) = "sudo",
        prefix: (str | list[str]) = None,
        admins: list[int] = [],
        log_chat: list[(int | str | list[int])] = None,
        # User defined sub-commands
        commands: dict[str, Callable] = {},
        # Function returning bot's users
        get_chats: Callable = None,
        # Enable error handling on the go instead of calling handle_errors()
        error_message: str = None,
        error_message_short: str = None,
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
            self.handle_errors(error_message, error_message_short)
        else:
            self.error_message = "An error occurred."
            self.error_message_short = self.error_message

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

    async def report_error(self, bot, item, exception: Exception = None):
        # Report an error to the log chats
        traceback.print_exc()
        output = f"{item}"
        user, chat = None, None
        if isinstance(item, Message):
            await item.reply(self.error_message)
            output = item.text or item.caption or "[Media]"
            user = item.from_user or item.sender_chat
            chat = item.chat
        elif isinstance(item, CallbackQuery):
            await item.answer(self.error_message, show_alert=True)
            output = item.data
            user = item.from_user
            chat = item.message.chat if item.message else "somewhere"
        elif isinstance(item, InlineQuery):
            await quick_answer(item, self.error_message_short, "h")
            output = item.query
            user = item.from_user
            chat = item.chat_type
        elif isinstance(item, ChosenInlineResult):
            output = f"[{item.result_id}]: {item.query}"
            user = item.from_user
            chat = "somewhere"
        exc = traceback.format_exc()
        # TODO: better handling of the output if exceeding the available length
        if len(exc) > 3500:
            exc = f"{exc[:200]}...\n\n...\n\n...{exc[-300:]}"
        await self.log(
            f"An exception occurred to {format_chat(user)} in"
            f" {format_chat(chat)}:\n\n"
            f"<pre language=\"log\">{html.escape(exc)}</pre>\n\n"
            f"{type(item).__name__}:\n"
            f"<code>{html.escape(output)}</code>"
        )

    def handle_errors(
        self,
        text: str = "An error occurred.",
        text_short: str = "An error occurred.",
    ):
        log.info("Enabling error handling...")
        self.error_message = text
        self.error_message_short = text_short

        self.bot.on_message = try_run_decorator(
            self.bot.on_message, self.report_error)
        self.bot.on_callback_query = try_run_decorator(
            self.bot.on_callback_query, self.report_error)
        self.bot.on_inline_query = try_run_decorator(
            self.bot.on_inline_query, self.report_error)
        self.bot.on_chosen_inline_result = try_run_decorator(
            self.bot.on_chosen_inline_result, self.report_error)
