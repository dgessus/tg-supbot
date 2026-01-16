from telegram import Update
from telegram.ext import ContextTypes
from bin.classes.message_constructor import MessageConstructor
from bin.handlers.logger import logger
from collections.abc import Sequence

async def forward_message(update: Update, context: ContextTypes.DEFAULT_TYPE, recipient: int = None) -> None:
    msg = context.user_data['user_messages'][-1]
    recipient_id = recipient or context.user_data.get("chat_partner")
    bot = context.bot

    if not (msg and recipient_id):
        raise ValueError("No message or recipient id")

    content_types = [
        "text", "photo", "sticker", "animation", "video",
        "voice", "document", "audio", "video_note", "location", "contact"
    ]

    content_type = next((t for t in content_types if getattr(msg, t, None)), None)
    if not content_type:
        raise ValueError("Unsupported message type")

    value = getattr(msg, content_type)

    if content_type == "text":
        send_method_name = "send_message"
    else:
        send_method_name = f"send_{content_type}"

    logger.info(f'[{update.effective_chat.id}] send_method_name: <{send_method_name}>')
    send_method = getattr(bot, send_method_name, None)

    if not send_method:
        raise ValueError("Unsupported message type")

    kwargs = {"chat_id": recipient_id}

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        logger.info(f"[{update.effective_chat.id}] unpacked value from getarrr(message): <{value}>")
        kwargs[content_type] = value[-1].file_id
    elif hasattr(value, "file_id"):
        kwargs[content_type] = value.file_id
    elif content_type == "text":
        kwargs["text"] = MessageConstructor.sanitize_md(value)
        kwargs["parse_mode"] = "MarkdownV2"
    else:
        logger.warning(f'[{update.effective_chat.id}] cannot unpack value from getarrr(message): <{value}>; using it as is')
        kwargs[content_type] = value

    if getattr(msg, "caption", None):
        kwargs["caption"] = MessageConstructor.sanitize_md(msg.caption)
        kwargs["parse_mode"] = "MarkdownV2"

    logger.info(f'[{update.effective_chat.id}] kwargs from message_forwarding_handler: <{kwargs}>')
    return await send_method(**kwargs)

