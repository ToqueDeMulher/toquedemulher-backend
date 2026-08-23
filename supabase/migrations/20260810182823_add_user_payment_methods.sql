CREATE TABLE IF NOT EXISTS user_payment_method (
	id UUID NOT NULL,
	user_id UUID NOT NULL,
	method_type VARCHAR NOT NULL,
	label VARCHAR,
	holder_name VARCHAR,
	billing_document VARCHAR,
	card_brand VARCHAR,
	card_last4 VARCHAR,
	card_exp_month INTEGER,
	card_exp_year INTEGER,
	is_default BOOLEAN NOT NULL,
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT ck_user_payment_method_type CHECK (method_type IN ('card', 'pix', 'boleto')),
	CONSTRAINT ck_user_payment_method_card_last4 CHECK (card_last4 IS NULL OR length(card_last4) = 4),
	CONSTRAINT ck_user_payment_method_card_exp_month CHECK (
		card_exp_month IS NULL OR (card_exp_month >= 1 AND card_exp_month <= 12)
	),
	CONSTRAINT ck_user_payment_method_card_required_fields CHECK (
		method_type <> 'card'
		OR (
			holder_name IS NOT NULL
			AND card_last4 IS NOT NULL
			AND card_exp_month IS NOT NULL
			AND card_exp_year IS NOT NULL
		)
	),
	FOREIGN KEY(user_id) REFERENCES "user" (id)
);

CREATE INDEX IF NOT EXISTS ix_user_payment_method_user_id ON user_payment_method (user_id);

CREATE UNIQUE INDEX IF NOT EXISTS ix_user_payment_method_single_default
	ON user_payment_method (user_id)
	WHERE is_default;

ALTER TABLE public.user_payment_method ENABLE ROW LEVEL SECURITY;
