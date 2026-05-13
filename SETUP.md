# Setup WhatsApp Bot — 100% Gratis

## Paso 1 — Supabase (base de datos gratis)

1. Ve a https://supabase.com y crea una cuenta gratis
2. Crea un proyecto nuevo (cualquier nombre, ej: "trading-bot")
3. Ve a **SQL Editor** y pega el contenido de `supabase_schema.sql` → Run
4. Ve a **Project Settings → API** y copia:
   - `Project URL`  → lo necesitas luego
   - `anon public`  → lo necesitas luego


## Paso 2 — Render.com (servidor gratis)

1. Ve a https://render.com y crea una cuenta gratis con GitHub
2. Sube la carpeta `bot/` a un repositorio de GitHub (puede ser privado)
3. En Render: **New → Web Service** → conecta tu repo
4. Configura:
   - **Name**: trading-bot
   - **Root Directory**: bot
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type**: Free
5. En **Environment Variables** añade estas 3:
   - `GROQ_API_KEY` = `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`
   - `SUPABASE_URL` = `https://vsyrsydfcvpubxausjnn.supabase.co`
   - `SUPABASE_KEY` = `sb_secret_HrY8xrvSdQCFtKTuImwm-Q_pWUju182`
6. Haz clic en **Deploy** → espera ~2 minutos
7. Copia la URL del servicio (ej: `https://trading-bot-xxxx.onrender.com`)


## Paso 3 — Twilio WhatsApp Sandbox (gratis)

1. Ve a https://twilio.com y crea una cuenta gratis
2. En el dashboard: **Messaging → Try it out → Send a WhatsApp message**
3. Sigue las instrucciones para unirte al sandbox:
   - Envía el código que te dan por WhatsApp al número de Twilio
4. Ve a **Sandbox Settings** y en **"When a message comes in"** pega:
   ```
   https://trading-bot-xxxx.onrender.com/webhook
   ```
   (usa tu URL de Render del paso 2)
5. Método: **HTTP POST** → Guardar


## Paso 4 — Conectar la app web

1. Abre `trading.html` en el navegador
2. Haz clic en ⚙️ arriba a la derecha
3. Rellena:
   - **Supabase URL**: la del paso 1
   - **Supabase Anon Key**: la del paso 1
4. Guarda → haz clic en **🔄 Sincronizar**

¡Listo! Ahora los datos se comparten entre la web y WhatsApp.


## Uso desde WhatsApp

Envía mensajes al número de Twilio sandbox:

| Mensaje | Resultado |
|---------|-----------|
| `añade cena 25 ocio` | Añade gasto personal |
| `alquiler 800 fijo` | Añade gasto fijo |
| `ganancia forex 200` | Añade ganancia trading |
| `pérdida comisión 15` | Añade pérdida trading |
| `resumen del mes` | Muestra resumen |
| `¿cómo voy este mes?` | Análisis de tu situación |


## Notas

- Render free tier puede tardar ~30s en arrancar si lleva inactivo
- Twilio sandbox requiere re-confirmar el número cada 72h (solo para sandbox)
- Para uso permanente sin límites: WhatsApp Business API (Meta) — proceso más largo
