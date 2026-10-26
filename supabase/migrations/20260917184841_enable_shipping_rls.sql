-- These backend-only tables were created on the hosted database before their
-- migration was recorded. Its three RLS statements were never applied there.
-- The FastAPI backend connects as postgres, which has BYPASSRLS. Supabase
-- Data API roles have no policies for these tables and must not read them.
ALTER TABLE IF EXISTS public.shipping_connection ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.shipping_quote ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.shipment ENABLE ROW LEVEL SECURITY;
