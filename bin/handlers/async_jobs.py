from typing import Literal

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from bin.classes.message_constructor import MessageConstructor
from bin.classes.ticket_manager import Ticket, TicketManager
from utils.logger import logger
from utils.config_loader import Load_config
import asyncio

config = Load_config()

async def notify_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, notification_type: Literal['new_ticket', 'ticket_overdue'], ticket_id: int = None) -> None:
    logger.info(f'notifying admins about ticket', update.effective_chat.id)
    def format_notification_text(ticket: Ticket, notification_type):
        if notification_type == 'new_ticket':
            message_text = (f"🎫Новий тікет від ТТ {ticket.shop_name}\n"
                    f"💬Коротке повідомлення: {ticket.message_text.split('\n')[0]}\n"
                    f"🕔Час звернення: {ticket.created_at}")
            return message_text

        elif notification_type == 'ticket_overdue':
            message_text = (f"🎫Тікет від ТТ {ticket.shop_name} номер #{ticket.ticket_id} просрочено\n"
                            f"🤌Зверніть на нього увагу")
            return message_text
        else: return None

    chat_id = config.notification_chat_id

    if ticket_id:
        ticket_obj = await TicketManager().find_user_ticket(ticket_id)
    else:
        ticket_obj = await TicketManager().find_user_ticket(context.user_data['active_ticket_id'][-1])

    markup = InlineKeyboardMarkup([[InlineKeyboardButton(text="🤖Перейти у бот", url=f"https://t.me/{config.bot_username}")]])

    try:
        await context.bot.send_message(chat_id=chat_id, text=format_notification_text(ticket_obj, notification_type), reply_markup=markup)
    except Exception as e:
        logger.warning(f"failed to send ticket notification: {e}")


async def clear_user_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await asyncio.sleep(300)
    context.user_data['user_messages'].clear()
    logger.info(f"auto-cleared messages from context.user_data for user {update.effective_user.id}")
    return None


async def ticket_overdue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await asyncio.sleep(900)
    context.user_data['menu_position'] = 'ticket is overdue'
    await MessageConstructor(update, context).send.new_message()
