"""
skills/market_scan.py  –  市场扫描 skill（每 N 分钟触发）
当前：测试阶段，输出扫描时间戳 + 占位结果。
后续：接入 yfinance / Gemini 实现真实扫描逻辑。
扫描结果写入 state.latest_scan_summary 供报告 skill 读取。
"""

from datetime import datetime, timezone, timedelta

import discord

from skills import BaseSkill
from state import State


class MarketScanSkill(BaseSkill):
    name = "市场扫描"

    # 扫描结果只在有异常信号时才发到 channel，否则静默
    # 测试阶段：每次都发，方便验证
    SILENT_ON_NORMAL = False   # TODO: 生产环境改为 True

    async def run(self, channel: discord.TextChannel, state: State) -> None:
        summary = self._scan(state)

        # 写入共享状态，供早晚报读取
        state.latest_scan_summary = summary
        state.last_market_scan    = datetime.now(timezone.utc)
        state.market_scan_count  += 1

        if not self.SILENT_ON_NORMAL:
            now_cst = datetime.now(timezone.utc) + timedelta(hours=8)
            await channel.send(
                f"🔍 **市场扫描 #{state.market_scan_count}**  "
                f"`{now_cst.strftime('%H:%M')} CST`\n"
                f"> {summary} `[测试模式]`"
            )

    def _scan(self, state: State) -> str:
        """
        执行市场扫描，返回摘要字符串。
        TODO: 替换为 yfinance + Gemini 实现。
        """
        now_utc = datetime.now(timezone.utc)
        return f"扫描完成，无异常信号  ({now_utc.strftime('%H:%M')} UTC)"
