import asyncio
import html
import logging
import re

from typing import Callable

from pyrogram import filters, ContinuePropagation, StopPropagation
from pyrogram.enums import ChatType, ChatMemberStatus, ChatAction
from pyrogram.types import (
    Chat, User,
    Message,
    CallbackQuery,
    InlineQuery,
    InlineKeyboardMarkup,
    ChatPrivileges,
)
from pyrogram.errors import FloodWait

log = logging.getLogger(__name__)


# User output formatting
def format_chat(
        item: (Message | CallbackQuery | InlineQuery | User | Chat),
        text: str = None,
) -> str:
    if item is None:
        return None
    if isinstance(item, Message):
        item = item.from_user or item.sender_chat
    elif isinstance(item, CallbackQuery) or isinstance(item, InlineQuery):
        item = item.from_user
    if isinstance(item, User) or isinstance(item, Chat):
        return f"[<code>{item.id}</code>] {chat_link(item, text)}"
    return f"{html.escape(str(item))}"


def chat_link(
    item: (Message | CallbackQuery | InlineQuery | User | Chat),
    text: str = None,
) -> str:
    if item is None:
        return None
    if isinstance(item, Message):
        item = item.from_user or item.sender_chat
    elif isinstance(item, CallbackQuery) or isinstance(item, InlineQuery):
        item = item.from_user
    if not isinstance(item, Chat) and not isinstance(item, User):
        return html.escape(str(item))
    if isinstance(item, User) or item.type in (ChatType.PRIVATE, ChatType.BOT):
        return f"<a href=\"tg://user?id={item.id}\">" + (
            text or (
                f"@{item.username}" if item.username else
                html.escape(item.first_name)
            )
        ) + "</a>"
    if not text:
        text = (
            f"@{item.username}" if item.username else
            html.escape(item.title)
        )
    if item.invite_link:
        text = f"<a href=\"{item.invite_link}\">{text}</a>"
    return text


def chat_name(chat: (Chat | User), show_username=True) -> str:
    if type(chat) not in (Chat, User):
        return str(chat)
    return (
        (chat.first_name or chat.title)
        + (f" (@{chat.username})" if show_username and chat.username else "")
    )


# Some bool flags
async def is_admin(
    m: (Message | CallbackQuery),
) -> (bool | ChatPrivileges):
    user = None
    if isinstance(m, CallbackQuery):
        user = m.from_user
        m = m.message
        if m is None:
            return False
    elif isinstance(m, Message):
        user = m.from_user or m.sender_chat
    else:
        return False
    if user.id == m.chat.id:
        return True
    member = await m.chat.get_member(user.id)
    return member.privileges is not None if member else False


async def _(f, b, m):
    return await is_admin(m)


from_admin = filters.create(_, "admin")


async def is_member(user: (User | int), chat: Chat) -> bool:
    if isinstance(user, User):
        user = user.id
    return (
        isinstance(user, int) and
        isinstance(chat, Chat) and
        (await chat.get_member(user)).status in (
            ChatMemberStatus.OWNER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.MEMBER,
        )
    )


async def can_delete(chat: (Chat | Message), who="me") -> bool:
    if isinstance(chat, Message):
        chat = chat.chat
    if chat.type == ChatType.PRIVATE:
        return True
    user = await chat.get_member(who)
    return user.privileges.can_delete_messages if user and user.privileges else None


async def can_send_to(bot, user: (User | int)) -> bool:
    if isinstance(user, User):
        user = user.id
    elif not isinstance(user, int):
        return False
    try:
        await bot.send_chat_action(user, ChatAction.TYPING)
        await bot.send_chat_action(user, ChatAction.CANCEL)
        return True
    except Exception:
        pass
    return False


def chat_type(bot, item: (Chat | Message | InlineQuery | CallbackQuery)):
    if isinstance(item, Message):
        return item.chat.type
    if isinstance(item, InlineQuery):
        return item.chat_type
    if isinstance(item, CallbackQuery):
        return item.message.chat.type if item.message else None
    if isinstance(item, Chat):
        return item.type
    return None


async def quick_answer(query, text, parameter):
    await query.answer(
        [],
        switch_pm_text=text,
        switch_pm_parameter=parameter,
        cache_time=1,
    )


# Regex for chosen inline results
def query_match(query):
    async def func(f, _, result):
        return re.match(f.query, result.query)

    return filters.create(func, query=query)


# There's a button matching the specified callback_data
def has_button(data, row=0, col=0):
    async def func(f, _, message):
        rm = message.reply_markup
        return (
            isinstance(rm, InlineKeyboardMarkup) and
            len(rm.inline_keyboard) > f.row and
            len(rm.inline_keyboard[f.row]) > f.col and
            re.match(f.data, (rm.inline_keyboard[f.row][f.col]).callback_data or "")
        )
    return filters.create(func, data=data, row=row, col=col)


async def _(f, b, m):
    r = m.reply_to_message
    return r and r.from_user and r.from_user.is_self and isinstance(r.reply_markup, InlineKeyboardMarkup)


reply_to_buttons = filters.create(_, "reply_to_buttons")


# Get the callback data of the first inline button
def button_args(m, startswith: str = None):
    if not (m and m.from_user and m.from_user.is_self and m.reply_markup):
        return []
    data = m.reply_markup.inline_keyboard[0][0].callback_data
    if startswith and not (data and data.startswith(startswith)):
        return []
    return data.split(" ")


# Get the callback data of the first inline button
def button_args_inline(m, startswith: str = None):
    if not (m and m.from_user and m.from_user.is_self and m.reply_markup):
        return []
    data = m.reply_markup.inline_keyboard[0][0].switch_inline_query_current_chat
    if startswith and not (data and data.startswith(startswith)):
        return []
    return data.split(" ")


# Retry performing a specific task waiting for FloodWait limitations
async def try_wait(func: Callable, *args, **kwargs):
    ok = False
    while not ok:
        try:
            ok = await func(*args, **kwargs) or True
        except FloodWait as e:
            log.info(f"Waiting {e.value + 5} seconds before sending again...")
            await asyncio.sleep(e.value + 5)
        except Exception as e:
            log.info(
                "Couldn't send message to"
                f" {kwargs.get('chat') or args[0] if len(args) > 0 else '?'}: {e}"
            )
            return False
    return ok


# Retry sending messages waiting for FloodWait limitations
async def try_sending(bot, *args, **kwargs) -> bool:
    return await try_wait(bot.send_message, *args, **kwargs)


# Decorator to handle errors in a nicer way, usage:
# bot.on_message = try_run_decorator(bot.on_message, report_error)
def try_run_decorator(actual_decorator, handle_error):
    def decorator(*dargs, **dkwargs):
        def wrapper(fun):
            async def catcher(*args, **kwargs):
                try:
                    await fun(*args, **kwargs)
                except (ContinuePropagation, StopPropagation) as e:
                    raise e
                except Exception as e:
                    await handle_error(*args, **kwargs, exception=e)
            # Turning on_message into an auto-reporter if exceptions occurr
            return actual_decorator(*dargs, **dkwargs)(catcher)
        return wrapper
    return decorator


# Send a message and edit it n times counting down
async def countdown(func: Callable, n, text, delete=True, *args, **kwargs):
    m = await func(text.format(n), *args, **kwargs)
    for i in range(n - 1, -1, -1):
        await asyncio.sleep(1)
        m = await try_wait(m.edit, text.format(i))
        if not m:
            return
    if delete:
        await m.delete()


# Copy a message to another chat while also editing the text
async def edit_copy(bot, m: Message, chat_id: int, prefix: str = "", suffix: str = "", **kwargs):
    next_text = ""
    func, text = (
        bot.send_message,
        {"text": f"{prefix}{m.text.html}{suffix}"},
    ) if m.text else (
        m.copy,
        {"caption": f"{prefix}{m.caption.html}{suffix}" if m.caption else f"{prefix}{suffix}"},
    )
    if m.text and len(text) > 4096:
        text, next_text = f"{text[:4093]}...", f"...{text[4093:]}".strip()
    elif m.caption and len(text) > 1024:
        text, next_text = f"{text[:1021]}...", f"...{text[1021:]}".strip()
    r = await func(
        chat_id,
        **text,
        **kwargs,
    )
    if next_text:
        try:
            await bot.send_message(chat_id, next_text, reply_to_message_id=r.id)
        except Exception as e:
            print(e)
    return r
