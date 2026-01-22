from telegram import (InputMediaPhoto,
                      InputMediaVideo,
                      InputMediaAnimation,
                      )
from telegram.ext import CallbackContext

from openpyxl import Workbook
from openpyxl.styles import Font
import os

from bin.classes.media import Media
from bin.handlers.async_jobs import *
from bin.handlers.message_handlers import admin_panel_handler
from bin.handlers.message_handlers import forward_message
from utils.config_loader import Load_config

config = Load_config()
ticket_manager = TicketManager()


def get_username(update: Update, context: CallbackContext):
    username = (context.user_data['shop_name'] or
                update.effective_user.username or
                update.effective_user.first_name or
                update.effective_user.last_name or
                f"Відсутнє ім'я користувача: ID={update.effective_chat.id}")
    return username


async def dummy(update: Update, context: CallbackContext):
    await update.callback_query.answer()


def get_user_messages(update:Update, context: CallbackContext):
    user_messages = context.user_data["user_messages"]
    messages_list = []

    for message in user_messages:
        if message.text or message.caption:
            messages_list.append(message.text or message.caption)
        else: pass

    return messages_list


def get_user_media(update:Update, context: CallbackContext):
    logger.info(f"contents of context.user_data['user_messages']: {context.user_data["user_messages"]}", extra={"user_id" : update.effective_chat.id})

    user_media = []
    for message in context.user_data["user_messages"]:

        if message.photo:
            logger.info(f"handler found a photo in context_user_data", extra={"user_id" : update.effective_chat.id})
            user_media.append(InputMediaPhoto(media=message.photo[-1].file_id))
        if message.video:
            logger.info(f"handler found video in context_user_data", extra={"user_id" : update.effective_chat.id})
            user_media.append(InputMediaVideo(media=message.video.file_id))
        if message.animation:
            logger.info(f"handler found a GIF in context_user_data", extra={"user_id" : update.effective_chat.id})
            user_media.append(InputMediaAnimation(media=message.animation.file_id))

    return user_media


async def usr_create_ticket(update: Update, context: CallbackContext):
    messages_list = get_user_messages(update, context)
    message_text = "\n".join(messages_list)
    username = get_username(update, context)

    ticket = Ticket(user_id=update.effective_chat.id, username=username,
                    shop_name=context.user_data["shop_name"], message_text=message_text)
    new_ticket_id = await ticket_manager.create_ticket(ticket)
    ticket_media = get_user_media(update, context)

    context.user_data["active_ticket_id"].append(int(new_ticket_id))
    context.user_data["menu_position"] = "ticket created"

    logger.info(f"amount of elements in ticket_media: {len(ticket_media)}", extra={"user_id" : update.effective_chat.id})

    logger.info(f"variable new_ticket_id before insertion into context_userdata: {new_ticket_id}", extra={"user_id" : update.effective_chat.id})

    logger.info(f"active ticket id: {context.user_data["active_ticket_id"]}", extra={"user_id" : update.effective_chat.id})

    if ticket_media:
        logger.info(f"ticket has mediafiles attached to it: {ticket_media}", extra={"user_id" : update.effective_chat.id})
        message= await context.bot.send_media_group(chat_id=config.media_chat_id, media=ticket_media[-10:],
                                                    caption=f"ticket_media_{new_ticket_id}")
        logger.info(f"sent ticket media to the media group: {message}", extra={"user_id" : update.effective_chat.id})
        serialized_files_string = Media(update, context).serialize()

        try:
          await ticket_manager.update_ticket(ticket_id=new_ticket_id, update_columns_values={"media_file_ids": serialized_files_string})
        except Exception as e:
            logger.error(f"failed to update ticket: {e}", extra={"user_id" : update.effective_chat.id})

    context.user_data["ticket_timer_task"] = context.application.create_task(ticket_overdue(update, context))

    await notify_admin(update, context, notification_type="new_ticket")
    await update.callback_query.answer()
    await MessageConstructor(update=update, context=context, remove_user_messages=True).send.refresh_message()


async def usr_cancel_ticket(update: Update, context: CallbackContext):
    task = context.user_data.setdefault("ticket_timer_task", None)
    ticket_id = update.callback_query.data.split('_')[-1]
    logger.info(f"user has canceled the ticket {ticket_id}", extra={"user_id" : update.effective_chat.id})

    try:
        await ticket_manager.close_ticket(ticket_id=ticket_id, closedby_user_id=update.effective_chat.id)
    except Exception as error:
        if "not found" in str(error):
            await update.callback_query.answer("‼️Тікет не знайдено в базі", show_alert=True)

        elif "already closed" in str(error):
            await update.callback_query.answer("‼️Тікет вже закрито", show_alert=True)

    if task:
        task.cancel()

    context.user_data["menu_position"] = "ticket canceled"
    await MessageConstructor(update=update, context=context, remove_user_messages=True).send.edit_message()

    context.user_data["active_ticket_id"] = []

    return None


async def usr_edit_ticket(update: Update, context: CallbackContext):
    context_user_messages_list = get_user_messages(update, context)
    ticket_id = int(update.callback_query.data.split('_')[-1])
    updated_ticket_text = "\n".join(context_user_messages_list)

    logger.info(f"inserting new message_text into ticket: {context_user_messages_list}", extra={"user_id" : update.effective_chat.id})

    await ticket_manager.update_ticket(ticket_id=ticket_id, update_columns_values={"message_text": updated_ticket_text})

    logger.info("inserted new message_text into ticket", extra={"user_id" : update.effective_chat.id})

    context.user_data["user_messages"].clear()
    context.user_data["menu_position"] = "ticket created"

    await MessageConstructor(update=update, context=context, message_text="Ваш тікет оновлено успішно!",
                             remove_user_messages=True).send.edit_message()
    await update.callback_query.answer()


async def usr_append_ticket(update: Update, context: CallbackContext):
    ticket_id = int(update.callback_query.data.split('_')[-1])
    context_user_messages_list = get_user_messages(update, context)
    ticket = await ticket_manager.find_user_ticket(ticket_id=ticket_id)
    appended_ticket_text = ticket.message_text+'\n'+'\n'.join(context_user_messages_list)

    logger.info(f"appending new message_text into ticket: {context_user_messages_list}", extra={"user_id" : update.effective_chat.id})

    await ticket_manager.update_ticket(ticket_id=ticket_id, update_columns_values={"message_text": appended_ticket_text})
    context.user_data["menu_position"] = "ticket created"

    await MessageConstructor(update=update, context=context, message_text="Ваш тікет оновлено успішно!",
                             remove_user_messages=True).send.edit_message()
    await update.callback_query.answer()


async def usr_push_ticket(update: Update, context: CallbackContext):
    ticket_id = int(update.callback_query.data.split('_')[-1])

    logger.info(f"user pushed pushed ticket #{ticket_id}", extra={"user_id" : update.effective_chat.id})
    await ticket_manager.update_ticket(ticket_id=ticket_id, update_columns_values={"status": 3})
    await notify_admin(update=update, context=context, notification_type="ticket_overdue", ticket_id=ticket_id)


async def format_ticket_text(ticket: Ticket):
    status = {0: "✅Закрито",
              1: "🟡Очікує виконання",
              2: "🟢Виконується",
              3: "🔴Протерміновано❗️",
              4: "❎Скасовано користувачем"}

    message = (f"🎫Тікет #{ticket.ticket_id} від користувача 🗣{ticket.shop_name}\n\n"
               f"💬{ticket.message_text}\n\n"
               f"🗓Дата створення заявки: {ticket.created_at}\n\n"
               f"🏚Для відділу: {ticket.designated_dept}\n\n"
               f"🫠Виконавець: {ticket.assigned_to}\n\n"
               f"📊Статус: {status[ticket.status]}\n")

    return message


async def ticket_loader(update: Update, context: CallbackContext, ticket: Ticket = None, load_one: bool = False):
    if load_one:
        context.user_data["menu_position"] = "one ticket"
    else:
        context.user_data["menu_position"] = "tickets menu"
    media = None

    if not ticket:
        logger.info(f"no tickets were supplied. reading the first in the list", extra={"user_id" : update.effective_chat.id})
        ticket_ids = await ticket_manager.query_open()
        context.user_data["ticket_list"] = ticket_ids
        try:
            ticket = await ticket_manager.find_user_ticket(ticket_ids[0])
        except IndexError:
            await update.callback_query.answer(text="🚬Наразі нема активних заявок", show_alert=True)
            await admin_panel_handler(update=update, context=context)
            return

    ticket_ids = context.user_data["ticket_list"]
    message = await format_ticket_text(ticket)

    media_serialized_string = ticket.media_file_ids
    if media_serialized_string:
        media = Media(update, context).deserialize(serialized_string=media_serialized_string, caption=message)
        logger.info(f"media list: {media}", extra={"user_id" : update.effective_chat.id})

    ticket_list = [ticket_id if ticket_id != ticket.ticket_id else f"^{ticket_id}" for ticket_id in ticket_ids]
    context.user_data["active_ticket_id"] = [ticket.ticket_id]
    logger.info(f"active ticket id: {context.user_data["active_ticket_id"]}", extra={"user_id" : update.effective_chat.id})
    context.user_data["ticket_list"] = ticket_list
    logger.info(f"current open tickets list: {ticket_list}", extra={"user_id" : update.effective_chat.id})
    await MessageConstructor(update=update, context=context, message_text=message, media=media if media else None, sanitize=False, remove_user_messages=True).send.refresh_message()
    await update.callback_query.answer()


async def ticket_lookup(update: Update, context: CallbackContext):
    direction = update.callback_query.data.split('_')[-1]
    logger.info(f"fetching next ticket; direction: {direction}", extra={"user_id" : update.effective_chat.id})

    ticket_list = context.user_data["ticket_list"]
    next_ticket = None

    for i, ticket_id in enumerate(ticket_list):
        logger.info(f"start id = {ticket_id}",  extra={"user_id" : update.effective_chat.id})

        if isinstance(ticket_id, str) and ticket_id.startswith("^"):
            logger.info(f"current shown ticket id is {ticket_id}",  extra={"user_id" : update.effective_chat.id})

            ticket_list[i] = int(ticket_id[1:])

            if direction == "forward":
                next_ticket = ticket_list[(i + 1) % len(ticket_list)]
            elif direction == "backward":
                next_ticket = ticket_list[(i - 1) % len(ticket_list)]

            context.user_data["ticket_list"] = ticket_list
            break

    if next_ticket is not None:
        logger.info(f"loaded next ticket for user",  extra={"user_id" : update.effective_chat.id})
        ticket = await ticket_manager.find_user_ticket(next_ticket)
        await update.callback_query.answer()
        await ticket_loader(update, context, ticket)
    else:
        logger.info(f"reached end of tickets list. loading first ticket",  extra={"user_id" : update.effective_chat.id})
        await update.callback_query.answer()
        await ticket_loader(update, context, None)


async def admin_close_ticket(update: Update, context: CallbackContext):
    ticket_timer_task = context.user_data.setdefault("ticket_timer_task", None)
    logger.info("admin is closing ticket",  extra={"user_id" : update.effective_chat.id})
    ticket_list = context.user_data["ticket_list"]
    current_ticket = None
    for i, ticket_id in enumerate(ticket_list):
        if isinstance(ticket_id, str) and ticket_id.startswith("^"):
            current_ticket = ticket_list[i].strip("^")
    logger.info(f"closing ticket #{current_ticket}",  extra={"user_id" : update.effective_chat.id})
    try:
        await ticket_manager.close_ticket(ticket_id=current_ticket, closedby_user_id=update.effective_chat.id)
    except Exception as error:
        if "not found" in str(error):
            await update.callback_query.answer("‼️Тікет не знайдено в базі", show_alert=True)
        elif "already closed" in str(error):
            await update.callback_query.answer("‼️Тікет вже закрито", show_alert=True)
        else:
            logger.error(f"failed to close ticket; API error: <{error}>",  extra={"user_id" : update.effective_chat.id})
            await update.callback_query.answer("‼️Непередбачувана помилка. Зверніться до максіма\n{error}", show_alert=True)
    await update.callback_query.answer()

    ticket = await ticket_manager.find_user_ticket(ticket_id=current_ticket)
    try:
        logger.info(f"current context_userdata['active_ticket_id'] contents: {context.user_data["ticket_list"]}",
                    extra={"user_id" : update.effective_chat.id})
        logger.info(f"removing ticket {current_ticket} from the context_user_data",  extra={"user_id" : update.effective_chat.id})
        context.user_data["ticket_list"].remove(f"^{current_ticket}")
        try:
            context.application.user_data[ticket.user_id]["active_ticket_id"].pop()
        except Exception as error:
            logger.error(f"failed to remove ticket #{current_ticket} from the context_user_data",  extra={"user_id" : update.effective_chat.id})
        context.application.user_data[ticket.user_id]["menu_position"] = "faq loaded"

    except IndexError:
        pass

    if ticket_timer_task:
        ticket_timer_task.cancel()

    await context.bot.send_message(chat_id=ticket.user_id, text=f"Ваш 🫵 тікет 👉№{ticket.ticket_id} було закрито❌")
    await ticket_loader(update, context, None)


async def back(update: Update, context: CallbackContext):
    message_constructor = MessageConstructor(update=update, context=context)
    menu_positions = message_constructor.load_data.position_data()
    logger.info(f"BACKBTN menu position: {context.user_data["menu_position"]}; previous level: {menu_positions["previous_level"]}",
                extra={"user_id" : update.effective_chat.id})

    context.user_data["menu_position"] = menu_positions["previous_level"]
    context.user_data["ticket_list"].clear()

    if context.user_data["menu_position"] == "main menu":
        await admin_panel_handler(update, context)
    elif context.user_data["menu_position"] == "tickets menu":
        await ticket_loader(update, context)
    else:
      await MessageConstructor(update=update, context=context, remove_user_messages=True).send.refresh_message()


async def accept(update: Update, context: CallbackContext):
    ticket_list = context.user_data["ticket_list"]
    current_ticket = None
    username = get_username(update, context)

    for i, ticket_id in enumerate(ticket_list):
        if isinstance(ticket_id, str) and ticket_id.startswith("^"):
            current_ticket = ticket_list[i].strip("^")

    if current_ticket:
        ticket = await ticket_manager.find_user_ticket(ticket_id=current_ticket)

        if ticket.status == 1 or ticket.status == 3:
            update_columns_values = {"status": 2, "assigned_to": username}
        elif ticket.status == 2:
            if ticket.assigned_to == username:
                update_columns_values = {"status": 1, "assigned_to": username}
            else:
                update_columns_values = None
                await update.callback_query.answer("‼️Це не ваш тікет!")
        else:
            update_columns_values = None
            await update.callback_query.answer("‼️Тікет вже закрили!", show_alert=True)
            await back(update, context)
            return

        if update_columns_values:
            await ticket_manager.update_ticket(ticket_id=current_ticket, update_columns_values=update_columns_values)
        await update.callback_query.answer("Тікет взято в роботу")
        await ticket_loader(update, context, None)
    else:
        await ticket_loader(update, context, None)


async def message_user(update: Update, context: CallbackContext):
    subject_ticket_id = context.user_data["active_ticket_id"][-1]
    ticket = await ticket_manager.find_user_ticket(ticket_id=subject_ticket_id)
    username = get_username(update, context)

    if ticket.status == 1 or 3:
        await ticket_manager.update_ticket(ticket_id=subject_ticket_id,
                                           update_columns_values={"status": 2, "assigned_to": username})
    elif ticket.status == 2:
        if ticket.assigned_to != username:
            await update.callback_query.answer("‼️Це не ваш тікет")
            return
        else:
            logger.info(f"starting a chat with user {username}", extra={"user_id" : update.effective_chat.id})

    context.user_data["menu_position"] = "texting"
    context.bot_data.setdefault(subject_ticket_id, [])

    context.user_data["chat_partner"] = ticket.user_id
    context.application.user_data[ticket.user_id]["verified"] = True
    context.application.user_data[ticket.user_id]["menu_position"] = "texting"
    context.application.user_data[ticket.user_id]["active_ticket_id"].append(subject_ticket_id)
    context.application.user_data[ticket.user_id]["chat_partner"] = update.effective_chat.id

    await MessageConstructor(update=update, context=context).send.edit_message()

    try:
        await context.bot.send_message(chat_id=ticket.user_id,
                                       text=f"💬Чат з техніком стосовно тікета #{ticket.ticket_id} розпочато.\nПриємного спілкування!")
    except Exception as error:
        logger.error(f"failed to send a message to the user inside the in-bot chat; API error: <{error}>", extra={"user_id" : update.effective_chat.id})
        context.user_data["menu_position"] = "tickets menu"
        await update.callback_query.answer(f"‼️Помилка під час створення чату: {error}", show_alert=True)
        await MessageConstructor(update=update, context=context).send.edit_message()


async def stop_texting(update: Update, context: CallbackContext):
    chat_partner = context.user_data["chat_partner"]
    context.user_data["menu_position"] = "tickets menu"
    context.user_data["chat_partner"] = None
    subject_ticket_id = context.user_data["active_ticket_id"][-1]

    context.application.user_data[chat_partner]["menu_position"] = "faq loaded"
    context.application.user_data[chat_partner]["chat_partner"] = None
    context.application.user_data[chat_partner]["active_ticket_id"].pop()

    ticket = await ticket_manager.find_user_ticket(ticket_id=subject_ticket_id)
    combined_texting_messages = '$'.join(
        filter(None, [ticket.texting_messages, *context.bot_data[subject_ticket_id]])
    )

    await ticket_manager.update_ticket(ticket_id=subject_ticket_id, update_columns_values={"texting_messages": combined_texting_messages})
    await context.bot.send_message(chat_id=chat_partner, text="💬Чат завершено")
    await back(update, context)


async def announce(update: Update, context: CallbackContext):
    context.user_data["user_messages"].clear()
    context.user_data["menu_position"] = "announce"
    await MessageConstructor(update=update, context=context).send.edit_message()


async def send_announcement(update: Update, context: CallbackContext):
    registered_users = context.bot_data.get('users')
    message = "⚡️Оголошення від айті-відділу:"
    if registered_users:
        for user_id in registered_users:
            await context.bot.send_message(chat_id=user_id, text=message)
            await forward_message(update, context, user_id)
    else:
        await update.callback_query.answer('‼️Немає зареєстрованих користувачів', show_alert=True)
    await back(update, context)


async def refresh_ticket_panel(update: Update, context: CallbackContext):
    current_ticket = None
    await update.callback_query.answer()
    for ticket_id in context.user_data.get("ticket_list", []):
        if isinstance(ticket_id, str) and ticket_id.startswith("^"):
            logger.info(f"current shown ticket id is {ticket_id}", extra={"user_id" : update.effective_chat.id})
            current_ticket = int(ticket_id.lstrip("^"))

    if current_ticket:
        current_ticket = await ticket_manager.find_user_ticket(ticket_id=current_ticket)

    await ticket_loader(update=update, context=context, ticket=current_ticket if current_ticket else None)


async def manual_ticket_selection_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(f"handler was called")
    if context.user_data["role"] == "admin":
        ticket_id = int(update.message.text.lstrip('/'))
        try:
            ticket = await ticket_manager.find_user_ticket(ticket_id)

        except Exception as error:
            context.user_data["menu_position"] = "ticket not loaded"
            await MessageConstructor(update=update, context=context, message_text=error).send.new_message()
            return

        await ticket_loader(update=update, context=context, ticket=ticket, load_one=True)
    else:
        pass


async def closed_tickets_list(update: Update, context: CallbackContext):
    logger.info("handler was called", extra={"user_id" : update.effective_chat.id})

    position = update.callback_query.data.split("_")[-1]
    if position == "menu":
        context.user_data["menu_position"] = "closed tickets choose range"
        await MessageConstructor(update=update, context=context).send.edit_message()
        await update.callback_query.answer()

    elif position in ['day', 'week', 'month']:
        context.user_data["menu_position"] = "bulk ticket load"
        closed_tickets = await ticket_manager.query_closed(position)
        ticket_list = [f"{ticket}" for ticket in closed_tickets]
        message = '\n'.join([f"/{ticket}" for ticket in ticket_list])
        logger.info(f'closed tickets list: {message}', extra={"user_id" : update.effective_chat.id})
        context.user_data["ticket_list"] = ticket_list

        if message:
            await MessageConstructor(update=update, context=context, message_text=message).send.refresh_message()
        else:
            await update.callback_query.answer("‼️Немає тікетів за вказаний період!")


async def export_ticket_data(update: Update, context: CallbackContext):
    logger.info("exporting ticket bot-data", extra={"user_id" : update.effective_chat.id})
    ticket_obj_list = []

    for ticket_id in context.user_data.get("ticket_list", []):
        ticket = await ticket_manager.find_user_ticket(ticket_id)
        ticket_obj_list.append(ticket)

    wb = Workbook()
    ws = wb.active
    ws.title = "Ticket Data"

    logger.info(f"generating .xlsx file for user", extra={"user_id" : update.effective_chat.id})
    if ticket_obj_list:
        headers_written = False

        for i, ticket_obj in enumerate(ticket_obj_list):
            ticket_data = []
            headers = []

            for attribute, value in ticket_obj.__dict__.items():
                headers.append(attribute)
                ticket_data.append(value)

            if not headers_written:
                ws.append(headers)
                headers_written = True

            ws.append(ticket_data)
    else:
        await update.callback_query.answer(
            "Неможливо вивантажити порожній список тікетів!",
            show_alert=True
        )

    for cell in ws[1]:
        cell.font = Font(bold=True)


    date_range = f"{ticket_obj_list[0].created_at.replace(':', '-')}" + '+' + f"{ticket_obj_list[-1].created_at.replace(':', '-')}"
    file_path = f"{date_range}_ticket_data.xlsx"

    logger.info(f"saving .xlsx file for user", extra={"user_id" : update.effective_chat.id})
    try:
        wb.save(file_path)
    except Exception as error:
        logger.error(f"an error occurred while saving the .xlsx file for user; error: <{error}>", extra={"user_id" : update.effective_chat.id})
        await update.callback_query.answer(f"‼️Помилка вивантаження файлу: <{error}>", show_alert=True)
        await back(update, context)
        return

    try:
        await context.bot.send_document(chat_id=update.effective_chat.id, document=open(file_path, 'rb'))
    except Exception as error:
        logger.error(f"failed to send .xlsx file for user; error: <{error}>", extra={"user_id" : update.effective_chat.id})
        await update.callback_query.answer("‼️Помилка надсилання файлу: <{error}>", show_alert=True)

    try:
        os.remove(file_path)
    except Exception as error:
        logger.warning(f"failed to remove the temp file that was generated for user; error: <{error}>", extra={"user_id" : update.effective_chat.id})
        await update.callback_query.answer(f"‼️Помилка видалення файлу з серверу: <{error}> \nВидаліть його вручну", show_alert=True)


async def chat_history(update: Update, context: CallbackContext):
    context.user_data['menu_position'] = 'ticket chat history'
    ticket_id = context.user_data["active_ticket_id"][-1]
    ticket = await ticket_manager.find_user_ticket(ticket_id)
    message_text = ticket.texting_messages.replace('$', '-----------\n') if ticket.texting_messages else None

    if message_text:
        await MessageConstructor(update=update, context=context, message_text=message_text).send.refresh_message()
    else:
        await update.callback_query.answer('❕Щодо цього тікету ще не було переписки')


async def show_stats(update: Update, context: CallbackContext):
    context.user_data['menu_position'] = 'show stats'
    curr_users = len(context.bot_data.setdefault("users", []))
    message_text = curr_users
    await MessageConstructor(update=update, context=context, message_text=message_text).send.edit_message()
