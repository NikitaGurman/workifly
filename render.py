from aiogram.exceptions import TelegramBadRequest
from aiogram.types import FSInputFile, InputMediaPhoto, Message, CallbackQuery

# Кэш file_id уже загруженных в Telegram баннеров, чтобы не грузить файл с диска
# заново при каждом переключении экрана — после первой отправки Telegram выдаёт
# file_id, и все следующие отправки того же файла идут по нему мгновенно.
_file_id_cache: dict[str, str] = {}


def _photo_input(photo_path: str):
    return _file_id_cache.get(photo_path) or FSInputFile(photo_path)


def _remember_file_id(photo_path: str, message: Message):
    if message and message.photo:
        _file_id_cache[photo_path] = message.photo[-1].file_id


async def send_screen(message: Message, photo_path: str, caption: str, reply_markup=None) -> Message:
    """Отправляет новое сообщение: фото + подпись + клавиатура одним целым."""
    sent = await message.answer_photo(
        photo=_photo_input(photo_path),
        caption=caption,
        reply_markup=reply_markup,
    )
    _remember_file_id(photo_path, sent)
    return sent


async def edit_screen(call: CallbackQuery, photo_path: str, caption: str, reply_markup=None) -> Message:
    """Заменяет фото/подпись/клавиатуру в уже показанном сообщении (без спама новыми сообщениями).

    Если предыдущее сообщение было обычным текстовым (не фото) — Telegram не даёт
    его отредактировать через edit_media. В этом случае просто удаляем старое
    сообщение и отправляем новое фото — без падения с ошибкой.
    """
    media = InputMediaPhoto(media=_photo_input(photo_path), caption=caption)
    try:
        edited = await call.message.edit_media(media=media, reply_markup=reply_markup)
    except TelegramBadRequest:
        try:
            await call.message.delete()
        except TelegramBadRequest:
            pass
        edited = await call.message.answer_photo(
            photo=_photo_input(photo_path),
            caption=caption,
            reply_markup=reply_markup,
        )
    _remember_file_id(photo_path, edited)
    return edited


async def edit_text_screen(call: CallbackQuery, text: str, reply_markup=None) -> Message:
    """Для случаев, когда контент не влезает в подпись к фото (например, длинный текст
    заявки — у подписи лимит 1024 символа, у обычного сообщения 4096). Всегда пересоздаёт
    сообщение как обычный текст без баннера."""
    try:
        await call.message.delete()
    except TelegramBadRequest:
        pass
    return await call.message.answer(text, reply_markup=reply_markup)
