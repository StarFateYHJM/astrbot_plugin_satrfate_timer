import asyncio
import time
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.message_components import Plain

class _MessageWrapper:
    def __init__(self, chain):
        self.chain = chain

@register("satrfate_timer", "Satrfate", "极简定时问候插件", "1.1.5")
class TimerPlugin(Star):
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.config = config or {}
        self.tasks = self.config.get("tasks", [])
        self.use_network_time = self.config.get("use_network_time", True)
        self.use_llm = self.config.get("use_llm", False)
        self.api_base = self.config.get("api_base", "https://api.deepseek.com/v1")
        self.api_key = self.config.get("api_key", "")
        self.model = self.config.get("model", "deepseek-chat")
        self._sent_today = {}

        logger.info(f"[Timer] 插件已加载，读取到 {len(self.tasks)} 个定时任务")
        logger.info(f"[Timer] LLM模式: {'开启' if self.use_llm else '关闭'}")
        if self.use_llm:
            logger.info(f"[Timer] API: {self.api_base}, Model: {self.model}")
        for i, task in enumerate(self.tasks):
            logger.info(f"[Timer] 任务{i+1}: time={task.get('time')}, umo={task.get('umo')}, prompt={task.get('prompt', '')[:30]}...")

        asyncio.create_task(self._loop())

    async def _loop(self):
        logger.info("[Timer] 定时任务循环已启动")
        last_sync = 0
        cache_now = time.strftime("%H:%M")

        while True:
            if self.use_network_time and time.time() - last_sync > 30:
                net_time = await self._get_network_time()
                if net_time:
                    cache_now = net_time
                    last_sync = time.time()
                else:
                    cache_now = time.strftime("%H:%M")
                    logger.warning("[Timer] 网络时间获取失败，降级使用系统时间")

            if not self.use_network_time:
                cache_now = time.strftime("%H:%M")

            today = time.strftime("%Y-%m-%d")

            for i, task in enumerate(self.tasks):
                task_time = task.get("time", "")
                if cache_now == task_time:
                    task_key = f"{i}-{today}"
                    if task_key not in self._sent_today:
                        self._sent_today[task_key] = True
                        logger.info(f"[Timer] 触发定时任务: {task_time}")
                        await self._execute_task(task)

            await asyncio.sleep(1)

    async def _get_network_time(self):
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get("https://timeapi.io/api/Time/current/zone?timeZone=Asia/Shanghai", timeout=5) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return f"{int(data['hour']):02d}:{int(data['minute']):02d}"
        except Exception as e:
            logger.error(f"[Timer] 获取网络时间失败: {e}")
        return None

    async def _execute_task(self, task: dict):
        umo = task.get("umo", "")
        raw_prompt = task.get("prompt", "你好~")

        if not umo:
            logger.error("[Timer] 任务缺少 UMO，已跳过")
            return

        if self.use_llm:
            final_text = await self._generate_text(raw_prompt)
            if not final_text:
                logger.error("[Timer] LLM生成失败，跳过此任务")
                return
        else:
            final_text = raw_prompt

        try:
            msg_chain = [Plain(final_text)]
            wrapper = _MessageWrapper(msg_chain)
            await self.context.send_message(umo, wrapper)
            logger.info(f"[Timer] 消息发送成功: {final_text[:50]}...")
        except Exception as e:
            logger.error(f"[Timer] 发送消息失败: {e}")

    async def _generate_text(self, prompt: str) -> str:
        """调用通用 LLM API 生成文本"""
        try:
            import aiohttp

            if not self.api_key:
                logger.error("[Timer] 缺少 api_key")
                return ""

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 500,
                "temperature": 0.8
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_base}/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        content = data["choices"][0]["message"]["content"]
                        return content.strip()
                    else:
                        logger.error(f"[Timer] API请求失败: {resp.status}")
                        return ""
        except Exception as e:
            logger.error(f"[Timer] LLM生成失败: {e}")
            return ""

    async def terminate(self):
        logger.info("[Timer] 插件已卸载")
