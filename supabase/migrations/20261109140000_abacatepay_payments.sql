ALTER TABLE public.payment
    ADD COLUMN IF NOT EXISTS provider_method varchar(10),
    ADD COLUMN IF NOT EXISTS provider_dev_mode boolean,
    ADD COLUMN IF NOT EXISTS provider_creation_started boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS provider_checked_at timestamptz,
    ADD COLUMN IF NOT EXISTS provider_checkout_details json;

CREATE UNIQUE INDEX IF NOT EXISTS ux_payment_abacatepay_session
    ON public.payment (provider_session_id)
    WHERE provider = 'abacatepay' AND provider_session_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_payment_abacatepay_reconcile
    ON public.payment (COALESCE(provider_checked_at, created_at), id)
    WHERE provider = 'abacatepay' AND status IN ('pending', 'disputed', 'refund_pending');
