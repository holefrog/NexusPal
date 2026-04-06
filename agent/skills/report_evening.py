"""
skills/report_evening.py  –  晚报 skill
当前：测试阶段，输出标题 + 占位复盘。
后续：替换 _generate_content() 接入 Gemini。
"""

from datetime import datetime, timezone, timedelta

import discord

from skills import BaseSkill
from state import State


class ReportEveningSkill(BaseSkill):
    name = "晚报"

    _TEST_TOPICS = [
        "美股收盘概况",
        "今日涨跌幅前十",
        "隔夜期货动态",
        "明日重要事件预告",
    ]

    async def run(self, channel: discord.TextChannel, state: State) -> None:
        content = self._generate_content(state)
        await channel.send(content)

        state.last_evening_report = datetime.now(timezone.utc)
        state.evening_report_count += 1

    def _generate_content(self, state: State) -> str:
        """
        生成晚报正文。
        TODO: 替换为 Gemini API 调用。
        """
        now_cst  = datetime.now(timezone.utc) + timedelta(hours=8)
        date_str = now_cst.strftime("%Y-%m-%d")
        weekday  = ["周一","周二","周三","周四","周五","周六","周日"][now_cst.weekday()]

        topics = "\n".join(
            f"> {i+1}. {t}" for i, t in enumerate(self._TEST_TOPICS)
        )

        return (
            f"🌙 **投研晚报  {date_str} {weekday}**\n\n"
            f"**今日复盘要点** `[测试模式]`\n"
            f"{topics}\n\n"
            f"_生成时间: {now_cst.strftime('%H:%M')} CST_"
        )
