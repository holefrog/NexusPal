"""
state.py  –  全局运行状态
由 agent 创建单例，传给每次 skill 调用。
重启后清零（当前阶段不需要持久化）。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class State:
    # ── 调度执行记录 ─────────────────────────────────────────
    last_morning_report: datetime | None = None
    last_evening_report: datetime | None = None
    last_market_scan:    datetime | None = None

    # ── 计数 ─────────────────────────────────────────────────
    morning_report_count: int = 0
    evening_report_count: int = 0
    market_scan_count:    int = 0

    # ── skill 间共享的临时数据（按需扩展）───────────────────
    # 例如：market_scan 写入，report 读取
    latest_scan_summary: str = ""

    # ── 通用扩展槽（不想改 dataclass 时用）──────────────────
    extra: dict[str, Any] = field(default_factory=dict)
