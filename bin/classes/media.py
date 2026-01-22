from telegram.ext import CallbackContext
from telegram import InputMediaPhoto, InputMediaVideo, InputMediaAnimation, Update
import json

from utils.logger import logger

class Media:
    def __init__(self, update: Update, context: CallbackContext):
        self.context = context
        self.update = update

    def get_user_media(self):
        logger.info(
            f"received contents of context.user_data['user_messages']", extra={"user_id" : self.update.effective_chat.id})

        user_media = []
        for message in self.context.user_data["user_messages"]:

            if message.photo:
                logger.info(f'found a photo in context_user_data', extra={"user_id" : self.update.effective_chat.id})
                user_media.append(InputMediaPhoto(media=message.photo[-1].file_id))
            if message.video:
                user_media.append(InputMediaVideo(media=message.video.file_id))
            if message.animation:
                user_media.append(InputMediaAnimation(media=message.animation.file_id))

        return user_media

    def serialize(self) -> str:
        data = self.get_user_media()
        serialized = []
        logger.info(f"serializing user media for storage", extra={"user_id" : self.update.effective_chat.id})

        for file in data:
            if isinstance(file, InputMediaPhoto):
                serialized.append(
                    {"type": "photo",
                     "file_id": file.media}
                )
            if isinstance(file, InputMediaVideo):
                serialized.append(
                    {"type": "video",
                     "file_id": file.media}
                )
            if isinstance(file, InputMediaAnimation):
                serialized.append(
                    {"type": "animation",
                     "file_id": file.media}
                ),

        return json.dumps(serialized, ensure_ascii=False)

    @staticmethod
    def deserialize(serialized_string, caption=None) -> list[InputMediaPhoto | InputMediaVideo | InputMediaAnimation]:
        data = json.loads(serialized_string)
        media_deserialized = []
        for i, item in enumerate(data):
            if item['type'] == 'photo':
                if i == 0:
                    media_deserialized.append(InputMediaPhoto(media=item['file_id'], caption=caption))
                else:
                    media_deserialized.append(InputMediaPhoto(media=item['file_id']))

            if item['type'] == 'video':
                if i == 0:
                    media_deserialized.append(InputMediaVideo(media=item['file_id'], caption=caption))
                else:
                    media_deserialized.append(InputMediaVideo(media=item['file_id']))
            if item['type'] == 'animation':
                if i == 0:
                    media_deserialized.append(InputMediaAnimation(media=item['file_id'], caption=caption))
                else:
                    media_deserialized.append(InputMediaAnimation(media=item['file_id']))

        return media_deserialized
