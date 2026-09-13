-- Add data-integrity rules after checking existing rows.
-- Preserve customer data and archive the unused legacy table.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'public.cart_item'::regclass
          AND conname = 'ck_cart_item_quantity_positive'
    ) THEN
        ALTER TABLE public.cart_item
            ADD CONSTRAINT ck_cart_item_quantity_positive
            CHECK (quantity > 0) NOT VALID;
    END IF;
END
$$;
ALTER TABLE public.cart_item
    VALIDATE CONSTRAINT ck_cart_item_quantity_positive;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'public.cart_item'::regclass
          AND conname = 'ck_cart_item_unit_price_non_negative'
    ) THEN
        ALTER TABLE public.cart_item
            ADD CONSTRAINT ck_cart_item_unit_price_non_negative
            CHECK (unit_price_at_time >= 0) NOT VALID;
    END IF;
END
$$;
ALTER TABLE public.cart_item
    VALIDATE CONSTRAINT ck_cart_item_unit_price_non_negative;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'public.payment'::regclass
          AND conname = 'ck_payment_amount_non_negative'
    ) THEN
        ALTER TABLE public.payment
            ADD CONSTRAINT ck_payment_amount_non_negative
            CHECK (amount >= 0) NOT VALID;
    END IF;
END
$$;
ALTER TABLE public.payment
    VALIDATE CONSTRAINT ck_payment_amount_non_negative;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'public.supplier_product'::regclass
          AND conname = 'ck_supplier_product_lead_time_non_negative'
    ) THEN
        ALTER TABLE public.supplier_product
            ADD CONSTRAINT ck_supplier_product_lead_time_non_negative
            CHECK (lead_time_days IS NULL OR lead_time_days >= 0) NOT VALID;
    END IF;
END
$$;
ALTER TABLE public.supplier_product
    VALIDATE CONSTRAINT ck_supplier_product_lead_time_non_negative;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'public.supplier_product'::regclass
          AND conname = 'ck_supplier_product_price_non_negative'
    ) THEN
        ALTER TABLE public.supplier_product
            ADD CONSTRAINT ck_supplier_product_price_non_negative
            CHECK (supplier_price >= 0) NOT VALID;
    END IF;
END
$$;
ALTER TABLE public.supplier_product
    VALIDATE CONSTRAINT ck_supplier_product_price_non_negative;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'public.payment_item'::regclass
          AND conname = 'ck_payment_item_quantity_positive'
    ) THEN
        ALTER TABLE public.payment_item
            ADD CONSTRAINT ck_payment_item_quantity_positive
            CHECK (quantity > 0) NOT VALID;
    END IF;
END
$$;
ALTER TABLE public.payment_item
    VALIDATE CONSTRAINT ck_payment_item_quantity_positive;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'public.payment_item'::regclass
          AND conname = 'ck_payment_item_unit_price_non_negative'
    ) THEN
        ALTER TABLE public.payment_item
            ADD CONSTRAINT ck_payment_item_unit_price_non_negative
            CHECK (unit_price >= 0) NOT VALID;
    END IF;
END
$$;
ALTER TABLE public.payment_item
    VALIDATE CONSTRAINT ck_payment_item_unit_price_non_negative;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'public.stock_batch'::regclass
          AND conname = 'ck_stock_batch_quantity_non_negative'
    ) THEN
        ALTER TABLE public.stock_batch
            ADD CONSTRAINT ck_stock_batch_quantity_non_negative
            CHECK (quantity >= 0) NOT VALID;
    END IF;
END
$$;
ALTER TABLE public.stock_batch
    VALIDATE CONSTRAINT ck_stock_batch_quantity_non_negative;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'public.stock_batch'::regclass
          AND conname = 'ck_stock_batch_unit_cost_non_negative'
    ) THEN
        ALTER TABLE public.stock_batch
            ADD CONSTRAINT ck_stock_batch_unit_cost_non_negative
            CHECK (unit_cost >= 0) NOT VALID;
    END IF;
END
$$;
ALTER TABLE public.stock_batch
    VALIDATE CONSTRAINT ck_stock_batch_unit_cost_non_negative;

CREATE UNIQUE INDEX IF NOT EXISTS ix_address_single_default_shipping
    ON public.address (user_id) WHERE is_default_shipping;
CREATE UNIQUE INDEX IF NOT EXISTS ix_address_single_default_billing
    ON public.address (user_id) WHERE is_default_billing;

-- Remove only non-unique indexes that exactly duplicate a valid primary-key index.
DO $$
DECLARE
    redundant_name text;
BEGIN
    FOREACH redundant_name IN ARRAY ARRAY[
        'ix_cart_id', 'ix_payment_id', 'ix_payment_item_id', 'ix_product_id', 'ix_user_id'
    ] LOOP
        IF EXISTS (
            SELECT 1 FROM pg_index i
            JOIN pg_index p ON p.indrelid = i.indrelid AND p.indisprimary AND p.indisvalid
            JOIN pg_class idx ON idx.oid = i.indexrelid
            JOIN pg_namespace ns ON ns.oid = idx.relnamespace
            WHERE ns.nspname = 'public' AND idx.relname = redundant_name
              AND NOT i.indisprimary AND NOT i.indisunique AND i.indisvalid
              AND i.indkey = p.indkey AND i.indclass = p.indclass
              AND i.indcollation = p.indcollation AND i.indoption = p.indoption
              AND i.indpred IS NULL AND i.indexprs IS NULL
              AND NOT EXISTS (SELECT 1 FROM pg_constraint c WHERE c.conindid = i.indexrelid)
        ) THEN
            EXECUTE format('DROP INDEX public.%I', redundant_name);
        END IF;
    END LOOP;
END
$$;

-- Keep the old empty table for reference, outside the exposed application schema.
DO $$
BEGIN
    IF to_regclass('public.paymentitem') IS NOT NULL THEN
        LOCK TABLE public.paymentitem IN ACCESS EXCLUSIVE MODE;
        IF EXISTS (SELECT 1 FROM public.paymentitem) THEN
            RAISE EXCEPTION 'Legacy paymentitem contains data; archive requires review';
        END IF;
        IF EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE contype = 'f' AND confrelid = 'public.paymentitem'::regclass
        ) THEN
            RAISE EXCEPTION 'Legacy paymentitem has incoming foreign keys';
        END IF;
        IF EXISTS (
            SELECT 1 FROM pg_depend d JOIN pg_rewrite r ON r.oid = d.objid
            WHERE d.refobjid = 'public.paymentitem'::regclass
        ) THEN
            RAISE EXCEPTION 'Legacy paymentitem has view dependencies';
        END IF;
        IF to_regclass('tdm_archive.paymentitem') IS NOT NULL THEN
            RAISE EXCEPTION 'Archive target already exists';
        END IF;
        CREATE SCHEMA IF NOT EXISTS tdm_archive;
        REVOKE ALL ON SCHEMA tdm_archive FROM PUBLIC, anon, authenticated;
        ALTER TABLE public.paymentitem SET SCHEMA tdm_archive;
        REVOKE ALL ON TABLE tdm_archive.paymentitem FROM PUBLIC, anon, authenticated;
    END IF;
END
$$;
