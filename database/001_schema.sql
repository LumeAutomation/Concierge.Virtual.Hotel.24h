-- PostgreSQL: base inicial para evolucao. O piloto Python usa SQLite.
-- Executar com uma conta de backend. Nao disponibilizar estas tabelas publicamente.
BEGIN;
CREATE TABLE IF NOT EXISTS hotels (
 id text PRIMARY KEY, name text NOT NULL, timezone text NOT NULL, is_demo boolean NOT NULL DEFAULT true
);
CREATE TABLE IF NOT EXISTS hotel_policies (
 hotel_id text NOT NULL REFERENCES hotels(id), id text NOT NULL, title text NOT NULL,
 content text NOT NULL, language text NOT NULL DEFAULT 'pt-BR', version integer NOT NULL,
 status text NOT NULL CHECK (status IN ('active','inactive')), PRIMARY KEY (hotel_id,id,version)
);
CREATE TABLE IF NOT EXISTS hotel_services (
 id text PRIMARY KEY, hotel_id text NOT NULL REFERENCES hotels(id), name text NOT NULL,
 details jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE TABLE IF NOT EXISTS hotel_restaurants (
 id text PRIMARY KEY, hotel_id text NOT NULL REFERENCES hotels(id), name text NOT NULL,
 details jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE TABLE IF NOT EXISTS hotel_knowledge (
 id text PRIMARY KEY, hotel_id text NOT NULL REFERENCES hotels(id),
 source text NOT NULL, content text NOT NULL, updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS guests (
 id text PRIMARY KEY, hotel_id text NOT NULL REFERENCES hotels(id),
 display_name text NOT NULL, UNIQUE (hotel_id,id)
);
CREATE TABLE IF NOT EXISTS reservations (
 id text PRIMARY KEY, hotel_id text NOT NULL REFERENCES hotels(id), guest_id text NOT NULL,
 external_reference text, status text NOT NULL, details jsonb NOT NULL DEFAULT '{}'::jsonb,
 FOREIGN KEY (hotel_id,guest_id) REFERENCES guests(hotel_id,id)
);
CREATE TABLE IF NOT EXISTS conversations (
 id text PRIMARY KEY, hotel_id text NOT NULL REFERENCES hotels(id), guest_id text,
 channel text NOT NULL CHECK(channel IN ('local_demo','whatsapp')),
 verified_at timestamptz, created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(hotel_id,id),
 FOREIGN KEY (hotel_id,guest_id) REFERENCES guests(hotel_id,id)
);
CREATE TABLE IF NOT EXISTS messages (
 id text PRIMARY KEY, conversation_id text NOT NULL REFERENCES conversations(id),
 external_message_id text UNIQUE, role text NOT NULL CHECK(role IN ('user','assistant','human')),
 content text NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS service_requests (
 id text PRIMARY KEY, hotel_id text NOT NULL REFERENCES hotels(id), conversation_id text NOT NULL,
 department text NOT NULL, status text NOT NULL DEFAULT 'open'
 CHECK(status IN ('open','in_progress','resolved','cancelled')),
 priority text NOT NULL CHECK(priority IN ('normal','urgent')),
 details jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY (hotel_id,conversation_id) REFERENCES conversations(hotel_id,id)
);
CREATE TABLE IF NOT EXISTS human_handoffs (
 id text PRIMARY KEY, conversation_id text NOT NULL REFERENCES conversations(id),
 message_id text NOT NULL UNIQUE REFERENCES messages(id), department text NOT NULL,
 reason text NOT NULL, priority text NOT NULL CHECK(priority IN ('normal','urgent')),
 status text NOT NULL DEFAULT 'open' CHECK(status IN ('open','in_progress','resolved')),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS handoffs_queue_idx ON human_handoffs(status,priority,created_at);
CREATE INDEX IF NOT EXISTS conversation_messages_idx ON messages(conversation_id,created_at);
-- RLS sem politicas publicas: acesso reservado ao proprietario/backend autorizado.
ALTER TABLE hotels ENABLE ROW LEVEL SECURITY;
ALTER TABLE hotel_policies ENABLE ROW LEVEL SECURITY;
ALTER TABLE hotel_services ENABLE ROW LEVEL SECURITY;
ALTER TABLE hotel_restaurants ENABLE ROW LEVEL SECURITY;
ALTER TABLE hotel_knowledge ENABLE ROW LEVEL SECURITY;
ALTER TABLE guests ENABLE ROW LEVEL SECURITY;
ALTER TABLE reservations ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE service_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE human_handoffs ENABLE ROW LEVEL SECURITY;
COMMIT;

