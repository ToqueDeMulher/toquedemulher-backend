-- Run through the project's migration workflow before restarting the backend.
ALTER TABLE public.product
    ADD COLUMN IF NOT EXISTS shipping_width double precision CHECK (shipping_width > 0),
    ADD COLUMN IF NOT EXISTS shipping_height double precision CHECK (shipping_height > 0),
    ADD COLUMN IF NOT EXISTS shipping_length double precision CHECK (shipping_length > 0),
    ADD COLUMN IF NOT EXISTS shipping_weight double precision CHECK (shipping_weight > 0);

CREATE TABLE IF NOT EXISTS public.shipping_connection (
    environment varchar(16) PRIMARY KEY CHECK (environment IN ('sandbox', 'production')),
    access_ciphertext text,
    refresh_ciphertext text,
    expires_at timestamptz,
    state_digest text,
    state_expires_at timestamptz
);
CREATE TABLE IF NOT EXISTS public.shipping_quote (
    id uuid PRIMARY KEY,
    environment varchar(16) NOT NULL CHECK (environment IN ('sandbox', 'production')),
    origin_postal_code varchar(8) NOT NULL,
    postal_code varchar(8) NOT NULL,
    items json NOT NULL,
    services json NOT NULL,
    subtotal numeric(10,2) NOT NULL CHECK (subtotal >= 0),
    expires_at timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_shipping_quote_expires_at ON public.shipping_quote(expires_at);
CREATE TABLE IF NOT EXISTS public.shipment (
    id uuid PRIMARY KEY,
    payment_id uuid NOT NULL UNIQUE REFERENCES public.payment(id),
    quote_id uuid NOT NULL REFERENCES public.shipping_quote(id),
    service_id integer NOT NULL,
    service_name text NOT NULL,
    company_name text NOT NULL,
    cost numeric(10,2) NOT NULL CHECK (cost >= 0),
    customer_price numeric(10,2) NOT NULL CHECK (customer_price >= 0),
    delivery_min integer NOT NULL,
    delivery_max integer NOT NULL,
    status varchar(32) NOT NULL DEFAULT 'pending',
    recipient json NOT NULL,
    sender json NOT NULL,
    labels json NOT NULL DEFAULT '[]',
    invoice_key varchar(44),
    print_url text,
    last_error text,
    updated_at timestamptz NOT NULL DEFAULT now()
);
-- Backend-only tables: deny access through Supabase REST, even when default
-- privileges expose new public tables. Backend SQL sessions enforce ownership.
ALTER TABLE public.shipping_connection ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.shipping_quote ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.shipment ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.shipping_connection, public.shipping_quote, public.shipment
    FROM PUBLIC, anon, authenticated, service_role;
