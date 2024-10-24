from ..fun import sender_of, format_chat, get_command

import asyncio
import html
import logging
import re
import os

from pyrogram import filters
from pyrogram.types import Chat, User

try:
    from .data.blocked import BLOCKED
except ImportError:
    BLOCKED = {"chats": {}, "users": {}}

PATH = f"{os.path.dirname(os.path.abspath(__file__))}/data"
BLOCKED_PATH = f"{PATH}/blocked.py"

log = logging.getLogger(__name__)
log.debug(f"Data path: {PATH}")


async def get_chat(bot, chat_id: (int | str)) -> (Chat, int):
    chat = None
    try:
        chat = await bot.get_chat(chat_id)
    except Exception:
        pass
    if not isinstance(chat_id, int):
        if re.match(r"(-|)[0-9]+$", chat_id):
            chat_id = int(chat_id)
        elif chat:
            chat_id = chat.id
        else:
            chat_id = None
    return chat, chat_id


class init:
    def __init__(self, sudo):
        self.sudo = sudo
        self._blocked_lock = asyncio.Lock()

        # Block users in "*"
        @sudo.bot.on_message(~filters.user(sudo.admins))
        async def _(bot, m):
            command = get_command(m.text or m.caption) or "*"
            sender = sender_of(m)
            if (
                self.can_use(m.chat, command) and
                (sender.id == m.chat.id or self.can_use(sender_of(m), command))
            ):
                m.continue_propagation()

        # Block users in "inline"
        @sudo.bot.on_inline_query(~filters.user(sudo.admins))
        async def _(bot, q):
            if self.can_use(q.from_user, "inline"):
                q.continue_propagation()

        # Block users in "callback"
        @sudo.bot.on_callback_query(~filters.user(sudo.admins))
        async def _(bot, c):
            if self.can_use(c.from_user, "callback"):
                c.continue_propagation()

    def can_use(self, item: (Chat | User), command: str = "*") -> bool:
        if not item:
            # Allow anonymous users
            return True
        chat_type = "chats" if item.id < 0 else "users"
        return (
            item.id not in (BLOCKED[chat_type].get(command) or []) and
            (command == "*" or (item.id not in (BLOCKED[chat_type].get("*") or [])))
        ) or self.whitelisted(item, command)

    def whitelisted(self, item: (Chat | User), command: str) -> bool:
        if not command:
            return False
        if not item:
            return True
        return item.id in (BLOCKED["chats" if item.id < 0 else "users"].get(f"!{command}") or [])

    # Block an user
    # * → block every update
    # callback → block buttons
    # inline → block inline mode
    # /<command> → a specific command
    # !<any of the above> → whitelist that command (maybe /feedback or similar)
    async def block(self, item: (int | Chat | User), commands: list[str] = ["*"]):
        if not isinstance(item, int):
            item = item.id
        chat_type = "chats" if item < 0 else "users"
        async with self._blocked_lock:
            os.makedirs(PATH, exist_ok=True)
            for i in commands:
                if not BLOCKED[chat_type].get(i):
                    BLOCKED[chat_type][i] = []
                if item not in BLOCKED[chat_type][i]:
                    BLOCKED[chat_type][i].append(item)
            with open(BLOCKED_PATH, "w") as f:
                f.write(f"BLOCKED = {BLOCKED}")

    # Unblock an user
    async def unblock(self, item: (int | Chat | User), commands: list[str] = ["*"]) -> list[str]:
        if not isinstance(item, int):
            item = item.id
        chat_type = "chats" if item < 0 else "users"
        removed_from = []
        deferred = []  # Items to remove if the list is empty
        async with self._blocked_lock:
            os.makedirs(PATH, exist_ok=True)
            if "*" in commands:
                for k, v in BLOCKED[chat_type].items():
                    try:
                        v.remove(item)
                        removed_from.append(k)
                    except ValueError:
                        pass
                    if not v:
                        deferred.append(k)
            else:
                for i in commands:
                    items = BLOCKED[chat_type].get(i)
                    if items:
                        try:
                            items.remove(item)
                            removed_from.append(i)
                        except ValueError:
                            pass
                    if items is not None and not items:
                        deferred.append(i)
            for i in deferred:
                del BLOCKED[chat_type][i]
            with open(BLOCKED_PATH, "w") as f:
                f.write(f"BLOCKED = {BLOCKED}")
        return removed_from

    async def command_block(self, bot, m):
        args = m.command[2:] if m.command[0] == self.sudo.name else m.command[1:]
        chat, chat_id = await get_chat(bot, args[0])
        if not chat_id:
            await m.reply(f"Invalid ID: <code>{html.escape(args[0])}</code>")
        else:
            commands = args[1:] or ["*"]
            await self.block(chat_id, commands)
            await m.reply(
                f"Blocked {format_chat(chat) if chat else f"[<code>{chat_id}</code>]"}:\n"
                f"<code>{"</code>, <code>".join(commands)}</code>"
            )

    async def command_unblock(self, bot, m):
        args = m.command[2:] if m.command[0] == self.sudo.name else m.command[1:]
        chat, chat_id = await get_chat(bot, args[0])
        if not chat_id:
            await m.reply(f"Invalid ID: <code>{html.escape(args[0])}</code>")
        else:
            commands = await self.unblock(chat_id, args[1:] or ["*"])
            await m.reply(
                f"Unblocked {format_chat(chat) if chat else f"[<code>{chat_id}</code>]"}:\n"
                f"<code>{"</code>, <code>".join(commands)}</code>" if commands else
                f"{format_chat(chat)} was not blocked."
            )

    async def list_blocked(self, what: str) -> str:
        items = {}
        out = ""
        func = self.sudo.bot.get_chat if what == "chats" else self.sudo.bot.get_users
        for k, v in BLOCKED[what].items():
            if v:
                out += f"─<code>{k}</code>\n"
                for i, chat_id in enumerate(v):
                    try:
                        chat = items.get(chat_id)
                        if not chat:
                            chat = items[chat_id] = await func(chat_id)
                        chat = format_chat(chat)
                    except Exception:
                        chat = f"[<code>{chat_id}</code>]"
                    prefix = "&#x2800;└─" if i == len(v) - 1 else "&#x2800;├─"
                    out += f"{prefix}{chat}\n"
        return f"<b>Blocked {what}</b>:\n{out}" if out else ""

    async def command_blocked(self, bot, m):
        MAX_LENGTH = 4095
        r = await m.reply("Loading...")
        out = (
            f"{await self.list_blocked("chats")}\n{await self.list_blocked("users")}".strip()
            or "No one is blocked."
        )
        sent = 0
        while len(out) > MAX_LENGTH:
            i = out[:MAX_LENGTH].rfind("\n")
            if i == -1:
                i = MAX_LENGTH
            r = await (r.reply if sent else r.edit)(out[:i])
            out = out[i + 1:]
            sent += 1
        if out:
            await (r.reply if sent else r.edit)(out)
