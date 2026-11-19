import asyncio
import json

from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, StarTools

from .advisor import Advisor


class StarRailAdvisor(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.advisor = Advisor(StarTools.get_data_dir("astrbot_plugin_hsr_advisor"))

    async def _query(self, fn, *args):
        try:
            result = await asyncio.to_thread(fn, *args)
        except (ValueError, OSError) as exc:
            result = {"查询失败": str(exc), "提示": "向群友说明缺少已核对的数据。"}
        return json.dumps(result, ensure_ascii=False)

    @filter.llm_tool(name="hsr_regular")
    async def regular(self, event: AstrMessageEvent, name: str, level: int = 0):
        """星铁常规配队和光锥选择。查询一个角色的技能、机制和星魂或一个光锥的各阶效果。

        Args:
            name(string): 一个角色或光锥的中文名称、常用别名或游戏 ID。
            level(number): 技能等级，填 0 取普攻6、其他10，按技能等级上限截取。光锥始终返回五阶。
        """
        if not isinstance(level, (int, float)) or level not in range(16):
            return "技能等级应为 0 至 15 的整数"
        return await self._query(self.advisor.regular, name, int(level))

    @filter.llm_tool(name="hsr_currency")
    async def currency(self, event: AstrMessageEvent, name: str):
        """查询星铁货币战争当前赛季某个员工、羁绊、装备、投资策略、环境或主角光环的实际效果。

        Args:
            name(string): 赛季条目名称或 ID，模糊名称会列出候选。
        """
        return await self._query(self.advisor.currency, name)

    @filter.llm_tool(name="hsr_currency_guides")
    async def guides(self, event: AstrMessageEvent, role: str = ""):
        """查询星铁货币战争当前版本与赛季的热门阵容、前后台站位、投资方向、装备与过渡思路。

        Args:
            role(string): 指定一个核心员工的完整中文名或 ID，空字符串查本季热门。
        """
        return await self._query(self.advisor.currency, role, True)

    @filter.command("星铁数据")
    async def status(self, event: AstrMessageEvent):
        """检查两个资料源并显示版本与缓存状态。"""
        outputs = await asyncio.gather(
            self._query(self.advisor.regular, "1001"),
            self._query(self.advisor.currency, "投资环境"),
        )
        lines = []
        for label, output in zip(("常规战斗", "货币战争"), outputs):
            row = json.loads(output)
            if "查询失败" in row:
                lines.append(f"{label}：{row['查询失败']}")
                continue
            version = (
                row.get("来源提交日期")
                or f"{row['游戏版本']} 赛季 {row['赛季']}.{row['子赛季']}"
            )
            state = "上游暂不可达，使用旧缓存" if row["刷新失败沿用缓存"] else "可用"
            lines.append(f"{label}：{version}，{state}。上次核对 {row['上次核对']}")
        yield event.plain_result("\n".join(lines))
