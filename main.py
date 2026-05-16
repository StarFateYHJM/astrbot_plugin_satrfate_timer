import asyncio
import time
import aiohttp
from astrbot.api.star import Context, Star, register
from astrbot.api.message_components import Plain, At
from astrbot.api import logger

class _MessageWrapper:
    def __init__(self, chain):
        self.chain = chain

@register("satrfate_timer", "YHJM", "极简定时问候插件", "1.7.1")
class TimerPlugin(Star):
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.config = config or {}
        self.tasks = self.config.get("tasks", [])
        self.use_llm = self.config.get("use_llm", False)
        self.api_base = self.config.get("api_base", "https://api.deepseek.com/v1")
        self.api_key = self.config.get("api_key", "")
        self.model = self.config.get("model", "deepseek-v4-flash")
        self.system_prompt = self.config.get("system_prompt", "")
        self._sent_today = set()

        logger.info(f"[Timer] 已加载 {len(self.tasks)} 个任务")
        for i, t in enumerate(self.tasks):
            logger.info(f"[Timer] 任务{i+1}: {t.get('time')} -> {t.get('umo','')[:30]}...")

        asyncio.create_task(self._loop())

    async def _loop(self):
        while True:
            now = time.strftime("%H:%M")
            today = time.strftime("%Y-%m-%d")

            for i, task in enumerate(self.tasks):
                if now != task.get("time", ""):
                    continue

                key = f"{i}-{today}"
                if key in self._sent_today:
                    continue

                self._sent_today.add(key)
                logger.info(f"[Timer] 触发 {task.get('time')}")
                await self._execute_task(task)

            await asyncio.sleep(1)

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
        pass
