import asyncio
import time
import re
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

@register("satrfate_timer", "Satrfate", "极简定时问候插件", "1.0.4")
class TimerPlugin(Star):
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.config = config or {}
        self.tasks = self.config.get("tasks", [])
        self._sent_today = {}
        self._one_time_tasks = []
        
        logger.info(f"[Timer] 插件已加载，读取到 {len(self.tasks)} 个定时任务")
        for i, task in enumerate(self.tasks):
            logger.info(f"[Timer] 任务{i+1}: time={task.get('time')}, umo={task.get('umo')}, prompt={task.get('prompt', '')[:30]}...")
        
        asyncio.create_task(self._loop())

    async def _loop(self):
        """每秒检查一次定时任务和一次性任务"""
        logger.info("[Timer] 定时任务循环已启动")
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
                        logger.info(f"[Timer] 触发定时任务: {task_time}")
                        await self._execute_task(task)

            # 处理一次性测试任务
            for task in self._one_time_tasks[:]:
                if current_ts >= task["trigger_ts"]:
                    logger.info(f"[Timer] 触发一次性任务")
                    await self._execute_task(task)
                    self._one_time_tasks.remove(task)

            await asyncio.sleep(1)

    async def _execute_task(self, task: dict):
        """执行任务：发送消息到目标会话"""
        try:
            umo = task.get("umo", "")
            prompt = task.get("prompt", "你好~")

            if not umo:
                logger.error("[Timer] 任务缺少 UMO，已跳过")
                return

            logger.info(f"[Timer] 正在发送消息到 {umo}: {prompt[:50]}...")
            await self.context.send_message(umo, prompt)
            logger.info(f"[Timer] 消息发送成功")
        except Exception as e:
            logger.error(f"[Timer] 发送消息失败: {e}")

    # ========== 测试指令 /test ==========
    @filter.command("test")
    async def cmd_test(self, event: AstrMessageEvent, message: str):
        parts = message.strip().rsplit(" ", 1)
        if len(parts) != 2 or not parts[1].isdigit():
            yield event.plain_result("❌ 格式错误，正确用法：/test <内容> <秒数>\n例如：/test 鸽鸽鸽 5")
            return

        content = parts[0].strip()
        seconds = int(parts[1])

        if seconds <= 0 or seconds > 300:
            yield event.plain_result("❌ 秒数需在 1-300 之间")
            return

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
