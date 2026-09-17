-- Restore checks missing from an already-provisioned payment-method table.
-- Existing rows are validated without modifying or deleting customer data.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'public.user_payment_method'::regclass
          AND conname = 'ck_user_payment_method_card_last4'
    ) THEN
        ALTER TABLE public.user_payment_method
            ADD CONSTRAINT ck_user_payment_method_card_last4
            CHECK (card_last4 IS NULL OR length(card_last4) = 4) NOT VALID;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'public.user_payment_method'::regclass
          AND conname = 'ck_user_payment_method_card_required_fields'
    ) THEN
        ALTER TABLE public.user_payment_method
            ADD CONSTRAINT ck_user_payment_method_card_required_fields
            CHECK (
                method_type <> 'card'
                OR (
                    holder_name IS NOT NULL
                    AND card_last4 IS NOT NULL
                    AND card_exp_month IS NOT NULL
                    AND card_exp_year IS NOT NULL
                )
            ) NOT VALID;
    END IF;
END
$$;

ALTER TABLE public.user_payment_method
    VALIDATE CONSTRAINT ck_user_payment_method_card_last4;
ALTER TABLE public.user_payment_method
    VALIDATE CONSTRAINT ck_user_payment_method_card_required_fields;

-- The backend returns public product-image URLs and permits JPG, PNG and WebP.
-- Only create a missing bucket; preserve any existing bucket configuration.
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'product-images',
    'product-images',
    true,
    5242880,
    ARRAY['image/jpeg', 'image/png', 'image/webp']
)
ON CONFLICT (id) DO NOTHING;
