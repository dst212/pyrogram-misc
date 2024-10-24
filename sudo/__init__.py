from .subcommands import SubCommandsFunctions

from ..fun import (
    sender_of,
    format_chat,
    quick_answer,
    try_wait,
    try_run_decorator,
)

import html
import logging
import traceback

from typing import Callable, Iterable


from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineQuery,
    ChosenInlineResult,
)

log = logging.getLogger(__name__)


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
        # Enable block-system
        block_system: bool = False,
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
        self.block_system = block_system

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
        user, chat = None, None
        if isinstance(item, Message):
            await item.reply(self.error_message)
            output = item.text or item.caption or "[Media]"
            user = sender_of(item)
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
        else:
            output = f"{item}"
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
