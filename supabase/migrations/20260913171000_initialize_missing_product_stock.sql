-- Initialize missing stock using the backend model's default quantity.
-- Existing stock balances remain unchanged; actual inventory is entered separately.
INSERT INTO public.stock (id, product_id, total_quantity, updated_at)
SELECT gen_random_uuid(), product.id, 0, timezone('UTC', now())
FROM public.product
WHERE NOT EXISTS (
    SELECT 1 FROM public.stock WHERE stock.product_id = product.id
)
ON CONFLICT (product_id) DO NOTHING;
