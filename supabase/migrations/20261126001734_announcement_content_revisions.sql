CREATE TABLE public.announcement_revision (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    status text NOT NULL DEFAULT 'draft'
        CONSTRAINT ck_announcement_revision_status
        CHECK (status IN ('draft', 'published', 'archived')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    published_at timestamptz
);

CREATE TABLE public.announcement_message (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    revision_id uuid NOT NULL
        REFERENCES public.announcement_revision(id) ON DELETE CASCADE,
    text text NOT NULL
        CONSTRAINT ck_announcement_message_text
        CHECK (length(btrim(text)) BETWEEN 1 AND 160),
    destination text NOT NULL
        CONSTRAINT ck_announcement_message_destination
        CHECK (
            length(destination) BETWEEN 1 AND 500
            AND destination LIKE '/%'
            AND destination NOT LIKE '//%'
            AND position(chr(92) IN destination) = 0
        ),
    active boolean NOT NULL DEFAULT true,
    sort_order integer NOT NULL
        CONSTRAINT ck_announcement_message_sort_order CHECK (sort_order >= 1),
    CONSTRAINT uq_announcement_message_revision_order
        UNIQUE (revision_id, sort_order)
);

-- A revision is edited privately until the administrator explicitly publishes it.
CREATE UNIQUE INDEX ux_announcement_revision_live_status
    ON public.announcement_revision (status)
    WHERE status IN ('draft', 'published');

-- Supports ordered reads and makes the foreign-key cascade efficient.
CREATE INDEX ix_announcement_message_revision_order
    ON public.announcement_message (revision_id, sort_order);

-- These tables are backend-only. FastAPI uses the database service connection;
-- Supabase Data API roles receive no direct policy.
ALTER TABLE public.announcement_revision ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.announcement_message ENABLE ROW LEVEL SECURITY;
