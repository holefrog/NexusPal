"""
skills/report_morning.py  –  早报 skill
当前：测试阶段，输出标题 + 占位主题。
后续：替换 _generate_content() 接入 Gemini。
"""

from datetime import datetime, timezone, timedelta

import discord

from skills import BaseSkill
from state import State


class ReportMorningSkill(BaseSkill):
    name = "早报"

    # 测试用占位主题，接入 Gemini 后删除
    _TEST_TOPICS = [
        "美联储利率预期动态",
        "AI 芯片供应链追踪",
        "标普 500 技术面",
        "能源板块资金流向",
        "亚太市场隔夜概况",
    ]

    async def run(self, channel: discord.TextChannel, state: State) -> None:
        content = self._generate_content(state)
        await channel.send(content)

        # 更新状态
        state.last_morning_report = datetime.now(timezone.utc)
        state.morning_report_count += 1

    def _generate_content(self, state: State) -> str:
        """
        生成早报正文。
        TODO: 替换为 Gemini API 调用。
        """
        now_cst  = datetime.now(timezone.utc) + timedelta(hours=8)
        date_str = now_cst.strftime("%Y-%m-%d")
        weekday  = ["周一","周二","周三","周四","周五","周六","周日"][now_cst.weekday()]

        topics = "\n".join(
            f"> {i+1}. {t}" for i, t in enumerate(self._TEST_TOPICS)
        )

        # 如果 market_scan 有数据则附上
        scan_note = ""
        if state.latest_scan_summary:
            scan_note = f"\n\n**昨日扫描摘要**\n> {state.latest_scan_summary}"

        return (
            f"🌅 **投研早报  {date_str} {weekday}**\n\n"
            f"**今日关注主题** `[测试模式]`\n"
            f"{topics}"
            f"{scan_note}\n\n"
            f"_生成时间: {now_cst.strftime('%H:%M')} CST_"
        )
