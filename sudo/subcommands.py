from ..fun import chat_name, format_chat, try_wait

import asyncio
import inspect
import html
import logging
import os
try:
    import psutil
except ImportError:
    psutil = None
import sys
import time

from pyrogram import filters
from pyrogram.errors import UserNotParticipant

log = logging.getLogger(__name__)
SPAWN = time.time()


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
            "sendsilent": self.send,
            "copy": self.send,
            "copysilent": self.send,
            "spam": self.spam,
            "broadcast": self.spam,
            "leave": self.leave,
        }
        if cfg.block_system:
            log.info("Enabling block system...")
            from . import block
            self._block = block.init(self.cfg)
            self.list["block"] = self._block.command_block
            self.list["unblock"] = self._block.command_unblock
            self.list["blocked"] = self._block.command_blocked
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
        create_time = self._p.create_time() if self._p else SPAWN
        await m.reply(
            "<b>.•°• System information •°•.</b>\n\n"
            f"<i>Python path:</i> <code>{html.escape(sys.executable)}</code>\n"
            "<i>Python version:</i> "
            f"<code>{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} "
            f"({sys.implementation._multiarch})</code>\n"
            f"<i>Process:</i> [<code>{os.getpid()}</code>] "
            f"<code>{html.escape(" ".join(sys.argv))}</code>\n" +
            (f"<i>Memory:</i> <code>{round(self._p.memory_full_info().uss/1048576, 3)}MiB</code>\n"
             if self._p else "") +
            "\n"
            f"<i>Uptime:</i> <code>{format_time(time.time() - create_time)}</code>\n"
            f"<i>Running since {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(create_time))}.</i>"
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
        if inspect.iscoroutinefunction(self.cfg.get_chats):
            chats = tuple(await self.cfg.get_chats())
        else:
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
            silent = "silent" in args[0]
            chat, rtmi, *_ = (*args[1].split("/"), None)
            try:
                chat = m.chat if chat == "#here" else await bot.get_chat(chat)
            except Exception:
                await m.reply(f"Couldn't retrieve <code>{html.escape(chat)}</code>.")
                return
            rtmi = int(rtmi) if rtmi and rtmi.isnumeric() else None
            text = " ".join(args[2:])
            if not text and m.reply_to_message and (m.reply_to_message.text or m.reply_to_message.media):
                await m.reply_to_message.copy(chat.id, reply_to_message_id=rtmi)
            else:
                await bot.send_message(chat.id, text or "⁭", reply_to_message_id=rtmi)
            if silent:
                try:
                    await m.delete()
                except Exception:
                    pass
            else:
                await m.reply(f"Message sent to {format_chat(chat)}.")
        else:
            await m.reply(
                f"Syntax:\n\n"
                f"<code>/{self.cfg.name} {args[0]} &lt;chat/reply to message id&gt; [text]</code>\n\n"
                "To copy a message, omit <code>[text]</code> while replying to that message.\n"
                "To send a message to the current chat, use <code>#here</code> as <code>chat</code>."
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
                    privs = me and me.privileges
                    if (
                            (privs and privs.can_post_messages) or
                            (perm and perm.can_send_other_messages)
                    ):
                        await bot.send_sticker(chat.id, self.job_done)
                        await bot.send_sticker(chat.id, self.swoosh)
                        out = "Stickers sent."
                    elif perm and perm.can_send_messages:
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
        await m.reply(f"Command <code>{html.escape(m.command[1])}</code> not recognized.")

    async def default_reply(self, bot, m):
        await m.reply("Woodo!")
