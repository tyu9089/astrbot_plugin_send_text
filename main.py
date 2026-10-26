import logging
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from astrbot.api.message_components import Plain

logger = logging.getLogger("astrbot")

class SendTextPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # 监视目标保存在内存，重启即清空
        self.watched_umo = ""
        self.admin_umo = ""

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("发送文本")
    async def send_text(self, event: AstrMessageEvent, content: str = ""):
        """基础功能：管理员被动原样发送文本"""
        text_to_send = content.strip()
        if not text_to_send:
            yield event.plain_result("请在 /发送文本 后输入要发送的内容。")
            return

        logger.info(f"[发送文本] 管理员触发，目标: {event.unified_msg_origin}, 内容: {text_to_send}")
        yield event.plain_result(text_to_send)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("监视群聊消息")
    async def watch_group(self, event: AstrMessageEvent, umo: str = ""):
        """监视控制：开启或关闭双向同步"""
        target_umo = umo.strip()
        if not target_umo:
            yield event.plain_result("指令格式错误，正确格式：/监视群聊消息 UMO")
            return

        if self.watched_umo == target_umo:
            # 结束监视
            self.watched_umo = ""
            self.admin_umo = ""
            logger.info("[监视控制] 已关闭双向消息同步")
            yield event.plain_result(f"已结束监视，停止双向转发。\n目标: {target_umo}")
        else:
            # 开启监视（覆盖旧的）
            self.watched_umo = target_umo
            self.admin_umo = event.unified_msg_origin
            logger.info(f"[监视控制] 开启双向同步: 目标={target_umo}, 管理员私聊={self.admin_umo}")
            yield event.plain_result(f"已开启监视，双向同步已启动。\n目标: {target_umo}\n（再次发送相同指令可关闭）")

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_all_messages(self, event: AstrMessageEvent):
        """全局消息监听：处理双向纯文本转发"""
        # 如果未开启监视，直接返回
        if not self.watched_umo or not self.admin_umo:
            return

        # 防死循环：如果是机器人自己发出的消息，直接忽略
        if event.get_sender_id() == event.get_self_id():
            return

        # 提取消息内容，如果为空则忽略
        text = event.message_str
        if not text:
            return

        # 如果是斜杠开头的指令，忽略（防止把指令转发过去）
        if text.startswith("/"):
            return

        # 严格过滤纯文本：只允许消息链中包含 Plain 组件，跳过图片、语音等多媒体
        for comp in event.message_obj.message:
            if not isinstance(comp, Plain):
                return

        # 场景 1：被监视的群聊发消息 -> 转发给管理员私聊
        if event.unified_msg_origin == self.watched_umo:
            logger.info(f"[监视转发] 捕获目标会话消息，推送到管理员: {text}")
            forward_msg = [Plain(text=f"【来自目标会话】\n{text}")]
            await self.context.send_message(self.admin_umo, forward_msg)

        # 场景 2：管理员私聊发消息 -> 转发给被监视的群聊
        elif event.unified_msg_origin == self.admin_umo:
            logger.info(f"[监视转发] 捕获管理员指令，同步到目标会话: {text}")
            forward_msg = [Plain(text=text)]
            await self.context.send_message(self.watched_umo, forward_msg)