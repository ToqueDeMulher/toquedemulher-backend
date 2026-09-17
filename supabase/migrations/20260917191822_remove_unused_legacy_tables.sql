-- Both tables have no callers in the active application. Stop if either table
-- gained data since the audit; DROP TABLE RESTRICT also protects dependencies.
DO $$
DECLARE
    has_rows boolean;
BEGIN
    IF to_regclass('public.payment_method') IS NOT NULL THEN
        EXECUTE 'SELECT EXISTS (SELECT 1 FROM public.payment_method)' INTO has_rows;
        IF has_rows THEN
            RAISE EXCEPTION 'public.payment_method is not empty';
        END IF;
        DROP TABLE public.payment_method RESTRICT;
    END IF;

    IF to_regclass('tdm_archive.paymentitem') IS NOT NULL THEN
        EXECUTE 'SELECT EXISTS (SELECT 1 FROM tdm_archive.paymentitem)' INTO has_rows;
        IF has_rows THEN
            RAISE EXCEPTION 'tdm_archive.paymentitem is not empty';
        END IF;
        DROP TABLE tdm_archive.paymentitem RESTRICT;
    END IF;
END;
$$;

DROP SCHEMA IF EXISTS tdm_archive RESTRICT;
