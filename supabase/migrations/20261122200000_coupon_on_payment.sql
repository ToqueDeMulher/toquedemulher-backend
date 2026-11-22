-- Liga cupons ao pagamento (o pedido real do checkout). A tabela legada
-- ordercouponlink aponta para "order", que o checkout atual não usa.
ALTER TABLE public.payment
    ADD COLUMN IF NOT EXISTS coupon_id integer REFERENCES public.coupon (id),
    ADD COLUMN IF NOT EXISTS discount_amount numeric(10, 2) NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS ix_payment_coupon_id
    ON public.payment (coupon_id)
    WHERE coupon_id IS NOT NULL;

DO $$
BEGIN
    ALTER TABLE public.payment
        ADD CONSTRAINT ck_payment_discount_amount_non_negative
        CHECK (discount_amount >= 0);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE public.coupon
        ADD CONSTRAINT ck_coupon_discount_type
        CHECK (discount_type IN ('percent', 'fixed'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE public.coupon
        ADD CONSTRAINT ck_coupon_percent_at_most_100
        CHECK (discount_type <> 'percent' OR discount_value <= 100);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
