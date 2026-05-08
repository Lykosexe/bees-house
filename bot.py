"""
Bees House 🐝 — Telegram Bot + HTTP API
"""
import os, json, logging, asyncio
from datetime import date, datetime
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    WebAppInfo, KeyboardButton, ReplyKeyboardMarkup,
    BufferedInputFile
)
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN  = os.getenv("BOT_TOKEN", "")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://lykosexe.github.io/bees-house")
DB_CHANNEL = int(os.getenv("DB_CHANNEL", "0"))
PORT       = int(os.getenv("PORT", "8080"))
DB_PATH    = os.path.join(os.path.dirname(__file__), "../data/db.json")

bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher(storage=MemoryStorage())

_db_cache      = None
_db_message_id = None

def _default_db():
    return {"defaultPrices": {"dadan": 4.5, "ruta": 3.5, "magazynna": 3.0},
            "workers": [], "records": []}

def load_db_local():
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return _default_db()

def save_db_local(db):
    try:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        with open(DB_PATH, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Local save error: {e}")

async def load_db():
    global _db_cache, _db_message_id
    if not DB_CHANNEL:
        _db_cache = load_db_local()
        return _db_cache
    try:
        import aiohttp
        chat = await bot.get_chat(DB_CHANNEL)
        if chat.pinned_message and chat.pinned_message.document:
            msg = chat.pinned_message
            _db_message_id = msg.message_id
            file = await bot.get_file(msg.document.file_id)
            url  = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file.file_path}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    content = await resp.text()
                    _db_cache = json.loads(content)
                    logger.info(f"✅ DB loaded from Telegram: {len(_db_cache.get('workers',[]))} workers")
                    return _db_cache
    except Exception as e:
        logger.warning(f"Telegram load failed: {e}, using local")
    _db_cache = load_db_local()
    return _db_cache

async def save_db(db):
    global _db_cache, _db_message_id
    _db_cache = db
    save_db_local(db)
    if not DB_CHANNEL:
        return
    try:
        json_bytes = json.dumps(db, ensure_ascii=False, indent=2).encode("utf-8")
        doc = BufferedInputFile(json_bytes, filename="db.json")
        msg = await bot.send_document(
            DB_CHANNEL, doc,
            caption=f"🐝 {datetime.now().strftime('%d.%m.%Y %H:%M')} | "
                    f"{len(db.get('workers',[]))} виконавців | {len(db.get('records',[]))} записів"
        )
        await bot.pin_chat_message(DB_CHANNEL, msg.message_id, disable_notification=True)
        if _db_message_id and _db_message_id != msg.message_id:
            try: await bot.delete_message(DB_CHANNEL, _db_message_id)
            except: pass
        _db_message_id = msg.message_id
        logger.info("✅ DB saved to Telegram")
    except Exception as e:
        logger.error(f"Telegram save error: {e}")

def get_db():
    return _db_cache or load_db_local()

# ── HTTP API ──────────────────────────────────────────────────────────────
async def handle_get_db(request):
    """GET /db — віддає поточну БД для Mini App"""
    db = get_db()
    return web.Response(
        text=json.dumps(db, ensure_ascii=False),
        content_type="application/json",
        headers={"Access-Control-Allow-Origin": "*"}
    )

async def handle_save_db(request):
    """POST /db — зберігає БД від Mini App"""
    try:
        data = await request.json()
        if not data.get("workers") is None and not data.get("records") is None:
            await save_db(data)
            return web.Response(text='{"ok":true}', content_type="application/json",
                                headers={"Access-Control-Allow-Origin": "*"})
    except Exception as e:
        logger.error(f"Save via API error: {e}")
    return web.Response(status=400, text='{"ok":false}', content_type="application/json",
                        headers={"Access-Control-Allow-Origin": "*"})

async def handle_options(request):
    """OPTIONS — для CORS preflight"""
    return web.Response(headers={
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    })

async def handle_health(request):
    return web.Response(text="🐝 Bees House Bot is running!")

# ── Helpers ───────────────────────────────────────────────────────────────
def gen_id():
    import random, string, time
    return ''.join(random.choices(string.ascii_lowercase+string.digits, k=8))+hex(int(time.time()*1000))[2:]

def today_str():    return date.today().isoformat()
def fmt_date(iso):
    try: return datetime.strptime(iso, "%Y-%m-%d").strftime("%d.%m.%Y")
    except: return iso

def fmt(n):
    n = round(float(n or 0), 2)
    return f"{int(n):,}".replace(",","\u00a0") if n==int(n) else f"{n:,.2f}".replace(",","\u00a0")

def rec_earned(r):
    return (r.get("dadan",0)*r.get("pDadan",0)+r.get("ruta",0)*r.get("pRuta",0)+
            r.get("magazynna",0)*(r.get("pMag") or r.get("pMagazynna",0)))

def w_stats(w, records):
    recs=[ r for r in records if r["workerId"]==w["id"]]
    earned=sum(rec_earned(r) for r in recs if r["type"]=="frames")
    paid=sum(r.get("amount",0) for r in recs if r["type"]=="payment")
    frames=sum(r.get("dadan",0)+r.get("ruta",0)+r.get("magazynna",0) for r in recs if r["type"]=="frames")
    return {**w,"earned":earned,"paid":paid,"debt":earned-paid,"frames":frames}

def worker_by_id(db, wid):
    return next((w for w in db["workers"] if w["id"]==wid), None)

# ── FSM ───────────────────────────────────────────────────────────────────
class AddFrames(StatesGroup):
    worker=State(); dadan=State(); ruta=State(); magazynna=State()

class AddPayment(StatesGroup):
    worker=State(); amount=State()

# ── Keyboards ─────────────────────────────────────────────────────────────
def main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🏠 Головна"),  KeyboardButton(text="👷 Виконавці")],
        [KeyboardButton(text="🔨 Рамки"),    KeyboardButton(text="💰 Виплата")],
        [KeyboardButton(text="📊 Звіт"),     KeyboardButton(text="⚙️ Налаштування")],
    ], resize_keyboard=True)

def webapp_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📱 Відкрити додаток", web_app=WebAppInfo(url=WEBAPP_URL))
    ]])

def workers_kb(workers, prefix):
    rows=[[InlineKeyboardButton(text=w["name"],callback_data=f"{prefix}:{w['id']}")] for w in workers]
    rows.append([InlineKeyboardButton(text="❌ Скасувати",callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def confirm_kb(yes_data):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Так",callback_data=yes_data),
        InlineKeyboardButton(text="❌ Ні", callback_data="cancel"),
    ]])

# ── Handlers ──────────────────────────────────────────────────────────────
@dp.message(CommandStart())
async def cmd_start(msg: Message):
    await msg.answer("🐝 <b>Bees House</b> — облік виробництва", parse_mode="HTML", reply_markup=main_kb())
    await msg.answer("📱 Повний додаток:", reply_markup=webapp_kb())

@dp.message(F.text == "🏠 Головна")
async def home(msg: Message):
    db=get_db(); stats=[w_stats(w,db["records"]) for w in db["workers"]]
    tF=sum(s["frames"] for s in stats); tD=sum(s["debt"] for s in stats); tP=sum(s["paid"] for s in stats)
    sign="📉 Борг" if tD>0 else ("📈 Переплата" if tD<0 else "✅ Розраховано")
    lines=[f"🐝 <b>Bees House</b> — {datetime.now().strftime('%d.%m.%Y')}",
           f"🔨 Рамок: <b>{tF}</b> | {sign}: <b>{fmt(abs(tD))} ₴</b>","","<b>Виконавці:</b>"]
    for s in stats:
        d=f"борг {fmt(s['debt'])} ₴" if s['debt']>0 else (f"переплата {fmt(abs(s['debt']))} ₴" if s['debt']<0 else "✓")
        lines.append(f"• {s['name']} — {s['frames']} рам. | {d}")
    await msg.answer("\n".join(lines), parse_mode="HTML")

@dp.message(F.text == "👷 Виконавці")
async def workers_list(msg: Message):
    db=get_db(); stats=[w_stats(w,db["records"]) for w in db["workers"]]
    if not stats:
        await msg.answer("Виконавців немає. Додайте через додаток 📱", reply_markup=webapp_kb()); return
    lines=["<b>👷 Виконавці:</b>"]
    for s in stats:
        d=f"🔴 Борг {fmt(s['debt'])} ₴" if s['debt']>0 else (f"🟢 Переплата {fmt(abs(s['debt']))} ₴" if s['debt']<0 else "🟡 Розраховано")
        lines.append(f"\n<b>{s['name']}</b> — {s['frames']} рам. | {fmt(s['earned'])} ₴\n  {d}")
    await msg.answer("\n".join(lines), parse_mode="HTML")

@dp.message(F.text == "🔨 Рамки")
async def frames_start(msg: Message, state: FSMContext):
    db=get_db()
    if not db["workers"]:
        await msg.answer("Додайте виконавця через додаток 📱", reply_markup=webapp_kb()); return
    await state.set_state(AddFrames.worker)
    await msg.answer("👷 Вибери виконавця:", reply_markup=workers_kb(db["workers"],"frames"))

@dp.callback_query(AddFrames.worker, F.data.startswith("frames:"))
async def frames_worker(cb: CallbackQuery, state: FSMContext):
    wid=cb.data.split(":")[1]; db=get_db(); w=worker_by_id(db,wid)
    await state.update_data(wid=wid,prices=w["prices"])
    await state.set_state(AddFrames.dadan)
    await cb.message.edit_text(f"👷 <b>{w['name']}</b>\n\n🟠 Скільки <b>Дадан</b>? (0 якщо немає)", parse_mode="HTML")

@dp.message(AddFrames.dadan)
async def frames_dadan(msg: Message, state: FSMContext):
    try: n=int(msg.text.strip())
    except: await msg.answer("Введи число, наприклад: 150"); return
    await state.update_data(dadan=n); await state.set_state(AddFrames.ruta)
    await msg.answer("🔵 Скільки <b>Рута</b>? (0 якщо немає)", parse_mode="HTML")

@dp.message(AddFrames.ruta)
async def frames_ruta(msg: Message, state: FSMContext):
    try: n=int(msg.text.strip())
    except: await msg.answer("Введи число, наприклад: 100"); return
    await state.update_data(ruta=n); await state.set_state(AddFrames.magazynna)
    await msg.answer("🟢 Скільки <b>Магазинна</b>? (0 якщо немає)", parse_mode="HTML")

@dp.message(AddFrames.magazynna)
async def frames_mag(msg: Message, state: FSMContext):
    try: n=int(msg.text.strip())
    except: await msg.answer("Введи число, наприклад: 50"); return
    await state.update_data(magazynna=n)
    data=await state.get_data(); db=get_db(); w=worker_by_id(db,data["wid"]); p=data["prices"]
    d_n,r_n,m_n=data["dadan"],data["ruta"],n
    total=d_n*p.get("dadan",0)+r_n*p.get("ruta",0)+m_n*p.get("magazynna",0)
    parts=[]
    if d_n: parts.append(f"Дадан {d_n} × {p.get('dadan')} = {fmt(d_n*p.get('dadan',0))} ₴")
    if r_n: parts.append(f"Рута {r_n} × {p.get('ruta')} = {fmt(r_n*p.get('ruta',0))} ₴")
    if m_n: parts.append(f"Маг. {m_n} × {p.get('magazynna')} = {fmt(m_n*p.get('magazynna',0))} ₴")
    if not parts:
        await msg.answer("Всі 0 — нічого не збережено."); await state.clear(); return
    await state.update_data(magazynna=n,total=total)
    await msg.answer(f"👷 <b>{w['name']}</b>\n📅 {fmt_date(today_str())}\n\n"+"\n".join(parts)+
                     f"\n\n💰 <b>{fmt(total)} ₴</b>\n\nЗберегти?",
                     parse_mode="HTML", reply_markup=confirm_kb("frames_save"))

@dp.callback_query(F.data == "frames_save")
async def frames_save(cb: CallbackQuery, state: FSMContext):
    data=await state.get_data(); db=get_db(); p=data["prices"]
    db["records"].append({"id":gen_id(),"date":today_str(),"type":"frames","workerId":data["wid"],
        "dadan":data["dadan"],"ruta":data["ruta"],"magazynna":data["magazynna"],
        "pDadan":p.get("dadan",0),"pRuta":p.get("ruta",0),"pMag":p.get("magazynna",0),"note":""})
    await save_db(db); await state.clear()
    w=worker_by_id(db,data["wid"])
    await cb.message.edit_text(f"✅ Збережено! {w['name']} — <b>{fmt(data['total'])} ₴</b>", parse_mode="HTML")

@dp.message(F.text == "💰 Виплата")
async def payment_start(msg: Message, state: FSMContext):
    db=get_db()
    if not db["workers"]: await msg.answer("Виконавців немає."); return
    await state.set_state(AddPayment.worker)
    await msg.answer("👷 Кому виплата?", reply_markup=workers_kb(db["workers"],"pay"))

@dp.callback_query(AddPayment.worker, F.data.startswith("pay:"))
async def payment_worker(cb: CallbackQuery, state: FSMContext):
    wid=cb.data.split(":")[1]; db=get_db(); w=worker_by_id(db,wid); s=w_stats(w,db["records"])
    await state.update_data(wid=wid); await state.set_state(AddPayment.amount)
    dl=f"\n🔴 Борг: <b>{fmt(s['debt'])} ₴</b>" if s['debt']>0 else (f"\n🟢 Переплата: <b>{fmt(abs(s['debt']))} ₴</b>" if s['debt']<0 else "")
    await cb.message.edit_text(f"👷 <b>{w['name']}</b>{dl}\n\nВведи суму (₴):", parse_mode="HTML")

@dp.message(AddPayment.amount)
async def payment_amount(msg: Message, state: FSMContext):
    try: amount=float(msg.text.strip().replace(",",".")); assert amount>0
    except: await msg.answer("Введи суму, наприклад: 1500"); return
    await state.update_data(amount=amount)
    data=await state.get_data(); w=worker_by_id(get_db(),data["wid"])
    await msg.answer(f"👷 <b>{w['name']}</b>\n💰 <b>{fmt(amount)} ₴</b>\n\nЗберегти?",
                     parse_mode="HTML", reply_markup=confirm_kb("pay_save"))

@dp.callback_query(F.data == "pay_save")
async def payment_save(cb: CallbackQuery, state: FSMContext):
    data=await state.get_data(); db=get_db()
    db["records"].append({"id":gen_id(),"date":today_str(),"type":"payment",
                          "workerId":data["wid"],"amount":data["amount"],"reason":""})
    await save_db(db); await state.clear()
    w=worker_by_id(db,data["wid"])
    await cb.message.edit_text(f"✅ Виплату збережено! {w['name']} — <b>{fmt(data['amount'])} ₴</b>", parse_mode="HTML")

@dp.message(F.text == "📊 Звіт")
async def report(msg: Message):
    db=get_db(); stats=[w_stats(w,db["records"]) for w in db["workers"]]
    lines=["<b>📊 Звіт:</b>"]
    for s in stats:
        e="🔴" if s['debt']>0 else ("🟢" if s['debt']<0 else "🟡")
        lines.append(f"{e} <b>{s['name']}</b>: {fmt(s['earned'])} ₴ нарах. | {fmt(s['paid'])} ₴ випл. | {fmt(abs(s['debt']))} ₴ {'борг' if s['debt']>0 else 'переплата' if s['debt']<0 else '✓'}")
    await msg.answer("\n".join(lines), parse_mode="HTML")

@dp.message(F.text == "⚙️ Налаштування")
async def settings(msg: Message):
    db=get_db(); dp_=db.get("defaultPrices",{})
    await msg.answer(f"⚙️ <b>Налаштування</b>\n\nЦіни: Дадан <b>{dp_.get('dadan','?')} ₴</b> | Рута <b>{dp_.get('ruta','?')} ₴</b> | Маг. <b>{dp_.get('magazynna','?')} ₴</b>\n\nВиконавців: <b>{len(db['workers'])}</b> | Записів: <b>{len(db['records'])}</b>",
                     parse_mode="HTML", reply_markup=webapp_kb())

@dp.callback_query(F.data == "cancel")
async def cancel(cb: CallbackQuery, state: FSMContext):
    await state.clear(); await cb.message.edit_text("❌ Скасовано.")

# ── Main ──────────────────────────────────────────────────────────────────
async def main():
    logger.info("🐝 Starting Bees House Bot")
    await load_db()
    db=get_db()
    logger.info(f"DB: {len(db.get('workers',[]))} workers, {len(db.get('records',[]))} records")

    # HTTP сервер для Mini App
    app = web.Application()
    app.router.add_get("/", handle_health)
    app.router.add_get("/db", handle_get_db)
    app.router.add_post("/db", handle_save_db)
    app.router.add_route("OPTIONS", "/db", handle_options)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"✅ HTTP API started on port {PORT}")

    # Telegram бот
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
