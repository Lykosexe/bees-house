"""
Bees House 🐝 — Telegram Bot
Облік рамок, тирси, складу
"""
import os, json, logging, asyncio
from datetime import date, datetime
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    WebAppInfo, KeyboardButton, ReplyKeyboardMarkup
)
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://your-username.github.io/bees-house")
DB_PATH = os.path.join(os.path.dirname(__file__), "../data/db.json")

# ── Database ──────────────────────────────────────────────────────────────
def load_db():
    with open(DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_db(db):
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

def gen_id():
    import random, string, time
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choices(chars, k=8)) + hex(int(time.time() * 1000))[2:]

def today_str():
    return date.today().isoformat()

def fmt(n):
    n = round(float(n or 0), 2)
    if n == int(n):
        return f"{int(n):,}".replace(",", "\u00a0")
    return f"{n:,.2f}".replace(",", "\u00a0")

def fmt_date(iso):
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%d.%m.%Y")
    except:
        return iso

def rec_earned(r):
    return (r.get("dadan", 0) * r.get("pDadan", 0) +
            r.get("ruta", 0) * r.get("pRuta", 0) +
            r.get("magazynna", 0) * (r.get("pMag") or r.get("pMagazynna", 0)))

def w_stats(w, records):
    recs = [r for r in records if r["workerId"] == w["id"]]
    earned = sum(rec_earned(r) for r in recs if r["type"] == "frames")
    paid   = sum(r.get("amount", 0) for r in recs if r["type"] == "payment")
    frames = sum(r.get("dadan",0) + r.get("ruta",0) + r.get("magazynna",0)
                 for r in recs if r["type"] == "frames")
    return {**w, "earned": earned, "paid": paid, "debt": earned - paid, "frames": frames}

def worker_by_id(db, wid):
    return next((w for w in db["workers"] if w["id"] == wid), None)

# ── FSM States ────────────────────────────────────────────────────────────
class AddFrames(StatesGroup):
    worker   = State()
    dadan    = State()
    ruta     = State()
    magazynna = State()

class AddPayment(StatesGroup):
    worker = State()
    amount = State()

class AddWorker(StatesGroup):
    name        = State()
    price_dadan = State()
    price_ruta  = State()
    price_mag   = State()

# ── Keyboards ─────────────────────────────────────────────────────────────
def main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🏠 Головна"),   KeyboardButton(text="👷 Виконавці")],
        [KeyboardButton(text="🔨 Рамки"),     KeyboardButton(text="💰 Виплата")],
        [KeyboardButton(text="📊 Звіт"),      KeyboardButton(text="⚙️ Налаштування")],
    ], resize_keyboard=True)

def webapp_kb(url: str):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="📱 Відкрити додаток",
            web_app=WebAppInfo(url=url)
        )
    ]])

def workers_inline_kb(workers, prefix="pay"):
    rows = [[InlineKeyboardButton(text=w["name"], callback_data=f"{prefix}:{w['id']}")]
            for w in workers]
    rows.append([InlineKeyboardButton(text="❌ Скасувати", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def confirm_kb(yes_data, no_data="cancel"):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Так", callback_data=yes_data),
        InlineKeyboardButton(text="❌ Ні",  callback_data=no_data),
    ]])

# ── Bot setup ─────────────────────────────────────────────────────────────
bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher(storage=MemoryStorage())

# ── /start ────────────────────────────────────────────────────────────────
@dp.message(CommandStart())
async def cmd_start(msg: Message):
    await msg.answer(
        "🐝 <b>Bees House</b> — облік виробництва\n\n"
        "Обери розділ у меню або відкрий повний додаток кнопкою нижче.",
        parse_mode="HTML",
        reply_markup=main_kb()
    )
    await msg.answer("📱 Повний додаток:", reply_markup=webapp_kb(WEBAPP_URL))

# ── Головна ───────────────────────────────────────────────────────────────
@dp.message(F.text == "🏠 Головна")
async def home(msg: Message):
    db = load_db()
    stats = [w_stats(w, db["records"]) for w in db["workers"]]
    total_frames = sum(s["frames"] for s in stats)
    total_debt   = sum(s["debt"]   for s in stats)
    total_paid   = sum(s["paid"]   for s in stats)

    debt_sign = "📉 Борг" if total_debt > 0 else ("📈 Переплата" if total_debt < 0 else "✅ Розраховано")
    lines = [
        f"🐝 <b>Облік рамок</b> — {datetime.now().strftime('%d.%m.%Y')}",
        "",
        f"🔨 Рамок збито: <b>{total_frames}</b>",
        f"{debt_sign}: <b>{fmt(abs(total_debt))} ₴</b>  (виплачено {fmt(total_paid)} ₴)",
        "",
        "<b>Виконавці:</b>",
    ]
    for s in stats:
        debt_str = f"борг {fmt(s['debt'])} ₴" if s['debt'] > 0 else \
                   (f"переплата {fmt(abs(s['debt']))} ₴" if s['debt'] < 0 else "✓ розраховано")
        lines.append(f"• {s['name']} — {s['frames']} рам. | {debt_str}")

    await msg.answer("\n".join(lines), parse_mode="HTML", reply_markup=main_kb())

# ── Виконавці ─────────────────────────────────────────────────────────────
@dp.message(F.text == "👷 Виконавці")
async def workers_list(msg: Message):
    db = load_db()
    stats = [w_stats(w, db["records"]) for w in db["workers"]]
    if not stats:
        await msg.answer("Виконавців ще немає. Додайте через додаток 📱",
                         reply_markup=webapp_kb(WEBAPP_URL))
        return
    lines = ["<b>👷 Виконавці:</b>", ""]
    for s in stats:
        p = s.get("prices", {})
        debt_str = f"🔴 Борг {fmt(s['debt'])} ₴" if s['debt'] > 0 else \
                   (f"🟢 Переплата {fmt(abs(s['debt']))} ₴" if s['debt'] < 0 else "🟡 Розраховано")
        lines.append(
            f"<b>{s['name']}</b>\n"
            f"  Рамок: {s['frames']} | Нарах: {fmt(s['earned'])} ₴\n"
            f"  Ціни: Дадан {p.get('dadan','?')} | Рута {p.get('ruta','?')} | Маг. {p.get('magazynna','?')} ₴\n"
            f"  {debt_str}"
        )
    await msg.answer("\n\n".join(lines), parse_mode="HTML")

# ── Рамки: вибір виконавця ────────────────────────────────────────────────
@dp.message(F.text == "🔨 Рамки")
async def frames_start(msg: Message, state: FSMContext):
    db = load_db()
    if not db["workers"]:
        await msg.answer("Спочатку додайте виконавця через додаток 📱",
                         reply_markup=webapp_kb(WEBAPP_URL))
        return
    await state.set_state(AddFrames.worker)
    await msg.answer("👷 Вибери виконавця:",
                     reply_markup=workers_inline_kb(db["workers"], "frames"))

@dp.callback_query(AddFrames.worker, F.data.startswith("frames:"))
async def frames_worker(cb: CallbackQuery, state: FSMContext):
    wid = cb.data.split(":")[1]
    db  = load_db()
    w   = worker_by_id(db, wid)
    await state.update_data(wid=wid, prices=w["prices"])
    await state.set_state(AddFrames.dadan)
    await cb.message.edit_text(
        f"👷 <b>{w['name']}</b>\n\n🟠 Скільки <b>Дадан</b>? (0 якщо немає)",
        parse_mode="HTML"
    )

@dp.message(AddFrames.dadan)
async def frames_dadan(msg: Message, state: FSMContext):
    try:
        n = int(msg.text.strip())
    except:
        await msg.answer("Введи ціле число, наприклад: 150")
        return
    await state.update_data(dadan=n)
    await state.set_state(AddFrames.ruta)
    await msg.answer("🔵 Скільки <b>Рута</b>? (0 якщо немає)", parse_mode="HTML")

@dp.message(AddFrames.ruta)
async def frames_ruta(msg: Message, state: FSMContext):
    try:
        n = int(msg.text.strip())
    except:
        await msg.answer("Введи ціле число, наприклад: 100")
        return
    await state.update_data(ruta=n)
    await state.set_state(AddFrames.magazynna)
    await msg.answer("🟢 Скільки <b>Магазинна</b>? (0 якщо немає)", parse_mode="HTML")

@dp.message(AddFrames.magazynna)
async def frames_mag(msg: Message, state: FSMContext):
    try:
        n = int(msg.text.strip())
    except:
        await msg.answer("Введи ціле число, наприклад: 50")
        return
    await state.update_data(magazynna=n)
    data = await state.get_data()
    db   = load_db()
    w    = worker_by_id(db, data["wid"])
    p    = data["prices"]

    d_n, r_n, m_n = data["dadan"], data["ruta"], n
    total = d_n * p.get("dadan", 0) + r_n * p.get("ruta", 0) + m_n * p.get("magazynna", 0)

    parts = []
    if d_n: parts.append(f"Дадан {d_n} × {p.get('dadan')} = {fmt(d_n * p.get('dadan',0))} ₴")
    if r_n: parts.append(f"Рута {r_n} × {p.get('ruta')} = {fmt(r_n * p.get('ruta',0))} ₴")
    if m_n: parts.append(f"Маг. {m_n} × {p.get('magazynna')} = {fmt(m_n * p.get('magazynna',0))} ₴")

    if not parts:
        await msg.answer("Всі значення 0 — нічого не збережено.")
        await state.clear()
        return

    text = (f"👷 <b>{w['name']}</b>\n"
            f"📅 {fmt_date(today_str())}\n\n" +
            "\n".join(parts) +
            f"\n\n💰 <b>До нарахування: {fmt(total)} ₴</b>\n\nЗберегти?")

    await state.update_data(magazynna=n, total=total)
    await msg.answer(text, parse_mode="HTML",
                     reply_markup=confirm_kb("frames_save"))

@dp.callback_query(F.data == "frames_save")
async def frames_save(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    db   = load_db()
    p    = data["prices"]
    db["records"].append({
        "id": gen_id(), "date": today_str(), "type": "frames",
        "workerId": data["wid"],
        "dadan": data["dadan"], "ruta": data["ruta"], "magazynna": data["magazynna"],
        "pDadan": p.get("dadan", 0), "pRuta": p.get("ruta", 0), "pMag": p.get("magazynna", 0),
        "note": ""
    })
    save_db(db)
    await state.clear()
    w = worker_by_id(db, data["wid"])
    await cb.message.edit_text(
        f"✅ Збережено!\n👷 {w['name']} — нараховано <b>{fmt(data['total'])} ₴</b>",
        parse_mode="HTML"
    )

# ── Виплата ───────────────────────────────────────────────────────────────
@dp.message(F.text == "💰 Виплата")
async def payment_start(msg: Message, state: FSMContext):
    db = load_db()
    if not db["workers"]:
        await msg.answer("Виконавців немає.")
        return
    await state.set_state(AddPayment.worker)
    await msg.answer("👷 Кому виплата?",
                     reply_markup=workers_inline_kb(db["workers"], "pay"))

@dp.callback_query(AddPayment.worker, F.data.startswith("pay:"))
async def payment_worker(cb: CallbackQuery, state: FSMContext):
    wid = cb.data.split(":")[1]
    db  = load_db()
    w   = worker_by_id(db, wid)
    s   = w_stats(w, db["records"])
    await state.update_data(wid=wid)
    await state.set_state(AddPayment.amount)

    debt_line = ""
    if s["debt"] > 0:
        debt_line = f"\n🔴 Борг: <b>{fmt(s['debt'])} ₴</b>"
    elif s["debt"] < 0:
        debt_line = f"\n🟢 Переплата: <b>{fmt(abs(s['debt']))} ₴</b>"

    await cb.message.edit_text(
        f"👷 <b>{w['name']}</b>{debt_line}\n\nВведи суму виплати (₴):",
        parse_mode="HTML"
    )

@dp.message(AddPayment.amount)
async def payment_amount(msg: Message, state: FSMContext):
    try:
        amount = float(msg.text.strip().replace(",", "."))
        assert amount > 0
    except:
        await msg.answer("Введи суму, наприклад: 1500")
        return
    await state.update_data(amount=amount)
    data = await state.get_data()
    db   = load_db()
    w    = worker_by_id(db, data["wid"])
    await msg.answer(
        f"👷 <b>{w['name']}</b>\n💰 Виплата: <b>{fmt(amount)} ₴</b>\n\nЗберегти?",
        parse_mode="HTML",
        reply_markup=confirm_kb("pay_save")
    )

@dp.callback_query(F.data == "pay_save")
async def payment_save(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    db   = load_db()
    db["records"].append({
        "id": gen_id(), "date": today_str(), "type": "payment",
        "workerId": data["wid"], "amount": data["amount"], "reason": ""
    })
    save_db(db)
    await state.clear()
    w = worker_by_id(db, data["wid"])
    await cb.message.edit_text(
        f"✅ Виплату збережено!\n👷 {w['name']} — <b>{fmt(data['amount'])} ₴</b>",
        parse_mode="HTML"
    )

# ── Звіт ──────────────────────────────────────────────────────────────────
@dp.message(F.text == "📊 Звіт")
async def report(msg: Message):
    db     = load_db()
    stats  = [w_stats(w, db["records"]) for w in db["workers"]]
    # Last 7 days records
    recs   = sorted(db["records"], key=lambda r: r["date"], reverse=True)[:20]
    by_date = {}
    for r in recs:
        by_date.setdefault(r["date"], []).append(r)

    lines = ["<b>📊 Звіт по виконавцях:</b>", ""]
    for s in stats:
        emoji = "🔴" if s["debt"] > 0 else ("🟢" if s["debt"] < 0 else "🟡")
        lines.append(f"{emoji} <b>{s['name']}</b>: нарах. {fmt(s['earned'])} ₴ | випл. {fmt(s['paid'])} ₴")

    lines += ["", "<b>Останні записи:</b>"]
    for d in sorted(by_date.keys(), reverse=True):
        dr = by_date[d]
        frames_sum = sum(rec_earned(r) for r in dr if r["type"] == "frames")
        pay_sum    = sum(r.get("amount", 0) for r in dr if r["type"] == "payment")
        line = f"📅 {fmt_date(d)}"
        if frames_sum: line += f" | 🔨 {fmt(frames_sum)} ₴"
        if pay_sum:    line += f" | 💰 −{fmt(pay_sum)} ₴"
        lines.append(line)

    await msg.answer("\n".join(lines), parse_mode="HTML")

# ── Налаштування ──────────────────────────────────────────────────────────
@dp.message(F.text == "⚙️ Налаштування")
async def settings(msg: Message):
    db = load_db()
    dp_ = db.get("defaultPrices", {})
    await msg.answer(
        f"⚙️ <b>Налаштування</b>\n\n"
        f"Базові ціни:\n"
        f"🟠 Дадан: <b>{dp_.get('dadan', '?')} ₴</b>\n"
        f"🔵 Рута: <b>{dp_.get('ruta', '?')} ₴</b>\n"
        f"🟢 Магазинна: <b>{dp_.get('magazynna', '?')} ₴</b>\n\n"
        f"Виконавців: <b>{len(db['workers'])}</b>\n"
        f"Записів: <b>{len(db['records'])}</b>\n\n"
        f"Для детального управління — відкрийте додаток 👇",
        parse_mode="HTML",
        reply_markup=webapp_kb(WEBAPP_URL)
    )

# ── Cancel ────────────────────────────────────────────────────────────────
@dp.callback_query(F.data == "cancel")
async def cancel(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text("❌ Скасовано.")

# ── Run ───────────────────────────────────────────────────────────────────
async def main():
    logger.info("Starting Bees House Bot 🐝")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
