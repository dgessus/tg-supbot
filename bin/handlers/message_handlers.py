from telegram import (Update,
                      ReplyKeyboardMarkup,
                      KeyboardButton,
                      ReplyKeyboardMarkup,
                      ReplyKeyboardRemove,
                      Update)
from telegram.ext import ContextTypes
from functools import wraps
import datetime

from bin.classes.auth import Auth
from bin.classes.pattern_search import Instruction
from bin.classes.message_constructor import MessageConstructor
from bin.classes.ticket_manager import TicketManager
from bin.handlers.message_forwarding_handler import forward_message
from bin.handlers.async_jobs import *
from bin.handlers.logger import logger

ticket_mgr = TicketManager()


def requires_verification(handler_func):
    @wraps(handler_func)
    async def wrapper(update, context, *args, **kwargs):
        if not context.user_data.get("verified") and not context.user_data.get("chat_partner"):
            logger.info(f'[{update.effective_chat.id}] authorising user')
            context.user_data['menu_position'] = 'verification'
            await start_handler(update, context)
            return None
        else:
            return await handler_func(update, context, *args, **kwargs)

    return wrapper


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    reply_keyboard = [[KeyboardButton('Верифікувати', request_contact=True)]]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True,
                                 input_field_placeholder='Натисніть кнопку нижче', resize_keyboard=True)
    await update.message.reply_text("🔐Для початку, пройдіть верифікацію номеру", reply_markup=markup)


async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    contact = update.message.contact.phone_number.strip('+')
    user_id = update.message.from_user.id
    auth = Auth(user_id, contact)

    return_data = auth.check()
    if return_data:
        context.user_data['contact'] = contact
        context.user_data['shop_name'] = return_data['shop_name']
        context.user_data['user_id'] = user_id
        context.user_data['role'] = return_data['role']
        context.user_data['menu_position'] = f"{return_data['role']} verification complete"
        context.user_data['verified'] = True
        context.user_data['lang'] = update.message.from_user.language_code
        context.user_data['user_messages'] = []
        context.user_data['bot_message_ids'] = []
        context.user_data['ticket_chat_messages'] = []
        context.user_data['active_ticket_id'] = []

        if context.user_data['role'] == 'admin':
            context.bot_data.setdefault('admins', [])
            context.user_data['ticket_list'] = []
            context.bot_data['admins'].append(user_id) if not user_id in context.bot_data['admins'] else context.bot_data['admins']
            await admin_panel_handler(update, context)
        elif context.user_data['role'] == 'user':
            context.bot_data.setdefault('users', []).append(user_id)
            await update.message.reply_text('✔️Верифікацію пройдено\n❓Опишіть вашу проблему (Не друкує принтер, треба змінити пароль в 1С, і т.д)')
    else:
        await update.message.reply_text('❌Вибачте, Вам відмовлено у доступі')


async def questions_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    task = context.user_data.setdefault('cleanup_task', None)
    if task:
        task.cancel()
    context.user_data['cleanup_task'] = context.application.create_task(clear_user_data(update, context), update)

    message_text = None

    logger.info(f'[{update.effective_chat.id}] questions handler has been triggered by user; message contents: <{update.message.text}>')
    if update.message.text or update.message.caption:
        message_text = Instruction().load(user_input=update.message.text or update.message.caption,
                                          lang=context.user_data['lang'])
    logger.info(f'[{update.effective_chat.id}] loaded instruction for user')
    context.user_data['menu_position'] = 'faq loaded'

    if message_text:
        await MessageConstructor(update=update, context=context, message_text=message_text, sanitize=True, parse_mode="MarkdownV2").send.refresh_message()


async def edit_ticket_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(f"[{update.effective_chat.id}] edit ticket text has been triggered by user; message contents: <{update.message.text}>")
    message_text = "🚯У вас вже є активна заявка. Бажаєте оновити її чи скасувати?"

    context.user_data['menu_position'] = 'ticket needs update'

    await MessageConstructor(update=update, context=context, message_text=message_text).send.refresh_message()


async def admin_panel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data['menu_position'] = 'main menu'
    open_tickets = len(await ticket_mgr.query_open())
    await MessageConstructor(update=update, context=context, message_text=open_tickets, remove_user_messages=True).send.refresh_message()


def format_message_for_storage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    username = context.user_data['shop_name'],
    message = update.message.text or update.message.caption
    return (f"{username}:\n"
            f"{message}\n"
            f"at {datetime.datetime.now().isoformat()}\n")

async def texting_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(f'[{update.effective_chat.id}] texting handler has been called by user; context.user_data contents: <{context.user_data}>')
    forward_to = context.user_data.get('chat_partner', None)
    message_obj = None
    topic_ticket_id = context.user_data['active_ticket_id'][-1]
    user_role = context.user_data['role']

    if forward_to:
        try:
            logger.info(f'[{update.effective_chat.id}] message_forward_handler has been called by user; recipient_id: <{forward_to}>')
            message_obj = await forward_message(update, context)
        except ValueError:
            try:
                message_obj = await context.bot.send_message(chat_id=forward_to,
                                                             text='✖️Повідомлення, відправлене іншою стороною, не підтримується!')
            except Exception as e:
                await update.effective_chat.send_message(f'🚨Помилка чату: <{e}>\nбула спричинена вашим співбесідником☠️')
                context.user_data['menu_position'] = f"{user_role} verification complete"
                return
    else:
        await update.effective_chat.send_message("🚷Користувача не знайдено\nКористувач видалив чат або щось пішло не так")
        raise ValueError("No recipient id specified")

    context.user_data['bot_message_ids'].append(message_obj.message_id)
    message = format_message_for_storage(update, context)
    context.bot_data[topic_ticket_id].append(message)


async def announce_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(f'[{update.effective_chat.id}] announce handler has been called by user')
    context.user_data['menu_position'] = "confirm announcement"
    users = len(context.bot_data.get('users', []))
    await MessageConstructor(update=update, context=context, message_text=users).send.refresh_message()
