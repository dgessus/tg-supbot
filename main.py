from telegram.ext import (ApplicationBuilder,
                          CommandHandler,
                          MessageHandler,
                          filters,
                          CallbackQueryHandler,
                          Application,
                          PicklePersistence)

from utils.paths import Paths
from utils.config_loader import Load_config
from bin.handlers.message_handlers import *
from bin.classes.text_dispatch import states_router
from bin.handlers.callback_handlers import *


path = Paths()
config = Load_config()
persistence = PicklePersistence(path.data_path/"bot-data.pkl")


class TelegramBot:
    def __init__(self, token: str):
        self.token = token
        self.application = ApplicationBuilder().token(self.token).persistence(persistence).build()
        self._register_handlers()

    def _register_handlers(self):
        #user handlers
        self.application.add_handler(CommandHandler("start", start_handler))

        self.application.add_handler(MessageHandler(filters.CONTACT, contact_handler))
        self.application.add_handler(MessageHandler(filters.Regex(r"^/\d+$"), manual_ticket_selection_handler))
        self.application.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.VIDEO | filters.ANIMATION | filters.Sticker.ALL, states_router))
        self.application.add_handler(CallbackQueryHandler(callback=usr_create_ticket, pattern=r"^usr_create_ticket$"))
        self.application.add_handler(CallbackQueryHandler(callback=usr_cancel_ticket, pattern=r"^usr_cancel_ticket_\d+$"))
        self.application.add_handler(CallbackQueryHandler(callback=usr_edit_ticket, pattern=r"^usr_update_ticket_\d+$"))
        self.application.add_handler(CallbackQueryHandler(callback=usr_append_ticket, pattern=r"^usr_append_ticket_\d+$"))
        self.application.add_handler(CallbackQueryHandler(callback=usr_push_ticket, pattern=r"^usr_push_ticket_\d+$"))

        #admin panel
        self.application.add_handler(CallbackQueryHandler(callback=ticket_loader, pattern=r"^adm_show_tickets$"))
        self.application.add_handler(CallbackQueryHandler(callback=ticket_lookup, pattern=r"^ticket_fetch_(?:forward|backward)$"))
        self.application.add_handler(CallbackQueryHandler(callback=admin_close_ticket, pattern=r"^adm_close_ticket$"))
        self.application.add_handler(CallbackQueryHandler(callback=back, pattern=r"^back$"))
        self.application.add_handler(CallbackQueryHandler(callback=accept, pattern=r"^accept_ticket$"))
        self.application.add_handler(CallbackQueryHandler(callback=message_user, pattern=r"^message_user$"))
        self.application.add_handler(CallbackQueryHandler(callback=stop_texting, pattern=r"^stop_texting$"))
        self.application.add_handler(CallbackQueryHandler(callback=chat_history, pattern=r"^chat_history$"))
        self.application.add_handler(CallbackQueryHandler(callback=announce, pattern=r"^announce$"))
        self.application.add_handler(CallbackQueryHandler(callback=send_announcement, pattern=r"^confirm_announce"))
        self.application.add_handler(CallbackQueryHandler(callback=refresh_ticket_panel, pattern=r"^refresh_ticket_panel$"))
        self.application.add_handler(CallbackQueryHandler(callback=closed_tickets_list, pattern=r"^closed_tickets_list_[a-z]+$"))
        self.application.add_handler(CallbackQueryHandler(callback=export_ticket_data, pattern=r"^export$"))
        self.application.add_handler(CallbackQueryHandler(callback=show_stats, pattern=r"^stats$"))

        #dummy callback for buttons that do nothing. Prevents the infinite loading
        self.application.add_handler(CallbackQueryHandler(callback=dummy, pattern=r"^dummycallback$"))

        self.application.add_error_handler(role_error)

    def run(self):
        self.application.run_polling()

bot = TelegramBot(config.token)
bot.run()
