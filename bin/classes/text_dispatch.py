from bin.handlers.message_handlers import *
from bin.handlers.logger import logger

@requires_verification
async def states_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    USER_STATES_ROUTER = {
        'user verification complete': questions_handler,
        'faq loaded': questions_handler,
        'ticket canceled': questions_handler,
        'ticket created': edit_ticket_text_handler,
        'texting': texting_handler,

        'admin verification complete': None,
        'announce': announce_handler,
    }

    context.user_data.setdefault('user_messages', []).append(update.message)

    state = context.user_data.get('menu_position')
    logger.info(f'[{update.effective_chat.id}] current user state: <{state}>')
    logger.info(f'[{update.effective_chat.id}] user messages: <{context.user_data["user_messages"]}>')
    try:
        await USER_STATES_ROUTER[state](update, context)
    except KeyError:
        if context.user_data['role'] == 'user':
            logger.warning(f'[{update.effective_chat.id}] user has an unsupported state: <{state}>')
            context.user_data['menu_position'] = "user verification complete"
            await update.message.reply_text(text='😬Ой, у нас щось зламалося!\nПовертаю усе як було...')
            await update.message.reply_text(text='✔️Верифікацію пройдено\n❓Опишіть вашу проблему (Не друкує принтер, треба змінити пароль в 1С, і т.д)')
            pass
        else:
            context.user_data['menu_position'] = None
            pass