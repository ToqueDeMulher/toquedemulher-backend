ALTER TABLE public.payment
    ADD COLUMN IF NOT EXISTS idempotency_key UUID;

CREATE UNIQUE INDEX IF NOT EXISTS ix_payment_idempotency_key
    ON public.payment (idempotency_key);

DO $$
BEGIN
    IF to_regclass('public.payment_item') IS NULL
       AND to_regclass('public.paymentitem') IS NOT NULL THEN
        ALTER TABLE public.paymentitem RENAME TO payment_item;
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS public.payment_item (
    id UUID NOT NULL PRIMARY KEY,
    product_id UUID NOT NULL REFERENCES public.product (id),
    payment_id UUID NOT NULL REFERENCES public.payment (id),
    title VARCHAR(255) NOT NULL,
    product_url VARCHAR(500) NOT NULL,
    unit_price NUMERIC(10, 2) NOT NULL,
    quantity INTEGER NOT NULL
);

DO $$
BEGIN
    IF to_regclass('public.paymentitem') IS NOT NULL THEN
        EXECUTE '
            INSERT INTO public.payment_item (
                id, product_id, payment_id, title, product_url, unit_price, quantity
            )
            SELECT
                id, product_id, payment_id, title, product_url, unit_price, quantity
            FROM public.paymentitem
            ON CONFLICT (id) DO NOTHING
        ';
    END IF;
END
$$;

CREATE INDEX IF NOT EXISTS ix_payment_item_id
    ON public.payment_item (id);

CREATE INDEX IF NOT EXISTS ix_payment_item_payment_id
    ON public.payment_item (payment_id);

CREATE INDEX IF NOT EXISTS ix_payment_item_product_id
    ON public.payment_item (product_id);

ALTER TABLE public.payment_item ENABLE ROW LEVEL SECURITY;
