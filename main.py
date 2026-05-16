import asyncio
import time
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.message_components import Plain
from astrbot.api.provider import ProviderRequest

# 解决 send_message 兼容性问题：构建一个具有 .chain 属性的简单包装器
class _MessageWrapper:
    def __init__(self, chain):
        self.chain = chain

@register("satrfate_timer", "Satrfate", "极简定时问候插件", "1.1.1")
class TimerPlugin(Star):
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.config = config or {}
        self.tasks = self.config.get("tasks", [])
        self.use_network_time = self.config.get("use_network_time", True)
        self.use_llm = self.config.get("use_llm", False)
        self._sent_today = {}

        logger.info(f"[Timer] 插件已加载，读取到 {len(self.tasks)} 个定时任务")
        logger.info(f"[Timer] LLM模式: {'开启' if self.use_llm else '关闭'}")
        for i, task in enumerate(self.tasks):
            logger.info(f"[Timer] 任务{i+1}: time={task.get('time')}, umo={task.get('umo')}, prompt={task.get('prompt', '')[:30]}...")

        asyncio.create_task(self._loop())

    async def _loop(self):
        """每隔30秒校准一次网络北京时间，每秒检查任务"""
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
        """从网络API获取北京时间"""
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
        """执行任务：根据配置使用LLM或固定内容，然后发送消息"""
        umo = task.get("umo", "")
        raw_prompt = task.get("prompt", "你好~")

        if not umo:
            logger.error("[Timer] 任务缺少 UMO，已跳过")
            return

        # 决定最终发送的文本
        if self.use_llm:
            final_text = await self._generate_text(raw_prompt)
            if not final_text:
                logger.error("[Timer] LLM生成失败，跳过此任务")
                return
        else:
            final_text = raw_prompt

        # 发送消息
        try:
            msg_chain = [Plain(final_text)]
            wrapper = _MessageWrapper(msg_chain)
            await self.context.send_message(umo, wrapper)
            logger.info(f"[Timer] 消息发送成功: {final_text[:50]}...")
        except Exception as e:
            logger.error(f"[Timer] 发送消息失败: {e}")

    async def _generate_text(self, prompt: str) -> str:
        """调用 LLM 生成文本，并返回纯文本内容"""
        try:
            provider = self.context.get_llm_provider()
            if not provider:
                logger.error("[Timer] 没有可用的 LLM 提供者")
                return ""

            req = ProviderRequest(
                prompt=prompt,
                system_prompt="",  # 使用全局人格设定
                contexts=[],
            )
            resp = await provider.request(req)
            if resp and resp.chain:
                # 提取纯文本
                texts = []
                for comp in resp.chain:
                    if hasattr(comp, 'text'):
                        texts.append(comp.text)
                    elif isinstance(comp, Plain):
                        texts.append(comp.text)
                return "".join(texts).strip()
            return ""
        except Exception as e:
            logger.error(f"[Timer] LLM生成失败: {e}")
            return ""

    async def terminate(self):
        logger.info("[Timer] 插件已卸载")
