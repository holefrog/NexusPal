"""
agent.py  –  投研 Agent 主进程
职责：
  1. Discord client + slash commands
  2. APScheduler 定时调度（早报 / 晚报 / 市场扫描）
  3. 维护全局 State，传给每次 skill 调用
"""

import asyncio
import logging
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import discord
import psutil
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from skills import invoke
from skills.market_scan import MarketScanSkill
from skills.report_evening import ReportEveningSkill
from skills.report_morning import ReportMorningSkill
from state import State

# ═══════════════════════════════════════════════════════════════
# 日志
# ═══════════════════════════════════════════════════════════════
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("invest.agent")

# ═══════════════════════════════════════════════════════════════
# 配置加载
# ═══════════════════════════════════════════════════════════════
load_dotenv(Path(__file__).parent / ".env")


def _require(key: str) -> str:
    val = os.getenv(key, "").strip()
    if not val:
        log.critical("缺少必要环境变量: %s  (检查 .env)", key)
        sys.exit(1)
    return val


def _optional(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


BOT_TOKEN         = _require("DISCORD_BOT_TOKEN")
REPORT_CHANNEL_ID = int(_require("REPORT_CHANNEL_ID"))
GUILD_ID          = int(_require("GUILD_ID"))
_admin_raw        = _optional("ADMIN_CHANNEL_ID")
ADMIN_CHANNEL_ID  = int(_admin_raw) if _admin_raw else None

MORNING_CRON      = _optional("MORNING_REPORT_CRON",          "0 0 * * *")
EVENING_CRON      = _optional("EVENING_REPORT_CRON",          "0 12 * * *")
SCAN_INTERVAL_MIN = int(_optional("MARKET_SCAN_INTERVAL_MINUTES", "15"))

_START_TIME = datetime.now(timezone.utc)

# ═══════════════════════════════════════════════════════════════
# 全局状态（单例）
# ═══════════════════════════════════════════════════════════════
state = State()

# skill 实例（单例，整个进程复用）
_skill_morning = ReportMorningSkill()
_skill_evening = ReportEveningSkill()
_skill_scan    = MarketScanSkill()

# ═══════════════════════════════════════════════════════════════
# Bot 初始化
# ═══════════════════════════════════════════════════════════════
intents = discord.Intents.default()
intents.message_content = True
bot       = commands.Bot(command_prefix="!", intents=intents)
# bot.tree      = app_commands.Commandbot.tree(bot)
GUILD_OBJ = discord.Object(id=GUILD_ID)
scheduler = AsyncIOScheduler(timezone="UTC")

# ═══════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════
def _get_report_channel() -> discord.TextChannel | None:
    return bot.get_channel(REPORT_CHANNEL_ID)


def _uptime_str() -> str:
    delta = datetime.now(timezone.utc) - _START_TIME
    h, rem = divmod(int(delta.total_seconds()), 3600)
    m, s   = divmod(rem, 60)
    return f"{h}h {m}m {s}s"


def _bar(pct: float, width: int = 10) -> str:
    filled = round(pct / 100 * width)
    return f"[{'█' * filled}{'░' * (width - filled)}] {pct:.1f}%"


def _sys_stats() -> dict:
    mem  = psutil.virtual_memory()
    swap = psutil.swap_memory()
    disk = psutil.disk_usage("/")
    return {
        "cpu_pct"   : psutil.cpu_percent(interval=0.5),
        "cpu_cores" : psutil.cpu_count(),
        "mem_total" : mem.total  // (1024 ** 2),
        "mem_used"  : mem.used   // (1024 ** 2),
        "mem_pct"   : mem.percent,
        "swap_total": swap.total // (1024 ** 2),
        "swap_used" : swap.used  // (1024 ** 2),
        "swap_pct"  : swap.percent,
        "disk_total": disk.total // (1024 ** 3),
        "disk_used" : disk.used  // (1024 ** 3),
        "disk_pct"  : disk.percent,
    }


def _build_status_embed() -> discord.Embed:
    s = _sys_stats()
    worst = max(s["cpu_pct"], s["mem_pct"], s["disk_pct"])
    color = 0xED4245 if worst >= 85 else (0xFEE75C if worst >= 60 else 0x57F287)

    embed = discord.Embed(
        title="🖥️  投研节点状态",
        color=color,
        timestamp=datetime.now(timezone.utc),
    )
    embed.add_field(name="主机",     value=f"`{platform.node()}`",                   inline=True)
    embed.add_field(name="运行时长", value=f"`{_uptime_str()}`",                     inline=True)
    embed.add_field(name="延迟",     value=f"`{round(bot.latency * 1000)} ms`",      inline=True)
    embed.add_field(name=f"CPU ({s['cpu_cores']} 核)",
                    value=f"`{_bar(s['cpu_pct'])}`",                                  inline=False)
    embed.add_field(name=f"内存  {s['mem_used']} / {s['mem_total']} MB",
                    value=f"`{_bar(s['mem_pct'])}`",                                  inline=False)
    if s["swap_total"] > 0:
        embed.add_field(name=f"Swap  {s['swap_used']} / {s['swap_total']} MB",
                        value=f"`{_bar(s['swap_pct'])}`",                             inline=False)
    else:
        embed.add_field(name="Swap", value="`未启用`",                                inline=False)
    embed.add_field(name=f"磁盘 /  {s['disk_used']} / {s['disk_total']} GB",
                    value=f"`{_bar(s['disk_pct'])}`",                                 inline=False)

    # 调度状态
    jobs_info = []
    for job in scheduler.get_jobs():
        next_run = job.next_run_time
        next_str = next_run.strftime("%m-%d %H:%M UTC") if next_run else "未知"
        jobs_info.append(f"{job.name}: `{next_str}`")
    if jobs_info:
        embed.add_field(name="下次调度", value="\n".join(jobs_info), inline=False)

    embed.set_footer(text=f"Python {sys.version.split()[0]} · discord.py {discord.__version__}")
    return embed


# ═══════════════════════════════════════════════════════════════
# 调度任务（由 scheduler 调用，也可由 slash command 直接调用）
# ═══════════════════════════════════════════════════════════════
async def run_morning_report():
    ch = _get_report_channel()
    if ch:
        await invoke(_skill_morning, ch, state)


async def run_evening_report():
    ch = _get_report_channel()
    if ch:
        await invoke(_skill_evening, ch, state)


async def run_market_scan():
    ch = _get_report_channel()
    if ch:
        await invoke(_skill_scan, ch, state)


# ═══════════════════════════════════════════════════════════════
# 事件：登录成功
# ═══════════════════════════════════════════════════════════════
@bot.event
async def on_ready():
    log.info("已登录: %s (id=%s)", bot.user, bot.user.id)

    # 注册 slash commands（guild 级，秒生效）
    try:
        bot.tree.copy_global_to(guild=GUILD_OBJ)
        synced = await bot.tree.sync(guild=GUILD_OBJ)
        log.info("Slash commands 已同步: %d 条", len(synced))
    except Exception as e:
        log.error("Slash commands 同步失败: %s", e)

    # 启动调度器（幂等：重连时不重复启动）
    if not scheduler.running:
        # 解析 cron 字符串（格式：分 时 日 月 周）
        def _parse_cron(cron_str: str) -> dict:
            parts = cron_str.split()
            keys  = ["minute", "hour", "day", "month", "day_of_week"]
            return dict(zip(keys, parts))

        morning_cron = _parse_cron(MORNING_CRON)
        evening_cron = _parse_cron(EVENING_CRON)

        scheduler.add_job(
            run_morning_report,
            CronTrigger(**morning_cron, timezone="UTC"),
            name="早报",
            id="morning_report",
            replace_existing=True,
        )
        scheduler.add_job(
            run_evening_report,
            CronTrigger(**evening_cron, timezone="UTC"),
            name="晚报",
            id="evening_report",
            replace_existing=True,
        )
        scheduler.add_job(
            run_market_scan,
            IntervalTrigger(minutes=SCAN_INTERVAL_MIN),
            name="市场扫描",
            id="market_scan",
            replace_existing=True,
        )
        scheduler.start()
        log.info(
            "调度器已启动 — 早报: %s  晚报: %s  扫描: 每 %d 分钟",
            MORNING_CRON, EVENING_CRON, SCAN_INTERVAL_MIN,
        )

    # 上线通知
    report_ch = _get_report_channel()
    if report_ch:
        await report_ch.send(
            "✅ **投研节点已就绪**\n"
            f"> 主机 `{platform.node()}` · Python {sys.version.split()[0]}\n"
            "> 输入 `/` 可查看可用指令"
        )
    else:
        log.error("找不到 report channel_id=%s", REPORT_CHANNEL_ID)

    if ADMIN_CHANNEL_ID:
        admin_ch = bot.get_channel(ADMIN_CHANNEL_ID)
        if admin_ch:
            await admin_ch.send("🔧 **Agent online**", embed=_build_status_embed())


# ═══════════════════════════════════════════════════════════════
# Slash Commands
# ═══════════════════════════════════════════════════════════════

@bot.tree.command(name="ping", description="检查 bot 延迟")
async def slash_ping(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"🏓 Pong!  延迟 **{round(bot.latency * 1000)} ms**",
        ephemeral=True,
    )
    log.info("/ping 来自 %s", interaction.user)


@bot.tree.command(name="status", description="查看服务器资源与调度状态")
async def slash_status(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    embed = await asyncio.get_event_loop().run_in_executor(None, _build_status_embed)
    await interaction.followup.send(embed=embed, ephemeral=True)
    log.info("/status 来自 %s", interaction.user)


# ── /report 指令组 ────────────────────────────────────────────
report_group = app_commands.Group(name="report", description="手动触发报告")


@report_group.command(name="morning", description="立即生成并发送早报")
async def slash_report_morning(interaction: discord.Interaction):
    await interaction.response.send_message("📤 正在生成早报...", ephemeral=True)
    await run_morning_report()
    log.info("/report morning 来自 %s", interaction.user)


@report_group.command(name="evening", description="立即生成并发送晚报")
async def slash_report_evening(interaction: discord.Interaction):
    await interaction.response.send_message("📤 正在生成晚报...", ephemeral=True)
    await run_evening_report()
    log.info("/report evening 来自 %s", interaction.user)


bot.tree.add_command(report_group)


# ── /scan ─────────────────────────────────────────────────────
@bot.tree.command(name="scan", description="立即执行一次市场扫描")
async def slash_scan(interaction: discord.Interaction):
    await interaction.response.send_message("🔍 正在扫描...", ephemeral=True)
    await run_market_scan()
    log.info("/scan 来自 %s", interaction.user)


# ── /reboot ───────────────────────────────────────────────────
class RebootView(discord.ui.View):
    def __init__(self, requester: discord.User | discord.Member):
        super().__init__(timeout=30)
        self.requester = requester
        self._message: discord.Message | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.requester.id:
            await interaction.response.send_message("⛔ 只有指令触发者才能确认", ephemeral=True)
            return False
        return True

    def _disable_all(self):
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]

    @discord.ui.button(label="取消", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self._disable_all()
        await interaction.response.edit_message(content="✅ 已取消，服务继续运行", view=self)
        self.stop()
        log.info("/reboot 取消，来自 %s", interaction.user)

    @discord.ui.button(label="确认重启", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self._disable_all()
        await interaction.response.edit_message(
            content="🔄 **正在重启...**  systemd 将在数秒内拉起服务", view=self
        )
        self.stop()
        log.warning("/reboot 已确认，来自 %s", interaction.user)
        await asyncio.sleep(1.5)
        await bot.close()

    async def on_timeout(self):
        self._disable_all()
        if self._message:
            try:
                await self._message.edit(content="⏱️ 超时未确认，已自动取消（默认否）", view=self)
            except discord.NotFound:
                pass


@bot.tree.command(name="reboot", description="重启 agent 进程（需确认，默认取消）")
async def slash_reboot(interaction: discord.Interaction):
    view = RebootView(requester=interaction.user)
    await interaction.response.send_message(
        "⚠️ **确认要重启 agent 进程吗？**\n"
        "> systemd 会在数秒内自动拉起，期间暂停服务\n"
        "> 30 秒内未确认将自动取消",
        view=view,
        ephemeral=True,
    )
    view._message = await interaction.original_response()
    log.info("/reboot 触发，来自 %s", interaction.user)


# ═══════════════════════════════════════════════════════════════
# 错误处理
# ═══════════════════════════════════════════════════════════════
@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError,
):
    log.error("Slash command 错误: %s", error)
    msg = "⚠️ 指令执行出错，请稍后重试"
    if interaction.response.is_done():
        await interaction.followup.send(msg, ephemeral=True)
    else:
        await interaction.response.send_message(msg, ephemeral=True)


# ═══════════════════════════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    try:
        bot.run(BOT_TOKEN, log_handler=None)
    except discord.LoginFailure:
        log.critical("Token 无效，请检查 .env 中的 DISCORD_BOT_TOKEN")
        sys.exit(1)
    except KeyboardInterrupt:
        log.info("收到中断信号，正常退出")
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)
