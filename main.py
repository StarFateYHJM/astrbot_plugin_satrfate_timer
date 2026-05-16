import asyncio
import time
import aiohttp
from astrbot.api.star import Context, Star, register
from astrbot.api.message_components import Plain, At
from astrbot.api import logger

class _MessageWrapper:
    def __init__(self, chain):
        self.chain = chain

@register("satrfate_timer", "Satrfate", "极简定时问候插件", "1.6.1")
class TimerPlugin(Star):
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.config = config or {}
        self.debug = self.config.get("debug", False)
        self.tasks = self.config.get("tasks", [])
        self.use_llm = self.config.get("use_llm", False)
        self.api_base = self.config.get("api_base", "https://api.deepseek.com/v1")
        self.api_key = self.config.get("api_key", "")
        self.model = self.config.get("model", "deepseek-v4-flash")
        self.system_prompt = self.config.get("system_prompt", "")
        self.use_network_time = self.config.get("use_network_time", True)
        self._sent_today = set()
        self._last_triggered_time = None

        logger.info(f"[Timer] 已加载 {len(self.tasks)} 个任务")
        logger.info(f"[Timer] LLM: {'开' if self.use_llm else '关'} | 网络校准: {'开' if self.use_network_time else '关'}")
        for i, t in enumerate(self.tasks):
            logger.info(f"[Timer] 任务{i+1}: {t.get('time')} -> {t.get('umo','')[:30]}...")

        asyncio.create_task(self._loop())

    def _log(self, msg, level="info"):
        if self.debug or level != "debug":
            getattr(logger, level)(f"[Timer] {msg}")

    async def _loop(self):
        self._log("循环已启动", "debug")
        last_sync = 0
        cache_now = time.strftime("%H:%M")

        while True:
            if self.use_network_time and time.time() - last_sync > 30:
                net = await self._get_network_time()
                if net:
                    cache_now = net
                    last_sync = time.time()
                    self._log(f"网络校准: {cache_now}", "debug")
                else:
                    cache_now = time.strftime("%H:%M")
                    if not hasattr(self, '_net_warned'):
                        self._net_warned = True
                        logger.warning("[Timer] 网络校准失败，使用系统时间")

            if not self.use_network_time:
                cache_now = time.strftime("%H:%M")

            today = time.strftime("%Y-%m-%d")

            for i, task in enumerate(self.tasks):
                task_time = task.get("time", "")
                if cache_now != task_time:
                    continue

                if self._last_triggered_time == cache_now:
                    continue

                key = f"{i}-{today}"
                if key in self._sent_today:
                    self._log(f"任务{i+1} 今日已发送，跳过", "debug")
                    continue

                self._sent_today.add(key)
                self._last_triggered_time = cache_now
                logger.info(f"[Timer] 触发 {task_time}")
                await self._execute_task(task)

            await asyncio.sleep(1)

    async def _get_network_time(self):
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get("https://timeapi.io/api/Time/current/zone?timeZone=Asia/Shanghai", timeout=5) as r:
                    if r.status == 200:
                        d = await r.json()
                        return f"{int(d['hour']):02d}:{int(d['minute']):02d}"
        except Exception:
            pass
        return None

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
            logger.info(f"[Timer] 发送成功{' (@全体)' if at_all else ''}: {text[:50]}...")
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
        self._log("已卸载", "debug")
