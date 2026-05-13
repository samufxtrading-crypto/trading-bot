-- Ejecuta esto en Supabase → SQL Editor

CREATE TABLE IF NOT EXISTS trading (
  id          BIGSERIAL PRIMARY KEY,
  client_id   BIGINT,
  tipo        TEXT NOT NULL CHECK (tipo IN ('ganancia','gasto')),
  descripcion TEXT,
  monto       DECIMAL(10,2) NOT NULL,
  fecha       TEXT NOT NULL,
  nota        TEXT DEFAULT '',
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS gastos_personales (
  id          BIGSERIAL PRIMARY KEY,
  client_id   BIGINT,
  cat         TEXT NOT NULL CHECK (cat IN ('fijo','variable','ocio','otro')),
  descripcion TEXT,
  monto       DECIMAL(10,2) NOT NULL,
  fecha       TEXT NOT NULL,
  nota        TEXT DEFAULT '',
  created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Acceso público de lectura/escritura (anon key)
ALTER TABLE trading            ENABLE ROW LEVEL SECURITY;
ALTER TABLE gastos_personales  ENABLE ROW LEVEL SECURITY;

CREATE POLICY "allow_all_trading"   ON trading           FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "allow_all_gp"        ON gastos_personales FOR ALL USING (true) WITH CHECK (true);
