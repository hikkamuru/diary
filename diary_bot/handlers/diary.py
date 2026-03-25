import asyncio
import logging
import os
import aiohttp
from datetime import datetime
from pathlib import Path

import requests
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

from database import db

router = Router()
logger = logging.getLogger(__name__)


class DiaryStates(StatesGroup):
    waiting_for_text = State()


async def recognize_voice_yandex(file_path: Path) -> str:
    try:
        import config
        api_key = config.YANDEX_API_KEY
        
        if not api_key:
            logger.warning("Yandex API key not set")
            return None
        
        with open(file_path, "rb") as audio_file:
            audio_data = audio_file.read()
        
        url = "https://transcribe.api.cloud.yandex.net/speech/v1/recognize"
        headers = {"Authorization": f"Api-Key {api_key}"}
        
        response = requests.post(url, headers=headers, data=audio_data)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("result"):
                return result["result"]
            return "Не удалось распознать речь"
        else:
            logger.error(f"Yandex API error: {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Voice recognition error: {e}")
        return None


async def recognize_voice_file(file_path: Path) -> str:
    result = await recognize_voice_yandex(file_path)
    if result:
        return result
    
    return "Настрой Yandex SpeechKit для распознавания голоса"


main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📖 Читать дневник")],
        [KeyboardButton(text="📝 Добавить запись")],
        [KeyboardButton(text="🗑️ Удалить запись")],
        [KeyboardButton(text="📊 Статистика")],
    ],
    resize_keyboard=True
)


@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "📔 <b>Личный дневник</b>\n\n"
        "Записывай голосовые или текстовые сообщения о своём дне, "
        "а потом перечитывай их в любое время!",
        reply_markup=main_keyboard
    )


@router.message(F.text == "📖 Читать дневник")
async def read_diary(message: Message):
    user_id = message.from_user.id
    entries = db.get_entries(user_id, limit=10)
    
    if not entries:
        await message.answer("Записей пока нет. Добавь первую!")
        return
    
    response = "📖 <b>Последние записи:</b>\n\n"
    
    for entry in entries:
        entry_id, content, entry_date, created_at = entry
        short_content = content[:200] + "..." if len(content) > 200 else content
        response += f"📅 <b>{entry_date}</b>\n{short_content}\n\n"
    
    await message.answer(response)


@router.message(F.text == "📝 Добавить запись")
async def add_entry_prompt(message: Message, state: FSMContext):
    await message.answer(
        "📝 Напиши или запиши голосовое сообщение о своём дне:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Отмена")]],
            resize_keyboard=True
        )
    )
    await state.set_state(DiaryStates.waiting_for_text)


@router.message(F.text == "Отмена")
async def cancel_entry(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Отменено", reply_markup=main_keyboard)


@router.message(DiaryStates.waiting_for_text, F.text)
async def process_text_entry(message: Message, state: FSMContext):
    user_id = message.from_user.id
    content = message.text.strip()
    entry_date = datetime.now().strftime("%Y-%m-%d")
    
    db.add_entry(user_id, content, entry_date)
    
    await message.answer(
        f"✅ Запись сохранена за {entry_date}!",
        reply_markup=main_keyboard
    )
    await state.clear()


@router.message(F.text == "🗑️ Удалить запись")
async def delete_entry_prompt(message: Message):
    user_id = message.from_user.id
    entries = db.get_entries(user_id, limit=5)
    
    if not entries:
        await message.answer("Записей нет")
        return
    
    response = "Выбери номер записи для удаления:\n\n"
    
    for i, entry in enumerate(entries, 1):
        entry_id, content, entry_date, created_at = entry
        short_content = content[:50] + "..." if len(content) > 50 else content
        response += f"{i}. {entry_date}: {short_content}\n"
    
    await message.answer(response)


@router.message(F.text == "📊 Статистика")
async def show_stats(message: Message):
    user_id = message.from_user.id
    count = db.get_entry_count(user_id)
    
    entries = db.get_entries(user_id, limit=100)
    dates = [e[2] for e in entries]
    unique_dates = len(set(dates))
    
    await message.answer(
        f"📊 <b>Статистика твоего дневника:</b>\n\n"
        f"📝 Всего записей: {count}\n"
        f"📅 Дней с записями: {unique_dates}",
        reply_markup=main_keyboard
    )


@router.message(F.voice)
async def handle_voice(message: Message, state: FSMContext):
    logger.info(f"Voice message received from user {message.from_user.id}")
    user_id = message.from_user.id
    
    await message.answer("🎤 Распознаю голос...")
    
    try:
        voice_file = await message.bot.download(message.voice)
        file_path = Path(f"temp_voice_{user_id}.ogg")
        
        with open(file_path, "wb") as f:
            f.write(voice_file.getvalue())
        
        text = await recognize_voice_file(file_path)
        file_path.unlink()
        
        if text == "Не удалось распознать речь":
            await message.answer(
                "😕 Не удалось распознать голос. Попробуй ещё раз:",
                reply_markup=main_keyboard
            )
            return
        
        entry_date = datetime.now().strftime("%Y-%m-%d")
        db.add_entry(user_id, text, entry_date)
        
        short_text = text[:100] + "..." if len(text) > 100 else text
        await message.answer(
            f"✅ Запись сохранена!\n\n📝 <i>{short_text}</i>\n\nЗа {entry_date}",
            reply_markup=main_keyboard
        )
        
    except Exception as e:
        logger.error(f"Voice processing error: {e}")
        await message.answer(
            "Произошла ошибка при обработке. Попробуй ещё раз:",
            reply_markup=main_keyboard
        )


@router.message()
async def debug_all_messages(message: Message):
    logger.info(f"Received message: type={message.content_type}, from={message.from_user.id}")
    if message.voice:
        logger.info("Voice detected!")

