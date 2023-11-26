import asyncio
import html
import logging

from typing import Union, Callable

from pyrogram import filters
from pyrogram.enums import ChatType, ChatMemberStatus, ChatAction
from pyrogram.types import (
    Chat, User,
    Message, CallbackQuery, InlineQuery,
    ChatPrivileges,
)
from pyrogram.errors import FloodWait

log = logging.getLogger(__name__)


# User output formatting
def format_chat(
        item: Union[Message, CallbackQuery, InlineQuery, User, Chat],
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
    item: Union[Message, CallbackQuery, InlineQuery, User, Chat],
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


def chat_name(chat: Union[Chat, User], show_username=True) -> str:
    if type(chat) not in (Chat, User):
        return str(chat)
    return (
        (chat.first_name or chat.title)
        + (f" (@{chat.username})" if show_username and chat.username else "")
    )


# Some bool flags
async def is_admin(
    m: Union[Message, CallbackQuery]
) -> Union[bool, ChatPrivileges]:
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


async def is_member(user: Union[User, int], chat: Chat) -> bool:
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


async def can_delete(chat: Union[Chat, Message], who="me") -> bool:
    if isinstance(chat, Message):
        chat = chat.chat
    if chat.type == ChatType.PRIVATE:
        return True
    user = await chat.get_member(who)
    return user.privileges.can_delete_messages if user else None


async def can_send_to(bot, user: Union[User, int]) -> bool:
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


def chat_type(bot, item: Union[Chat, Message, InlineQuery, CallbackQuery]):
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


# Retry performing a specific task waiting for FloodWait limitations
async def try_wait(func: Callable, *args, **kwargs) -> bool:
    ok = False
    while not ok:
        try:
            await func(*args, **kwargs)
            ok = True
        except FloodWait as e:
            log.info(f"Waiting {e.value + 5} seconds before sending again...")
            await asyncio.sleep(e.value + 5)
        except Exception as e:
            log.info(
                "Couldn't sent message to"
                f" {kwargs.get('chat') or args[0] if len(args) > 0 else '?'}: {e}"
            )
            return False
    return True


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
                except Exception:
                    await handle_error(*args, **kwargs)
            # Turning on_message into an auto-reporter if exceptions occurr
            return actual_decorator(*dargs, **dkwargs)(catcher)
        return wrapper
    return decorator
