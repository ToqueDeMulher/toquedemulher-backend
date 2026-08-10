-- Generated from SQLModel metadata for the backend application tables.
-- Idempotent because the remote Supabase database was provisioned once before this migration was recorded.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE n.nspname = 'public'
          AND t.typname = 'stockmovementtype'
    ) THEN
        CREATE TYPE public.stockmovementtype AS ENUM ('IN', 'OUT', 'ADJUSTMENT', 'RETURN');
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS brand (
	id SERIAL NOT NULL,
	name VARCHAR NOT NULL,
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS category (
	id SERIAL NOT NULL,
	name VARCHAR NOT NULL,
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS coupon (
	id SERIAL NOT NULL,
	code VARCHAR NOT NULL,
	description VARCHAR,
	discount_type VARCHAR NOT NULL,
	discount_value FLOAT NOT NULL,
	valid_from TIMESTAMP WITHOUT TIME ZONE,
	valid_to TIMESTAMP WITHOUT TIME ZONE,
	max_uses_global INTEGER,
	max_uses_per_user INTEGER,
	active BOOLEAN NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_coupon_discount_value_non_negative CHECK (discount_value >= 0)
);

CREATE TABLE IF NOT EXISTS description (
	id SERIAL NOT NULL,
	text VARCHAR NOT NULL,
	usage_tips VARCHAR,
	ingredients VARCHAR,
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS payment_method (
	id SERIAL NOT NULL,
	type_name VARCHAR NOT NULL,
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS supplier (
	id SERIAL NOT NULL,
	name VARCHAR NOT NULL,
	contact VARCHAR,
	email VARCHAR,
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS "user" (
	id UUID NOT NULL,
	name VARCHAR NOT NULL,
	cpf VARCHAR,
	email VARCHAR NOT NULL,
	hashed_password VARCHAR NOT NULL,
	phone VARCHAR,
	gender VARCHAR,
	birth_date DATE,
	accepts_marketing BOOLEAN NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	deleted_at TIMESTAMP WITHOUT TIME ZONE,
	disabled BOOLEAN NOT NULL,
	role VARCHAR NOT NULL,
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS address (
	id UUID NOT NULL,
	user_id UUID NOT NULL,
	label VARCHAR,
	cep VARCHAR NOT NULL,
	street VARCHAR NOT NULL,
	number VARCHAR,
	complement VARCHAR,
	neighborhood VARCHAR,
	city VARCHAR NOT NULL,
	state VARCHAR NOT NULL,
	region VARCHAR,
	ddd VARCHAR,
	is_default_shipping BOOLEAN NOT NULL,
	is_default_billing BOOLEAN NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES "user" (id)
);

CREATE TABLE IF NOT EXISTS cart (
	id UUID NOT NULL,
	user_id UUID NOT NULL,
	status VARCHAR NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES "user" (id)
);

CREATE TABLE IF NOT EXISTS product (
	id UUID NOT NULL,
	slug VARCHAR NOT NULL,
	name VARCHAR NOT NULL,
	price FLOAT NOT NULL,
	active BOOLEAN NOT NULL,
	volume VARCHAR,
	target_audience VARCHAR,
	product_type VARCHAR,
	skin_type VARCHAR,
	hair_type VARCHAR,
	color VARCHAR,
	fragrance VARCHAR,
	spf INTEGER,
	vegan BOOLEAN NOT NULL,
	cruelty_free BOOLEAN NOT NULL,
	hypoallergenic BOOLEAN NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	brand_id INTEGER,
	description_id INTEGER,
	PRIMARY KEY (id),
	CONSTRAINT ck_product_price_non_negative CHECK (price >= 0),
	FOREIGN KEY(brand_id) REFERENCES brand (id),
	FOREIGN KEY(description_id) REFERENCES description (id)
);

CREATE TABLE IF NOT EXISTS cart_item (
	id SERIAL NOT NULL,
	cart_id UUID NOT NULL,
	product_id UUID NOT NULL,
	quantity INTEGER NOT NULL,
	unit_price_at_time FLOAT NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(cart_id) REFERENCES cart (id),
	FOREIGN KEY(product_id) REFERENCES product (id)
);

CREATE TABLE IF NOT EXISTS categoryproductlink (
	category_id INTEGER NOT NULL,
	product_id UUID NOT NULL,
	PRIMARY KEY (category_id, product_id),
	FOREIGN KEY(category_id) REFERENCES category (id),
	FOREIGN KEY(product_id) REFERENCES product (id)
);

CREATE TABLE IF NOT EXISTS "order" (
	id SERIAL NOT NULL,
	user_id UUID NOT NULL,
	cart_id UUID,
	address_id UUID NOT NULL,
	order_date TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	final_price FLOAT NOT NULL,
	status VARCHAR NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_order_final_price_non_negative CHECK (final_price >= 0),
	FOREIGN KEY(user_id) REFERENCES "user" (id),
	FOREIGN KEY(cart_id) REFERENCES cart (id),
	FOREIGN KEY(address_id) REFERENCES address (id)
);

CREATE TABLE IF NOT EXISTS payment (
	id UUID NOT NULL,
	order_id UUID NOT NULL,
	user_id UUID NOT NULL,
	address_id UUID NOT NULL,
	provider VARCHAR NOT NULL,
	status VARCHAR NOT NULL,
	payer_email VARCHAR(255) NOT NULL,
	amount NUMERIC(10, 2) NOT NULL,
	currency VARCHAR(10) NOT NULL,
	provider_session_id VARCHAR(255),
	provider_payment_id VARCHAR(255),
	created_at TIMESTAMP WITH TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(user_id) REFERENCES "user" (id),
	FOREIGN KEY(address_id) REFERENCES address (id)
);

CREATE TABLE IF NOT EXISTS product_image (
	id SERIAL NOT NULL,
	product_id UUID NOT NULL,
	url VARCHAR NOT NULL,
	"order" INTEGER NOT NULL,
	alt_text VARCHAR,
	PRIMARY KEY (id),
	CONSTRAINT ck_product_image_order_positive CHECK ("order" >= 1),
	FOREIGN KEY(product_id) REFERENCES product (id)
);

CREATE TABLE IF NOT EXISTS product_review (
	id SERIAL NOT NULL,
	product_id UUID NOT NULL,
	user_id UUID NOT NULL,
	rating INTEGER NOT NULL,
	title VARCHAR,
	comment VARCHAR,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_product_review_rating_range CHECK (rating >= 1 AND rating <= 5),
	FOREIGN KEY(product_id) REFERENCES product (id),
	FOREIGN KEY(user_id) REFERENCES "user" (id)
);

CREATE TABLE IF NOT EXISTS stock (
	id UUID NOT NULL,
	product_id UUID NOT NULL,
	total_quantity INTEGER NOT NULL,
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_stock_quantity_non_negative CHECK (total_quantity >= 0),
	FOREIGN KEY(product_id) REFERENCES product (id)
);

CREATE TABLE IF NOT EXISTS supplier_product (
	id UUID NOT NULL,
	supplier_id INTEGER NOT NULL,
	product_id UUID NOT NULL,
	supplier_price FLOAT NOT NULL,
	lead_time_days INTEGER,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(supplier_id) REFERENCES supplier (id),
	FOREIGN KEY(product_id) REFERENCES product (id)
);

CREATE TABLE IF NOT EXISTS order_item (
	id SERIAL NOT NULL,
	order_id INTEGER NOT NULL,
	product_id UUID NOT NULL,
	quantity INTEGER NOT NULL,
	unit_price_at_time FLOAT NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_order_item_quantity_non_negative CHECK (quantity >= 0),
	CONSTRAINT ck_order_item_unit_price_non_negative CHECK (unit_price_at_time >= 0),
	FOREIGN KEY(order_id) REFERENCES "order" (id),
	FOREIGN KEY(product_id) REFERENCES product (id)
);

CREATE TABLE IF NOT EXISTS ordercouponlink (
	order_id INTEGER NOT NULL,
	coupon_id INTEGER NOT NULL,
	PRIMARY KEY (order_id, coupon_id),
	FOREIGN KEY(order_id) REFERENCES "order" (id),
	FOREIGN KEY(coupon_id) REFERENCES coupon (id)
);

CREATE TABLE IF NOT EXISTS paymentitem (
	id UUID NOT NULL,
	product_id UUID NOT NULL,
	payment_id UUID NOT NULL,
	title VARCHAR(255) NOT NULL,
	product_url VARCHAR(500) NOT NULL,
	unit_price NUMERIC(10, 2) NOT NULL,
	quantity INTEGER NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(product_id) REFERENCES product (id),
	FOREIGN KEY(payment_id) REFERENCES payment (id)
);

CREATE TABLE IF NOT EXISTS stock_batch (
	id UUID NOT NULL,
	product_id UUID NOT NULL,
	supplier_id INTEGER,
	stock_id UUID NOT NULL,
	quantity INTEGER NOT NULL,
	unit_cost FLOAT NOT NULL,
	expiry_date DATE,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(product_id) REFERENCES product (id),
	FOREIGN KEY(supplier_id) REFERENCES supplier (id),
	FOREIGN KEY(stock_id) REFERENCES stock (id)
);

CREATE TABLE IF NOT EXISTS stock_movement (
	id UUID NOT NULL,
	product_id UUID NOT NULL,
	stock_id UUID NOT NULL,
	movement_type stockmovementtype NOT NULL,
	quantity INTEGER NOT NULL,
	reason VARCHAR,
	order_id UUID,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(product_id) REFERENCES product (id),
	FOREIGN KEY(stock_id) REFERENCES stock (id)
);

CREATE INDEX IF NOT EXISTS ix_brand_name ON brand (name);

CREATE INDEX IF NOT EXISTS ix_category_name ON category (name);

CREATE UNIQUE INDEX IF NOT EXISTS ix_coupon_code ON coupon (code);

CREATE INDEX IF NOT EXISTS ix_supplier_email ON supplier (email);

CREATE INDEX IF NOT EXISTS ix_supplier_name ON supplier (name);

CREATE UNIQUE INDEX IF NOT EXISTS ix_user_email ON "user" (email);

CREATE INDEX IF NOT EXISTS ix_user_id ON "user" (id);

CREATE INDEX IF NOT EXISTS ix_address_user_id ON address (user_id);

CREATE INDEX IF NOT EXISTS ix_cart_id ON cart (id);

CREATE INDEX IF NOT EXISTS ix_cart_user_id ON cart (user_id);

CREATE INDEX IF NOT EXISTS ix_product_brand_id ON product (brand_id);

CREATE INDEX IF NOT EXISTS ix_product_description_id ON product (description_id);

CREATE INDEX IF NOT EXISTS ix_product_id ON product (id);

CREATE UNIQUE INDEX IF NOT EXISTS ix_product_name ON product (name);

CREATE UNIQUE INDEX IF NOT EXISTS ix_product_slug ON product (slug);

CREATE INDEX IF NOT EXISTS ix_cart_item_cart_id ON cart_item (cart_id);

CREATE INDEX IF NOT EXISTS ix_cart_item_product_id ON cart_item (product_id);

CREATE INDEX IF NOT EXISTS ix_categoryproductlink_product_id ON categoryproductlink (product_id);

CREATE INDEX IF NOT EXISTS ix_order_address_id ON "order" (address_id);

CREATE INDEX IF NOT EXISTS ix_order_cart_id ON "order" (cart_id);

CREATE INDEX IF NOT EXISTS ix_order_user_id ON "order" (user_id);

CREATE INDEX IF NOT EXISTS ix_payment_address_id ON payment (address_id);

CREATE INDEX IF NOT EXISTS ix_payment_id ON payment (id);

CREATE INDEX IF NOT EXISTS ix_payment_order_id ON payment (order_id);

CREATE INDEX IF NOT EXISTS ix_payment_provider_payment_id ON payment (provider_payment_id);

CREATE INDEX IF NOT EXISTS ix_payment_provider_session_id ON payment (provider_session_id);

CREATE INDEX IF NOT EXISTS ix_payment_status ON payment (status);

CREATE INDEX IF NOT EXISTS ix_payment_user_id ON payment (user_id);

CREATE INDEX IF NOT EXISTS ix_product_image_product_id ON product_image (product_id);

CREATE INDEX IF NOT EXISTS ix_product_review_product_id ON product_review (product_id);

CREATE INDEX IF NOT EXISTS ix_product_review_user_id ON product_review (user_id);

CREATE UNIQUE INDEX IF NOT EXISTS ix_stock_product_id ON stock (product_id);

CREATE INDEX IF NOT EXISTS ix_supplier_product_product_id ON supplier_product (product_id);

CREATE INDEX IF NOT EXISTS ix_supplier_product_supplier_id ON supplier_product (supplier_id);

CREATE INDEX IF NOT EXISTS ix_order_item_order_id ON order_item (order_id);

CREATE INDEX IF NOT EXISTS ix_order_item_product_id ON order_item (product_id);

CREATE INDEX IF NOT EXISTS ix_ordercouponlink_coupon_id ON ordercouponlink (coupon_id);

CREATE INDEX IF NOT EXISTS ix_paymentitem_id ON paymentitem (id);

CREATE INDEX IF NOT EXISTS ix_paymentitem_payment_id ON paymentitem (payment_id);

CREATE INDEX IF NOT EXISTS ix_paymentitem_product_id ON paymentitem (product_id);

CREATE INDEX IF NOT EXISTS ix_stock_batch_product_id ON stock_batch (product_id);

CREATE INDEX IF NOT EXISTS ix_stock_batch_stock_id ON stock_batch (stock_id);

CREATE INDEX IF NOT EXISTS ix_stock_batch_supplier_id ON stock_batch (supplier_id);

CREATE INDEX IF NOT EXISTS ix_stock_movement_product_id ON stock_movement (product_id);

CREATE INDEX IF NOT EXISTS ix_stock_movement_stock_id ON stock_movement (stock_id);

alter table public.brand enable row level security;
alter table public.category enable row level security;
alter table public.coupon enable row level security;
alter table public.description enable row level security;
alter table public.payment_method enable row level security;
alter table public.supplier enable row level security;
alter table public."user" enable row level security;
alter table public.address enable row level security;
alter table public.cart enable row level security;
alter table public.product enable row level security;
alter table public.cart_item enable row level security;
alter table public.categoryproductlink enable row level security;
alter table public."order" enable row level security;
alter table public.payment enable row level security;
alter table public.product_image enable row level security;
alter table public.product_review enable row level security;
alter table public.stock enable row level security;
alter table public.supplier_product enable row level security;
alter table public.order_item enable row level security;
alter table public.ordercouponlink enable row level security;
alter table public.paymentitem enable row level security;
alter table public.stock_batch enable row level security;
alter table public.stock_movement enable row level security;
