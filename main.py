import os, json
from datetime import date
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import httpx

app = FastAPI()

GROQ_KEY  = os.getenv("GROQ_API_KEY", "")
GROQ_URL  = "https://api.groq.com/openai/v1/chat/completions"
GROQ_WSP  = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_MODEL= "llama-3.1-8b-instant"
SB_URL    = os.getenv("SUPABASE_URL", "")
SB_KEY    = os.getenv("SUPABASE_KEY", "")
TG_TOKEN  = os.getenv("TELEGRAM_TOKEN", "")
TG_URL    = f"https://api.telegram.org/bot{TG_TOKEN}"
TG_FILE   = f"https://api.telegram.org/file/bot{TG_TOKEN}"

async def tg_send(chat_id: int, texto: str):
    async with httpx.AsyncClient(timeout=10) as c:
        await c.post(f"{TG_URL}/sendMessage", json={
            "chat_id": chat_id, "text": texto, "parse_mode": "Markdown"
        })

async def tg_transcribir(file_id: str) -> str:
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(f"{TG_URL}/getFile", params={"file_id": file_id})
        file_path = r.json()["result"]["file_path"]
        audio = await c.get(f"{TG_FILE}/{file_path}")
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(
            GROQ_WSP,
            headers={"Authorization": f"Bearer {GROQ_KEY}"},
            files={"file": ("audio.ogg", audio.content, "audio/ogg")},
            data={"model": "whisper-large-v3-turbo", "language": "es", "response_format": "json"}
        )
    return r.json().get("text", "").strip()

async def sb(method, table, data=None, qs=""):
    headers = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": "application/json"}
    if method == "POST": headers["Prefer"] = "return=representation,resolution=merge-duplicates"
    url = f"{SB_URL}/rest/v1/{table}{qs}"
    async with httpx.AsyncClient(timeout=10) as c:
        if method == "GET":      r = await c.get(url, headers=headers)
        elif method == "POST":   r = await c.post(url, headers=headers, json=data)
        elif method == "DELETE": r = await c.delete(url, headers=headers)
    try: return r.json()
    except: return []

async def get_context(mes=None):
    if not mes: mes = date.today().strftime("%Y-%m")
    trading = await sb("GET", "trading", qs=f"?fecha=gte.{mes}-01&select=*&order=fecha.asc")
    gastos  = await sb("GET", "gastos_personales", qs=f"?fecha=gte.{mes}-01&select=*&order=fecha.asc")
    if not isinstance(trading, list): trading = []
    if not isinstance(gastos,  list): gastos  = []
    g = sum(e["monto"] for e in trading if e.get("tipo") == "ganancia")
    p = sum(e["monto"] for e in trading if e.get("tipo") == "gasto")
    ctx  = f"Mes: {mes}\nTrading → ganancias: ${g:.2f} | pérdidas: ${p:.2f} | neto: ${g-p:.2f}\n"
    ctx += f"Gastos personales → total: ${sum(e['monto'] for e in gastos):.2f}\n"
    for e in trading: ctx += f"  {e['fecha']} {e['tipo']} ${e['monto']:.2f} {e.get('descripcion','')}\n"
    for cat in ['fijo','variable','ocio','otro']:
        items = [e for e in gastos if e.get('cat') == cat]
        if items:
            ctx += f"  {cat}: ${sum(e['monto'] for e in items):.2f}\n"
            for e in items: ctx += f"    {e['fecha']} ${e['monto']:.2f} {e.get('descripcion','')}\n"
    return ctx

async def ejecutar(nombre, args):
    hoy = date.today().isoformat()
    if nombre == "agregar_gasto_personal":
        row = {"cat": args.get("cat","otro"), "descripcion": args.get("desc","—"),
               "monto": abs(float(args.get("monto", 0))),
               "fecha": args.get("fecha", hoy), "nota": args.get("nota","") or ""}
        await sb("POST", "gastos_personales", row)
        return f"✅ *{row['descripcion']}* — ${row['monto']:.2f} ({row['cat']}, {row['fecha']})"
    if nombre == "agregar_trading":
        row = {"tipo": args.get("tipo"), "descripcion": args.get("desc","—"),
               "monto": abs(float(args.get("monto", 0))),
               "fecha": args.get("fecha", hoy), "nota": args.get("nota","") or ""}
        await sb("POST", "trading", row)
        return f"{'📈' if row['tipo']=='ganancia' else '📉'} *{row['descripcion']}* — ${row['monto']:.2f} ({row['fecha']})"
    if nombre == "consultar_resumen":
        return await get_context(args.get("mes"))
    return "❌ Herramienta no reconocida."

TOOLS = [
    {"type":"function","function":{"name":"agregar_gasto_personal","description":"Añade un gasto personal","parameters":{"type":"object","properties":{"desc":{"type":"string"},"monto":{"type":"number"},"cat":{"type":"string","enum":["fijo","variable","ocio","otro"]},"fecha":{"type":"string"},"nota":{"type":"string"}},"required":["desc","monto","cat"]}}},
    {"type":"function","function":{"name":"agregar_trading","description":"Añade ganancia o pérdida de trading","parameters":{"type":"object","properties":{"tipo":{"type":"string","enum":["ganancia","gasto"]},"desc":{"type":"string"},"monto":{"type":"number"},"fecha":{"type":"string"},"nota":{"type":"string"}},"required":["tipo","desc","monto"]}}},
    {"type":"function","function":{"name":"consultar_resumen","description":"Resumen financiero del mes","parameters":{"type":"object","properties":{"mes":{"type":"string"}}}}}
]

async def procesar(chat_id: int, texto: str, desde_voz: bool = False):
    if texto == "/start":
        await tg_send(chat_id,
            "👋 *Trading Bot activo*\n\n"
            "*Puedes escribir o enviar notas de voz:*\n"
            "• `cena 25 ocio`\n"
            "• `alquiler 800 fijo`\n"
            "• `ganancia forex 200`\n"
            "• `pérdida comisión 15`\n"
            "• `resumen del mes`"
        )
        return
    ctx = await get_context()
    messages = [
        {"role":"system","content":(
            f"Eres un asistente financiero. Hoy: {date.today().isoformat()}.\n"
            f"Datos:\n{ctx}\n"
            "Si pide añadir algo usa herramientas. Montos SIEMPRE positivos. "
            "Sé conciso (máx 3 líneas). En español."
        )},
        {"role":"user","content":texto}
    ]
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(GROQ_URL,
            headers={"Authorization":f"Bearer {GROQ_KEY}","Content-Type":"application/json"},
            json={"model":GROQ_MODEL,"messages":messages,"tools":TOOLS,"tool_choice":"auto","max_tokens":400})
    choice = r.json()["choices"][0]
    if choice.get("finish_reason") == "tool_calls":
        partes = [await ejecutar(tc["function"]["name"], json.loads(tc["function"]["arguments"]))
                  for tc in choice["message"]["tool_calls"]]
        respuesta = "\n".join(partes)
        if desde_voz:
            respuesta = f"🎙️ _{texto}_\n\n{respuesta}"
    else:
        respuesta = choice["message"]["content"].strip()
    await tg_send(chat_id, respuesta)

@app.post("/telegram")
async def telegram_webhook(req: Request):
    try:
        data    = await req.json()
        message = data.get("message") or data.get("edited_message")
        if not message: return JSONResponse({"ok": True})
        chat_id = message["chat"]["id"]
        voice = message.get("voice") or message.get("audio")
        if voice:
            await tg_send(chat_id, "🎙️ Transcribiendo...")
            try:
                texto = await tg_transcribir(voice["file_id"])
                if texto:
                    await procesar(chat_id, texto, desde_voz=True)
                else:
                    await tg_send(chat_id, "⚠️ No entendí el audio. Intenta de nuevo.")
            except Exception as e:
                await tg_send(chat_id, f"⚠️ Error: {e}")
            return JSONResponse({"ok": True})
        texto = message.get("text", "").strip()
        if texto:
            await procesar(chat_id, texto)
    except Exception as e:
        print(f"Error: {e}")
    return JSONResponse({"ok": True})

@app.get("/")
async def root():
    return {"status": "ok", "bot": "Trading Bot Telegram + Voz"}
