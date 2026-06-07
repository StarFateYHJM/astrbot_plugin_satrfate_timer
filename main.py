import asyncio
import time
import aiohttp
from datetime import datetime, timedelta
from astrbot.api.star import Context, Star, register
from astrbot.api.message_components import Plain, At
from astrbot.api import logger

class _MessageWrapper:
    def __init__(self, chain):
        self.chain = chain

@register("satrfate_timer", "YHJM", "极简定时问候插件", "2.1.0")
class TimerPlugin(Star):
    _instance = None          # 类级别单例
    _running_tasks = []       # 记录所有定时协程

    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)

        # 如果已有旧实例在运行，先清理干净
        if TimerPlugin._instance is not None:
            logger.warning("[Timer] 检测到旧实例，正在清理...")
            try:
                TimerPlugin._instance.terminate()
            except Exception as e:
                logger.error(f"[Timer] 清理旧实例失败: {e}")

        # 注册为新实例
        TimerPlugin._instance = self

        self.config = config or {}
        self.tasks = self.config.get("tasks", [])
        self.use_llm = self.config.get("use_llm", False)
        self.api_base = self.config.get("api_base", "https://api.deepseek.com/v1")
        self.api_key = self.config.get("api_key", "")
        self.model = self.config.get("model", "deepseek-v4-flash")
        self.system_prompt = self.config.get("system_prompt", "")

        logger.info(f"[Timer] 已加载 {len(self.tasks)} 个任务 (实例 id={id(self)})")
        for i, t in enumerate(self.tasks):
            logger.info(f"[Timer] 任务{i+1}: {t.get('time')} -> {t.get('umo','')[:30]}...")

        # 启动定时任务，并保存 task 引用，方便后续取消
        self._my_tasks = []
        for i, task in enumerate(self.tasks):
            t = asyncio.create_task(self._run_task(i, task))
            self._my_tasks.append(t)

    async def _run_task(self, idx, task):
        time_str = task.get("time", "")
        if not time_str:
            return

        try:
            h, m = map(int, time_str.split(":"))
        except ValueError:
            logger.error(f"[Timer] 任务{idx} 时间格式错误: {time_str}")
            return

        while True:
            now = datetime.now()
            target = now.replace(hour=h, minute=m, second=0, microsecond=0)

            if target <= now:
                target += timedelta(days=1)

            wait_seconds = (target - now).total_seconds()
            logger.info(f"[Timer] 任务{idx} 下次触发: {target.strftime('%Y-%m-%d %H:%M:%S')} (等待 {wait_seconds:.0f} 秒)")

            try:
                await asyncio.sleep(wait_seconds)
            except asyncio.CancelledError:
                logger.info(f"[Timer] 任务{idx} 被取消")
                break

            logger.info(f"[Timer] 触发 任务{idx} {time_str}")
            await self._execute_task(task)

    async def _execute_task(self, task):
        umo = task.get("umo", "")
        prompt = task.get("prompt", "你好~")
        at_all = task.get("at_all", False)

        if not umo:
            return

        text = prompt
        if self.use_llm:
            gen = await self._generate_text(prompt)
            if gen:
                text = gen
            else:
                logger.error("[Timer] LLM生成失败")
                return

        try:
            chain = []
            if at_all:
                chain.append(At(qq="all"))
            chain.append(Plain(text))
            wrapper = _MessageWrapper(chain)
            await self.context.send_message(umo, wrapper)
            logger.info(f"[Timer] 发送成功: {text[:50]}...")
        except Exception as e:
            logger.error(f"[Timer] 发送失败: {e}")

    async def _generate_text(self, prompt):
        try:
            if not self.api_key:
                logger.error("[Timer] 缺少 api_key")
                return ""
            headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": self.system_prompt or "请用中文回复。"},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 1024,
                "temperature": 0.8
            }
            async with aiohttp.ClientSession() as s:
                async with s.post(f"{self.api_base}/chat/completions", json=payload, headers=headers, timeout=30) as r:
                    if r.status == 200:
                        d = await r.json()
                        return d["choices"][0]["message"]["content"].strip()
        except Exception:
            pass
        return ""

    async def terminate(self):
        """终止所有定时任务"""
        logger.info("[Timer] 正在终止所有定时任务...")
        for t in getattr(self, '_my_tasks', []):
            t.cancel()
        # 等待任务真正结束
        if self._my_tasks:
            await asyncio.gather(*self._my_tasks, return_exceptions=True)
        logger.info("[Timer] 所有定时任务已终止")
