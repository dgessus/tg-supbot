import json

from telegram.ext import ContextTypes
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, InputMediaVideo, \
    InputMediaAnimation
import re

from utils.logger import logger
from utils.paths import Paths
from utils.config_loader import Load_config

config = Load_config()
paths = Paths()
supported_languages = config.supported_languages

class MessageConstructor:
    def __init__(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                 message_text = "вибачте, повідомлення не підвантажилось",
                 media: list[dict] = None, sanitize: bool = False,
                 remove_user_messages: bool = False, *args, **kwargs) -> None:

        self.update = update
        self.context = context
        self.message_text = message_text
        self.role = context.user_data['role']
        self.lang = context.user_data['lang'] if context.user_data['lang'] in supported_languages else 'uk'
        self.menu_position = context.user_data['menu_position'] or "any"
        user_ticket_ids = context.user_data.get('active_ticket_id', [])
        self.active_ticket_id = user_ticket_ids[-1] if user_ticket_ids else None
        self.user_id = self.update.effective_chat.id
        self.media = media
        self.sanitize = sanitize
        self.remove_user_messages = remove_user_messages
        self.args = args
        self.kwargs = kwargs
        self.__dict__.update(kwargs)
        self._load_data = self._Load_data(self)
        self._send = self._Send(self)

    @property
    def load_data(self) -> "_Load_data":
        return self._load_data

    @property
    def send(self) -> "_Send":
        return self._send

    @staticmethod
    def sanitize_md(string):
        escape_chars = r'_*\[\]()~`>#+\-=|{}.!'
        return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', string)

    class _Load_data:
        def __init__(self, parent):
            self.parent = parent
            self.update = parent.update
            self.lang = self.parent.lang
            self.role = self.parent.role
            self.menu_position = self.parent.menu_position
            self.message_text = self.parent.message_text
            self.jsondata = self._load_json()
            self.active_ticket_id = self.parent.active_ticket_id
            self.user_id = self.parent.user_id
            self.kwargs = self.parent.kwargs
            self.__dict__.update(self.kwargs)
            logger.info(f'active ticket id: <{self.active_ticket_id}>', extra={"user_id" : self.update.effective_chat.id})

        @staticmethod
      #  @lru_cache вызывает проблемы с повторным закрытием тикета юзером
        def _load_json():
            with open(paths.messages_path, 'r', encoding='UTF-8') as f:
                return json.load(f)

        def button_data(self):
            data = self.jsondata
            lang = self.lang
            context_data = data[self.role][lang][self.menu_position]
            buttons = {}
            var_map = {**self.__dict__}

            for json_key, json_value in context_data.items():
                if json_key == "message_text":
                    self.parent.message_text = json_value.format(**var_map)
                elif isinstance(json_value, dict):
                    logger.info(f'json value: <{json_value}>', extra={"user_id" : self.update.effective_chat.id})
                    for key, value in json_value.items():
                        if key in ("callback_data", "optional") and value is not None:
                            try:
                                if isinstance(json_value[key], dict):
                                    nested = json_value[key]
                                    for nested_key, nested_value in nested.items:
                                        nested[nested_key] = nested_value.format(**var_map)

                                json_value[key] = value.format(**var_map)

                            except Exception as e:
                                logger.warning(f"failed to evaluate json string while processing key <{key}>: <{e}>. Proceeding...", extra={"user_id" : self.update.effective_chat.id})
                                json_value[key] = value

                    buttons[json_key] = json_value

            return buttons

        def position_data(self) -> dict:
            data = self._load_json()
            context_data = data[self.role][self.lang][self.menu_position]
            positions = {}
            for json_key, json_value in context_data.items():
                if json_key == "previous_level":
                    logger.info(f'positional value "prev" from json: <{json_value}>', extra={"user_id" : self.update.effective_chat.id})
                    positions['previous_level'] = json_value

                elif json_key == "next_level":
                    logger.info(f'positional value "next" from json: <{json_value}>', extra={"user_id" : self.update.effective_chat.id})
                    positions['next_level'] = json_value

            return positions

    def load_keyboard(self):
        buttons = []
        loaded_data = self._load_data.button_data()
        for button in loaded_data.values():
            button_text = button.get('button_text')
            callback_data = button.get('callback_data')
            json_kwargs = button.get('optional', {}) or {}
            buttons.append(InlineKeyboardButton(button_text, callback_data=callback_data if callback_data else None, **json_kwargs))

        keyboard = MessageConstructor._chunk_buttons(buttons, 3)
        logger.info(f"buttons <{buttons}>", extra={"user_id" : self.update.effective_chat.id})
        logger.info(f"keyboard: <{keyboard}>", extra={"user_id" : self.update.effective_chat.id})
        markup = InlineKeyboardMarkup(keyboard)
        return markup

    @staticmethod
    def _chunk_buttons(buttons, chunk_size=3):
        return [buttons[i:i + chunk_size] for i in range(0, len(buttons), chunk_size)]

    class _Send:
        def __init__(self, parent):
            self.parent = parent
            self.context = self.parent.context
            self.update = self.parent.update
            self.keyboard = self.parent.load_keyboard()
            self.message_text = str(self.parent.message_text)
            self.media = self.parent.media
            self.sanitize = self.parent.sanitize
            self.remove_user_messages = self.parent.remove_user_messages
            self.args = self.parent.args
            self.kwargs = self.parent.kwargs
            self.user_id = self.parent.user_id
            self.__dict__.update(self.kwargs)

        async def _send(self, markup):
            sanitized_message_text = self.parent.sanitize_md(self.message_text) if self.sanitize else self.message_text

            if self.remove_user_messages:
                await self.clear_user_messages()

            if self.media is None:
                try:
                    chunked_message = self._message_text_delimiter(sanitized_message_text)

                    for message in chunked_message:
                        msg = await self.context.bot.send_message(chat_id=self.user_id, text=message, reply_markup=markup, **self.kwargs)
                        self.context.user_data['bot_message_ids'].append(msg.message_id)
                        logger.info(f"sent a message to the user", extra={"user_id" : self.update.effective_chat.id})

                except Exception as e:
                    logger.error(f"failed to send a message to the user", extra={"user_id" : self.update.effective_chat.id})
                    raise Exception('Failed to send message: {}'.format(e))

            else:
                if len(self.media) == 1:
                    if isinstance(self.media[0], InputMediaPhoto):
                        logger.info(f"found a single photo in media data: <{self.media[0]}>", extra={"user_id" : self.update.effective_chat.id})
                        msg = await self.context.bot.send_photo(chat_id=self.user_id, photo=self.media[0].media, caption=self.media[0].caption,
                                                                reply_markup=markup, **self.kwargs)
                        self.context.user_data['bot_message_ids'].append(msg.message_id)

                    if isinstance(self.media[0], InputMediaVideo):
                        logger.info(f"found a single video in media data: <{self.media[0]}>", extra={"user_id" : self.update.effective_chat.id})
                        msg = await self.context.bot.send_video(chat_id=self.user_id, video=self.media[0].media, caption=self.media[0].caption,
                                                                reply_markup=markup, **self.kwargs)
                        self.context.user_data['bot_message_ids'].append(msg.message_id)

                    if isinstance(self.media[0], InputMediaAnimation):
                        logger.info(f"found a single GIF in media data: <{self.media[0]}>", extra={"user_id" : self.update.effective_chat.id})
                        msg = await self.context.bot.send_animation(chat_id=self.user_id, animation=self.media[0].media, caption=self.media[0].caption,
                                                                    reply_markup=markup, **self.kwargs)
                        self.context.user_data['bot_message_ids'].append(msg.message_id)

                elif len(self.media) > 1:
                    logger.info(f"found an album in media data: <{self.media[0]}>", extra={"user_id" : self.update.effective_chat.id})
                    msg_list = await self.context.bot.send_media_group(chat_id=self.user_id, media=self.media, **self.kwargs)
                    bonus_message = await self.context.bot.send_message(chat_id=self.user_id, text="\u2063", reply_markup=markup, **self.kwargs)

                    self.context.user_data['bot_message_ids'].append(bonus_message.message_id)
                    for message in msg_list:
                        self.context.user_data['bot_message_ids'].append(message.message_id)
                else:
                    logger.info(f"No media found in the media list", extra={"user_id" : self.update.effective_chat.id})
                    raise Exception("No media found in the media list", self.update.effective_chat.id)

        async def _edit(self, markup):
            if self.remove_user_messages:
                await self.clear_user_messages()

            try:
                message_id = self.context.user_data['bot_message_ids'][-1]
            except KeyError or IndexError:
                message_id = None

            if message_id is not None:
                try:
                    safe_message_text = self.parent.sanitize_md(self.message_text) if self.sanitize else self.message_text
                    await self.context.bot.edit_message_text(text=safe_message_text, chat_id=self.user_id, message_id=message_id,
                                                             reply_markup=markup)

                    logger.info(f"edited message for user", extra={"user_id" : self.update.effective_chat.id})

                except Exception as e:
                    logger.warning(f"failed to edit message for user; taget message id: <{message_id}>, API error: <{e}>",
                                   extra={"user_id" : self.update.effective_chat.id})
                    raise

            elif self.media:
                logger.error("cannot add media to an existing message", extra={"user_id" : self.update.effective_chat.id})
                raise TypeError("Cannot add media to an existing message")

            else:
                logger.warning(f"message to edit is None", extra={"user_id" : self.update.effective_chat.id})
                raise ValueError("Message to edit is None")

        @staticmethod
        def _message_text_delimiter(text: str) -> list[str]:
            max_char_count = 4096
            messages = text.split('\n')
            segments = []
            buffer = ""

            for segment in messages:
                if len(buffer) + len(segment) + 1 > max_char_count:
                    segments.append(buffer)
                    buffer = segment
                else:
                    buffer += ('\n' if buffer else '') + segment

            if buffer:
                segments.append(buffer)

            return segments

        async def clear_bot_messages(self):
            if self.context.user_data['bot_message_ids']:
                for message_id in self.context.user_data['bot_message_ids']:
                    try:
                        await self.context.bot.delete_message(self.user_id, message_id)
                    except Exception as e:
                        logger.warning(f"failed to delete message for user; taget message id: <{message_id}>, error: <{e}>",
                                       extra={"user_id" : self.update.effective_chat.id})

                self.context.user_data['bot_message_ids'].clear()

        async def clear_user_messages(self):
            user_messages = self.context.user_data["user_messages"]
            logger.info(f"clearing user messages", extra={"user_id" : self.update.effective_chat.id})

            for message in user_messages:
                try:
                    await self.context.bot.delete_message(message.chat.id, message.message_id)
                except Exception as e:
                    logger.warning(f"failed to delete user message: <{message}>; API error: <{e}>", extra={"user_id" : self.update.effective_chat.id})

            self.context.user_data["user_messages"].clear()

        async def new_message(self):
            logger.info(f'method has been called', extra={"user_id" : self.update.effective_chat.id})
            keyboard = self.keyboard
            try:
                await self._send(keyboard)
            except Exception as e:
                logger.error(f'failed to send new message to to user; API error: <{e}>', extra={"user_id" : self.update.effective_chat.id})

        async def edit_message(self):
            logger.info(f'method has been called', extra={"user_id" : self.update.effective_chat.id})
            keyboard = self.keyboard
            try:
                await self._edit(keyboard)
            except Exception as e:
                logger.warning(f'failed to edit bot message; API error: <{e}>', extra={"user_id" : self.update.effective_chat.id})
                await self.clear_bot_messages()
                await self._send(keyboard)

        async def refresh_message(self):
            keyboard = self.keyboard
            await self.clear_bot_messages()
            await self._send(keyboard)
