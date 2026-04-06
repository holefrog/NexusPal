"""
skills/__init__.py  –  BaseSkill 基类
所有 skill 继承此类，实现 run()。
agent 统一通过 invoke() 调用，失败自动走 on_error。
"""

import logging
import traceback
from abc import ABC, abstractmethod

import discord

from state import State

log = logging.getLogger("invest.skill")


class BaseSkill(ABC):
    """所有 skill 的基类，定义统一接口。"""

    # 子类设置，用于日志和错误消息中的可读名称
    name: str = "unnamed"

    @abstractmethod
    async def run(self, channel: discord.TextChannel, state: State) -> None:
        """执行 skill 主逻辑。失败时抛出异常，由 invoke() 统一捕获。"""
        ...

    async def on_error(
        self,
        channel: discord.TextChannel,
        state: State,
        exc: Exception,
    ) -> None:
        """
        默认错误处理：发错误消息到 channel。
        子类可覆盖以实现自定义错误处理（如重试、告警）。
        """
        tb = traceback.format_exc()
        log.error("[%s] 执行失败: %s\n%s", self.name, exc, tb)
        try:
            await channel.send(
                f"⚠️ **[{self.name}] 执行失败**\n"
                f"```\n{type(exc).__name__}: {exc}\n```"
            )
        except Exception as send_err:
            log.error("[%s] 错误消息发送失败: %s", self.name, send_err)


async def invoke(
    skill: BaseSkill,
    channel: discord.TextChannel,
    state: State,
) -> bool:
    """
    统一 skill 调用入口。
    返回 True 表示执行成功，False 表示执行失败。
    """
    log.info("[%s] 开始执行", skill.name)
    try:
        await skill.run(channel, state)
        log.info("[%s] 执行完成", skill.name)
        return True
    except Exception as exc:
        await skill.on_error(channel, state, exc)
        return False
