import asyncio
import time
from astrbot.api.star import Context, Star, register
from astrbot.api.message_components import Plain
from astrbot.api import logger

class _MessageWrapper:
    """包装消息链，兼容 send_message 要求 .chain 属性的对象"""
    def __init__(self, chain):
        self.chain = chain

@register("satrfate_timer", "Satrfate", "极简定时问候插件", "1.2.5")
class TimerPlugin(Star):
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.config = config or {}
        self.debug = self.config.get("debug", False)
        self.tasks = self.config.get("tasks", [])
        self.use_network_time = self.config.get("use_network_time", True)
        self.timezone = self.config.get("timezone", "Asia/Shanghai")
        self.use_llm = self.config.get("use_llm", False)
        self.api_base = self.config.get("api_base", "https://api.deepseek.com/v1")
        self.api_key = self.config.get("api_key", "")
        self.model = self.config.get("model", "deepseek-v4-flash")
        self.system_prompt = self.config.get("system_prompt", "")
        self._sent_today = {}
        self._last_sent = {}

        # 插件启动信息始终输出
        logger.info(f"[Timer] 插件已加载，读取到 {len(self.tasks)} 个定时任务")
        logger.info(f"[Timer] LLM模式: {'开启' if self.use_llm else '关闭'}")
        logger.info(f"[Timer] 网络时间校准: {'开启' if self.use_network_time else '关闭'}, 时区: {self.timezone}")
        if self.use_llm:
            logger.info(f"[Timer] API: {self.api_base}, Model: {self.model}")
        for i, task in enumerate(self.tasks):
            logger.info(f"[Timer] 任务{i+1}: time={task.get('time')}, umo={task.get('umo')}, prompt={task.get('prompt', '')[:30]}...")

        asyncio.create_task(self._loop())

    # ========== 统一的日志方法（参考入群欢迎插件） ==========
    def _log(self, msg: str, level: str = "info"):
        """根据 debug 开关输出日志，debug 日志仅在开启时输出"""
        if self.debug or level != "debug":
            getattr(logger, level)(f"[Timer] {msg}")

    async def _loop(self):
        self._log("定时任务循环已启动", "info")
        last_sync = 0
        cache_now = time.strftime("%H:%M")

        while True:
            # 网络时间校准
            if self.use_network_time and time.time() - last_sync > 30:
                net_time = await self._get_network_time()
                if net_time:
                    cache_now = net_time
                    last_sync = time.time()
                    self._log(f"网络时间校准成功: {cache_now}", "debug")
                else:
                    cache_now = time.strftime("%H:%M")
                    self._log("网络时间获取失败，降级使用系统时间", "warning")
            if not self.use_network_time:
                cache_now = time.strftime("%H:%M")

            today = time.strftime("%Y-%m-%d")

            # 检查每个任务
            for i, task in enumerate(self.tasks):
                task_time = task.get("time", "")
                if cache_now == task_time:
                    task_key = f"{task.get('time')}-{task.get('umo')}-{today}"
                    now_ts = time.time()
                    # 60秒冷却 + 当天不重复
                    if task_key in self._sent_today or (task_key in self._last_sent and now_ts - self._last_sent[task_key] < 60):
                        self._log(f"任务 {task_time} 已在冷却期或今日已发送，跳过", "debug")
                        continue
                    self._sent_today[task_key] = True
                    self._last_sent[task_key] = now_ts
                    self._log(f"触发定时任务: {task_time}", "info")
                    await self._execute_task(task)

            await asyncio.sleep(1)

    async def _get_network_time(self):
        try:
            import aiohttp
            url = f"https://timeapi.io/api/Time/current/zone?timeZone={self.timezone}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return f"{int(data['hour']):02d}:{int(data['minute']):02d}"
        except Exception as e:
            self._log(f"获取网络时间失败: {e}", "debug")
        return None

    async def _execute_task(self, task: dict):
        umo = task.get("umo", "")
        raw_prompt = task.get("prompt", "你好~")
        if not umo:
            self._log("任务缺少 UMO，已跳过", "error")
            return

        if self.use_llm:
            self._log("正在调用 LLM 生成内容...", "debug")
            final_text = await self._generate_text(raw_prompt)
            if not final_text:
                self._log("LLM生成失败，跳过此任务", "error")
                return
            self._log(f"LLM 生成成功: {final_text[:50]}...", "debug")
        else:
            final_text = raw_prompt

        try:
            wrapper = _MessageWrapper([Plain(final_text)])
            await self.context.send_message(umo, wrapper)
            self._log(f"消息发送成功: {final_text[:50]}...", "info")
        except Exception as e:
            self._log(f"发送消息失败: {e}", "error")

    async def _generate_text(self, prompt: str) -> str:
        try:
            import aiohttp
            if not self.api_key:
                self._log("缺少 api_key", "error")
                return ""

            system_prompt = self.system_prompt if self.system_prompt else "请用中文回复，语气自然亲切。"
            headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
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
                        return data["choices"][0]["message"]["content"].strip()
                    else:
                        self._log(f"API请求失败: {resp.status}", "error")
                        return ""
        except Exception as e:
            self._log(f"LLM生成失败: {e}", "error")
            return ""

    async def terminate(self):
        self._log("插件已卸载", "info")
