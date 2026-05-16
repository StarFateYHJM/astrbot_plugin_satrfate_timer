import asyncio
import time
import re
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

@register("satrfate_timer", "Satrfate", "极简定时问候插件", "1.0.3")
class TimerPlugin(Star):
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.config = config or {}
        self.tasks = self.config.get("tasks", [])
        self._sent_today = {}
        self._one_time_tasks = []
        asyncio.create_task(self._loop())

    async def _loop(self):
        """每秒检查一次定时任务和一次性任务"""
        while True:
            now = time.strftime("%H:%M")
            today = time.strftime("%Y-%m-%d")
            current_ts = time.time()

            # 处理日常定时任务
            for i, task in enumerate(self.tasks):
                task_time = task.get("time", "")
                if now == task_time:
                    task_key = f"{i}-{today}"
                    if task_key not in self._sent_today:
                        self._sent_today[task_key] = True
                        await self._execute_task(task)
                        logger.info(f"[Timer] 已发送 {task_time} 的定时消息")

            # 处理一次性测试任务
            for task in self._one_time_tasks[:]:
                if current_ts >= task["trigger_ts"]:
                    await self._execute_task(task)
                    self._one_time_tasks.remove(task)
                    logger.info(f"[Timer] 已发送一次性测试消息")

            await asyncio.sleep(1)

    async def _execute_task(self, task: dict):
        """执行任务：发送消息到目标会话"""
        try:
            umo = task.get("umo", "")
            prompt = task.get("prompt", "你好~")

            if not umo:
                logger.error("[Timer] 任务缺少 UMO，已跳过")
                return

            await self.context.send_message(umo, prompt)
        except Exception as e:
            logger.error(f"[Timer] 发送消息失败: {e}")

    # ========== 测试指令 /test ==========
    @filter.command("test")
    async def cmd_test(self, event: AstrMessageEvent, message: str):
        """
        一次性测试任务：/test <内容> <秒数>
        例如：/test 鸽鸽鸽 5
        """
        match = re.match(r"(.+?)\s+(\d+)$", message.strip())
        if not match:
            yield event.plain_result("❌ 格式错误，正确用法：/test <内容> <秒数>\n例如：/test 鸽鸽鸽 5")
            return

        content = match.group(1).strip()
        seconds = int(match.group(2))

        if seconds <= 0 or seconds > 300:
            yield event.plain_result("❌ 秒数需在 1-300 之间")
            return

        # 使用当前会话的 UMO
        umo = event.unified_msg_origin

        task = {
            "umo": umo,
            "prompt": content,
            "trigger_ts": time.time() + seconds
        }
        self._one_time_tasks.append(task)

        yield event.plain_result(f"✅ 已设置一次性任务，{seconds} 秒后发送：{content}")

    async def terminate(self):
        logger.info("[Timer] 插件已卸载")
