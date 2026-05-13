import os, json
from datetime import date
from fastapi import FastAPI, Form
from fastapi.responses import Response
import httpx

app = FastAPI()

GROQ_KEY     = os.getenv("GROQ_API_KEY", "")
GROQ_URL     = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL   = "llama-3.1-8b-instant"
SB_URL       = os.getenv("SUPABASE_URL", "")
SB_KEY       = os.getenv("SUPABASE_KEY", "")

# ── SUPABASE ───────────────────────────────────────────────────
async def sb(method, table, data=None, qs=""):
    headers = {
        "apikey": SB_KEY,
        "Authorization": f"Bearer {SB_KEY}",
        "Content-Type": "application/json",
    }
    if method == "POST":
        headers["Prefer"] = "return=representation,resolution=merge-duplicates"
    url = f"{SB_URL}/rest/v1/{table}{qs}"
    async with httpx.AsyncClient(timeout=10) as c:
        if method == "GET":
            r = await c.get(url, headers=headers)
        elif method == "POST":
            r = await c.post(url, headers=headers, json=data)
        elif method == "DELETE":
            r = await c.delete(url, headers=headers)
    try:
        return r.json()
    except Exception:
        return []

async def get_context(mes=None):
    if not mes:
        mes = date.today().strftime("%Y-%m")
    inicio = f"{mes}-01"
    trading = await sb("GET", "trading", qs=f"?fecha=gte.{inicio}&select=*&order=fecha.asc")
    gastos  = await sb("GET", "gastos_personales", qs=f"?fecha=gte.{inicio}&select=*&order=fecha.asc")
    if not isinstance(trading, list): trading = []
    if not isinstance(gastos,  list): gastos  = []

    g  = sum(e["monto"] for e in trading if e.get("tipo") == "ganancia")
    p  = sum(e["monto"] for e in trading if e.get("tipo") == "gasto")
    gp = sum(e["monto"] for e in gastos)

    ctx  = f"Mes: {mes}\n"
    ctx += f"Trading → ganancias: ${g:.2f} | pérdidas: ${p:.2f} | neto: ${g-p:.2f}\n"
    ctx += f"Gastos personales → total: ${gp:.2f}\n"
    if trading:
        ctx += "Detalle trading:\n"
        for e in trading:
            ctx += f"  {e['fecha']} {e['tipo']} ${e['monto']:.2f} {e.get('descripcion','')}\n"
    if gastos:
        ctx += "Gastos personales:\n"
        cats = {e['cat'] for e in gastos}
        for cat in ['fijo','variable','ocio','otro']:
            items = [e for e in gastos if e.get('cat') == cat]
            if items:
                ctx += f"  {cat.capitalize()}: ${sum(e['monto'] for e in items):.2f}\n"
                for e in items:
                    ctx += f"    {e['fecha']} ${e['monto']:.2f} {e.get('descripcion','')}\n"
    return ctx

async def ejecutar(nombre, args):
    hoy = date.today().isoformat()

    if nombre == "agregar_gasto_personal":
        row = {
            "cat":   args.get("cat", "otro"),
            "descripcion": args.get("desc", "—"),
            "monto": float(args.get("monto", 0)),
            "fecha": args.get("fecha", hoy),
            "nota":  args.get("nota", "") or "",
        }
        await sb("POST", "gastos_personales", row)
        labels = {"fijo":"Fijo","variable":"Variable","ocio":"Ocio","otro":"Otro"}
        return f"✅ *{row['desc']}* — ${row['monto']:.2f} ({labels.get(row['cat'], row['cat'])}, {row['fecha']})"

    if nombre == "agregar_trading":
        row = {
            "tipo":  args.get("tipo"),
            "descripcion": args.get("desc", "—"),
            "monto": float(args.get("monto", 0)),
            "fecha": args.get("fecha", hoy),
            "nota":  args.get("nota", "") or "",
        }
        await sb("POST", "trading", row)
        emoji = "📈" if row["tipo"] == "ganancia" else "📉"
        return f"{emoji} *{row['desc']}* — ${row['monto']:.2f} ({row['fecha']})"

    if nombre == "consultar_resumen":
        mes = args.get("mes", date.today().strftime("%Y-%m"))
        return await get_context(mes)

    return "❌ Herramienta no reconocida."

# ── HERRAMIENTAS ───────────────────────────────────────────────
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "agregar_gasto_personal",
            "description": "Añade un gasto personal (fijo, variable, ocio u otro)",
            "parameters": {
                "type": "object",
                "properties": {
                    "desc":  {"type": "string",  "description": "Descripción del gasto"},
                    "monto": {"type": "number",  "description": "Monto positivo"},
                    "cat":   {"type": "string",  "enum": ["fijo","variable","ocio","otro"]},
                    "fecha": {"type": "string",  "description": "Fecha YYYY-MM-DD, default hoy"},
                    "nota":  {"type": "string",  "description": "Nota opcional"}
                },
                "required": ["desc", "monto", "cat"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "agregar_trading",
            "description": "Añade una ganancia o pérdida de trading",
            "parameters": {
                "type": "object",
                "properties": {
                    "tipo":  {"type": "string", "enum": ["ganancia","gasto"]},
                    "desc":  {"type": "string", "description": "Descripción"},
                    "monto": {"type": "number", "description": "Monto positivo"},
                    "fecha": {"type": "string", "description": "Fecha YYYY-MM-DD, default hoy"},
                    "nota":  {"type": "string", "description": "Nota opcional"}
                },
                "required": ["tipo", "desc", "monto"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_resumen",
            "description": "Obtiene el resumen financiero de un mes",
            "parameters": {
                "type": "object",
                "properties": {
                    "mes": {"type": "string", "description": "Formato YYYY-MM, default mes actual"}
                }
            }
        }
    }
]

# ── WEBHOOK ────────────────────────────────────────────────────
@app.post("/webhook")
async def webhook(From: str = Form(default=""), Body: str = Form(default="")):
    mensaje = Body.strip()
    if not mensaje:
        return Response(content="<Response/>", media_type="application/xml")

    hoy = date.today().isoformat()
    ctx = await get_context()

    messages = [
        {
            "role": "system",
            "content": (
                f"Eres un asistente financiero personal. Hoy es {hoy}.\n\n"
                f"Datos actuales:\n{ctx}\n\n"
                "Si el usuario pide añadir algo, usa las herramientas disponibles. "
                "Para consultas, responde directamente. "
                "Sé muy conciso (máx 3 líneas, para WhatsApp). En español."
            )
        },
        {"role": "user", "content": mensaje}
    ]

    respuesta = "❌ Error al procesar."
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(
                GROQ_URL,
                headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
                json={"model": GROQ_MODEL, "messages": messages, "tools": TOOLS,
                      "tool_choice": "auto", "max_tokens": 400}
            )
        data   = r.json()
        choice = data["choices"][0]

        if choice.get("finish_reason") == "tool_calls":
            partes = []
            for tc in choice["message"]["tool_calls"]:
                args = json.loads(tc["function"]["arguments"])
                partes.append(await ejecutar(tc["function"]["name"], args))
            respuesta = "\n".join(partes)
        else:
            respuesta = choice["message"]["content"].strip()
    except Exception as e:
        respuesta = f"⚠️ Error: {e}"

    twiml = f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{respuesta}</Message></Response>'
    return Response(content=twiml, media_type="application/xml")

@app.get("/")
async def root():
    return {"status": "ok", "bot": "Trading Bot WhatsApp"}
