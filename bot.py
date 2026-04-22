import asyncio
import logging
import os
from datetime import datetime, timedelta, date

import gspread
from google.oauth2.service_account import Credentials

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN не знайдено")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
client = gspread.authorize(creds)
sheet = client.open("GROW_bot_registrations").sheet1


class Form(StatesGroup):
    consent = State()
    name = State()
    phone = State()
    email = State()
    location = State()
    gender = State()
    ipn = State()
    age = State()
    vuln = State()
    consult = State()
    question = State()
    date = State()
    time = State()
    format = State()
    online_type = State()
    confirm = State()


dp = Dispatcher(storage=MemoryStorage())

ZOOM = "https://us04web.zoom.us/j/3059870825?pwd=S2ozbDg4Mi9EQkxFaXB0QUVsUlFFQT09"
ADDRESS = "м. Київ, вул. М. Берлінського, буд. 15"
MAP = "https://www.google.com/maps/search/?api=1&query=%D0%9A%D0%B8%D1%97%D0%B2+%D0%91%D0%B5%D1%80%D0%BB%D1%96%D0%BD%D1%81%D1%8C%D0%BA%D0%BE%D0%B3%D0%BE+15"

WELCOME_TEXT = (
    "Вітаємо!\n\n"
    "Команда проєкту GROW (Карітас-Київ) готова надати безкоштовні консультації "
    "з юридичних та бухгалтерських питань.\n\n"
    "Щоб записатись, натисніть «Далі»."
)

CONSENT_TEXT = (
    "Перед початком нам потрібна Ваша згода на обробку персональних даних.\n\n"
    "Чи погоджуєтесь Ви?"
)

VULNERABILITY_OPTIONS = {
    "single_parent": "самотня мати/батько неповнолітніх дітей",
    "disability": "людина з інвалідністю",
    "age_50_plus": "особи віком 50+ без статусу пенсіонер",
    "large_family": "багатодітні сім'ї",
    "idp": "ВПО",
    "veteran_family": "ветерани та члени їхніх родин",
    "low_income": "домогосподарства з низьким рівнем доходу",
}

CONSULTATION_TYPES = {
    "legal": "Юридичні",
    "accounting": "Бухгалтерські",
}


def save_to_sheet(data: dict, message: Message) -> None:
    row = [
        datetime.now().strftime("%Y-%m-%d %H:%M"),
        message.from_user.id if message.from_user else "",
        message.from_user.username if message.from_user else "",
        data.get("name", ""),
        data.get("phone", ""),
        data.get("email", ""),
        data.get("location", ""),
        data.get("gender", ""),
        data.get("ipn", ""),
        data.get("age", ""),
        ", ".join(data.get("vulnerability_labels", [])),
        data.get("consult", ""),
        data.get("question", ""),
        data.get("date", ""),
        data.get("time", ""),
        data.get("format", ""),
        data.get("online", ""),
    ]
    sheet.append_row(row)


def get_taken_slots(label: str, selected_date: str) -> set[str]:
    rows = sheet.get_all_values()
    taken = set()

    for row in rows[1:]:
        if len(row) < 15:
            continue
        if row[11] == label and row[13] == selected_date:
            taken.add(row[14])

    return taken


def times(code: str) -> list[str]:
    if code == "accounting":
        return ["10:00", "11:00", "12:00", "13:00", "14:00", "15:00"]
    return ["10:30", "11:30", "12:30", "13:30", "14:30", "15:30"]


def available_times(code: str, label: str, selected_date: str) -> list[str]:
    return [t for t in times(code) if t not in get_taken_slots(label, selected_date)]


def kb_start():
    b = InlineKeyboardBuilder()
    b.button(text="Далі", callback_data="next")
    b.adjust(1)
    return b.as_markup()


def kb_yesno():
    b = InlineKeyboardBuilder()
    b.button(text="Так", callback_data="yes")
    b.button(text="Ні", callback_data="no")
    b.adjust(2)
    return b.as_markup()


def kb_gender():
    b = InlineKeyboardBuilder()
    b.button(text="Ж", callback_data="g:Ж")
    b.button(text="Ч", callback_data="g:Ч")
    b.adjust(2)
    return b.as_markup()


def kb_consult():
    b = InlineKeyboardBuilder()
    b.button(text="Юридичні", callback_data="c:legal")
    b.button(text="Бухгалтерські", callback_data="c:accounting")
    b.adjust(1)
    return b.as_markup()


def kb_format():
    b = InlineKeyboardBuilder()
    b.button(text="Онлайн", callback_data="f:on")
    b.button(text="Офлайн", callback_data="f:off")
    b.adjust(1)
    return b.as_markup()


def kb_online():
    b = InlineKeyboardBuilder()
    b.button(text="Zoom", callback_data="on:zoom")
    b.button(text="Телефон", callback_data="on:phone")
    b.adjust(1)
    return b.as_markup()


def kb_next():
    b = InlineKeyboardBuilder()
    b.button(text="Далі", callback_data="go")
    b.adjust(1)
    return b.as_markup()


def kb_confirm():
    b = InlineKeyboardBuilder()
    b.button(text="Так", callback_data="ok")
    b.button(text="Ні", callback_data="cancel")
    b.adjust(2)
    return b.as_markup()


def kb_map_confirm():
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="Відкрити на карті", url=MAP))
    b.button(text="Так", callback_data="ok")
    b.button(text="Ні", callback_data="cancel")
    b.adjust(1, 2)
    return b.as_markup()


def kb_vuln(selected: list[str]):
    b = InlineKeyboardBuilder()
    for code, label in VULNERABILITY_OPTIONS.items():
        prefix = "✅ " if code in selected else ""
        b.button(text=f"{prefix}{label}", callback_data=f"v:{code}")
    b.button(text="Готово", callback_data="v:done")
    b.adjust(1)
    return b.as_markup()


def dates() -> list[date]:
    result = []
    current = datetime.now().date()
    end = current + timedelta(days=30)

    while current <= end:
        if current.weekday() == 2:
            result.append(current)
        current += timedelta(days=1)

    return result


def kb_dates():
    b = InlineKeyboardBuilder()
    for d in dates():
        b.button(text=d.strftime("%d.%m.%Y"), callback_data=f"d:{d.isoformat()}")
    b.adjust(1)
    return b.as_markup()


def kb_times(selected_date: str, code: str, label: str):
    b = InlineKeyboardBuilder()
    for t in available_times(code, label, selected_date):
        b.button(text=t, callback_data=f"t:{selected_date}|{t}")
    b.adjust(2)
    return b.as_markup()


def summary(data: dict) -> str:
    txt = (
        "Перевірте, будь ласка, дані:\n\n"
        f"ПІБ: {data.get('name', '')}\n"
        f"Телефон: {data.get('phone', '')}\n"
        f"Email: {data.get('email', '')}\n"
        f"Місце проживання: {data.get('location', '')}\n"
        f"Стать: {data.get('gender', '')}\n"
        f"ІПН: {data.get('ipn', '')}\n"
        f"Вік: {data.get('age', '')}\n"
        f"Категорії: {', '.join(data.get('vulnerability_labels', []))}\n"
        f"Напрямок: {data.get('consult', '')}\n"
        f"Питання: {data.get('question', '')}\n"
        f"Дата: {data.get('date', '')}\n"
        f"Час: {data.get('time', '')}\n"
        f"Формат: {data.get('format', '')}"
    )

    if data.get("format") == "Онлайн":
        if data.get("online") == "Zoom":
            txt += f"\nZoom:\n{ZOOM}"
        else:
            txt += "\nТелефонна консультація"

    return txt


def is_valid_ipn(ipn: str) -> bool:
    if not ipn.isdigit() or len(ipn) != 10:
        return False

    digits = [int(d) for d in ipn]
    weights = [-1, 5, 7, 9, 4, 6, 10, 5, 7]
    checksum = sum(d * w for d, w in zip(digits[:9], weights))
    control = checksum % 11
    if control > 9:
        control = control % 10
    return control == digits[9]


@dp.message(CommandStart())
async def start_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(WELCOME_TEXT, reply_markup=kb_start())


@dp.callback_query(F.data == "next")
async def consent_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Form.consent)
    await callback.message.edit_text(CONSENT_TEXT, reply_markup=kb_yesno())
    await callback.answer()


@dp.callback_query(Form.consent, F.data == "yes")
async def name_handler_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Form.name)
    await callback.message.edit_text("Будь ласка, вкажіть Ваше ПІБ:")
    await callback.answer()


@dp.callback_query(Form.consent, F.data == "no")
async def consent_no_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(WELCOME_TEXT, reply_markup=kb_start())
    await callback.answer("Реєстрацію не продовжено")


@dp.message(Form.name)
async def phone_handler_start(message: Message, state: FSMContext) -> None:
    await state.update_data(name=message.text.strip())
    await state.set_state(Form.phone)
    await message.answer("Вкажіть номер телефону:")


@dp.message(Form.phone)
async def email_handler_start(message: Message, state: FSMContext) -> None:
    await state.update_data(phone=message.text.strip())
    await state.set_state(Form.email)
    await message.answer("Вкажіть електронну пошту:")


@dp.message(Form.email)
async def location_handler_start(message: Message, state: FSMContext) -> None:
    await state.update_data(email=message.text.strip())
    await state.set_state(Form.location)
    await message.answer("Вкажіть місце проживання:")


@dp.message(Form.location)
async def gender_handler_start(message: Message, state: FSMContext) -> None:
    await state.update_data(location=message.text.strip())
    await state.set_state(Form.gender)
    await message.answer("Оберіть стать:", reply_markup=kb_gender())


@dp.callback_query(Form.gender, F.data.startswith("g:"))
async def ipn_handler_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(gender=callback.data.split(":", 1)[1])
    await state.set_state(Form.ipn)
    await callback.message.edit_text("Вкажіть ІПН:")
    await callback.answer()


@dp.message(Form.ipn)
async def age_handler_start(message: Message, state: FSMContext) -> None:
    ipn = message.text.strip()
    if not is_valid_ipn(ipn):
        await message.answer("Некоректний ІПН. Перевірте номер і спробуйте ще раз.")
        return

    await state.update_data(ipn=ipn)
    await state.set_state(Form.age)
    await message.answer("Вкажіть Ваш вік:")


@dp.message(Form.age)
async def vuln_handler_start(message: Message, state: FSMContext) -> None:
    await state.update_data(age=message.text.strip(), vulnerability_labels=[])
    await state.set_state(Form.vuln)
    await message.answer(
        "Оберіть категорії вразливості. Можна вибрати декілька. Після вибору натисніть «Готово».",
        reply_markup=kb_vuln([])
    )


@dp.callback_query(Form.vuln, F.data.startswith("v:"))
async def vuln_handler(callback: CallbackQuery, state: FSMContext) -> None:
    action = callback.data.split(":", 1)[1]
    data = await state.get_data()
    selected = data.get("vulnerability_codes", [])

    if action == "done":
        if not selected:
            await callback.answer("Оберіть хоча б одну категорію.", show_alert=True)
            return

        labels = [VULNERABILITY_OPTIONS[x] for x in selected]
        await state.update_data(vulnerability_labels=labels)
        await state.set_state(Form.consult)
        await callback.message.edit_text("Оберіть напрямок консультації:", reply_markup=kb_consult())
        await callback.answer()
        return

    if action in selected:
        selected.remove(action)
    else:
        selected.append(action)

    await state.update_data(vulnerability_codes=selected)
    await callback.message.edit_reply_markup(reply_markup=kb_vuln(selected))
    await callback.answer()


@dp.callback_query(Form.consult, F.data.startswith("c:"))
async def question_handler_start(callback: CallbackQuery, state: FSMContext) -> None:
    code = callback.data.split(":", 1)[1]
    label = CONSULTATION_TYPES.get(code, "")

    await state.update_data(consult=label, code=code)
    await state.set_state(Form.question)
    await callback.message.edit_text("Опишіть коротко Ваше питання:")
    await callback.answer()


@dp.message(Form.question)
async def date_handler_start(message: Message, state: FSMContext) -> None:
    await state.update_data(question=message.text.strip())
    await state.set_state(Form.date)
    await message.answer("Оберіть дату:", reply_markup=kb_dates())


@dp.callback_query(Form.date, F.data.startswith("d:"))
async def time_handler_start(callback: CallbackQuery, state: FSMContext) -> None:
    selected_date = callback.data.split(":", 1)[1]
    data = await state.get_data()

    free_times = available_times(data["code"], data["consult"], selected_date)
    if not free_times:
        await callback.message.edit_text("На цю дату немає вільних слотів.", reply_markup=kb_dates())
        await callback.answer()
        return

    await state.update_data(date=selected_date)
    await state.set_state(Form.time)
    await callback.message.edit_text(
        "Оберіть час:",
        reply_markup=kb_times(selected_date, data["code"], data["consult"])
    )
    await callback.answer()


@dp.callback_query(Form.time, F.data.startswith("t:"))
async def format_handler_start(callback: CallbackQuery, state: FSMContext) -> None:
    selected_date, selected_time = callback.data.split(":", 1)[1].split("|", 1)

    data = await state.get_data()
    if selected_time in get_taken_slots(data["consult"], selected_date):
        await callback.message.edit_text(
            "Цей слот уже зайнятий. Оберіть, будь ласка, інший час:",
            reply_markup=kb_times(selected_date, data["code"], data["consult"])
        )
        await callback.answer()
        return

    await state.update_data(date=selected_date, time=selected_time)
    await state.set_state(Form.format)
    await callback.message.edit_text("Формат:", reply_markup=kb_format())
    await callback.answer()


@dp.callback_query(Form.format, F.data.startswith("f:"))
async def format_handler(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data == "f:off":
        await state.update_data(format="Офлайн", online="")
        await state.set_state(Form.confirm)
        data = await state.get_data()
        await callback.message.edit_text(
            summary(data) + f"\n\nАдреса: {ADDRESS}",
            reply_markup=kb_map_confirm()
        )
        await callback.answer()
    else:
        await state.update_data(format="Онлайн")
        await state.set_state(Form.online_type)
        await callback.message.edit_text("Як саме онлайн?", reply_markup=kb_online())
        await callback.answer()


@dp.callback_query(Form.online_type, F.data.startswith("on:"))
async def online_handler(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data == "on:zoom":
        await state.update_data(online="Zoom")
        await callback.message.edit_text(f"Zoom:\n{ZOOM}", reply_markup=kb_next())
        await callback.answer()
    else:
        await state.update_data(online="Телефон")
        await callback.message.edit_text("Вам зателефонують у вибраний час.", reply_markup=kb_next())
        await callback.answer()


@dp.callback_query(Form.online_type, F.data == "go")
async def confirm_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Form.confirm)
    data = await state.get_data()
    await callback.message.edit_text(summary(data), reply_markup=kb_confirm())
    await callback.answer()


@dp.callback_query(Form.confirm, F.data == "ok")
async def done_handler(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()

    if data["time"] in get_taken_slots(data["consult"], data["date"]):
        await state.clear()
        await callback.message.answer(
            "На жаль, цей час щойно став недоступним. Будь ласка, спробуйте записатись ще раз."
        )
        await callback.message.answer(WELCOME_TEXT, reply_markup=kb_start())
        await callback.answer("Слот зайнято")
        return

    save_to_sheet(data, callback.message)

    txt = (
        "Дякуємо за реєстрацію.\n\n"
        "З Вами зв’яжуться."
    )

    if data.get("online") == "Zoom":
        txt += "\n\nВикористайте Zoom посилання у вибраний час."

    txt += "\n\n+380937011342"

    await state.clear()
    await callback.message.answer(txt)
    await callback.answer("Запис підтверджено")


@dp.callback_query(Form.confirm, F.data == "cancel")
async def cancel_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(WELCOME_TEXT, reply_markup=kb_start())
    await callback.answer("Скасовано")


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())