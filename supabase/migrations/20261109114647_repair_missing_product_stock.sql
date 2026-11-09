-- Products added after the original backfill may still lack their stock row.
-- Zero is the backend's initial value; physical inventory is entered separately.
-- Preserve all existing balances, including concurrent inserts by the API.
INSERT INTO public.stock (id, product_id, total_quantity, updated_at)
SELECT gen_random_uuid(), product.id, 0, timezone('UTC', now())
FROM public.product
WHERE NOT EXISTS (
    SELECT 1 FROM public.stock WHERE stock.product_id = product.id
)
ON CONFLICT (product_id) DO NOTHING;
