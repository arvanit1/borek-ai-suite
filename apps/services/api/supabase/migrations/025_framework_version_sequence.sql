DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM public.framework_versions
        GROUP BY opportunity_id, version_number
        HAVING COUNT(*) > 1
    ) THEN
        RAISE EXCEPTION 'duplicate Framework version numbers exist; reconcile them before applying migration 025';
    END IF;
END;
$$;

CREATE UNIQUE INDEX IF NOT EXISTS framework_versions_opportunity_version_key
ON public.framework_versions (opportunity_id, version_number);

CREATE OR REPLACE FUNCTION public.prevent_framework_version_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Framework versions are immutable; append a successor version';
END;
$$;

DROP TRIGGER IF EXISTS framework_versions_immutable ON public.framework_versions;
CREATE TRIGGER framework_versions_immutable
BEFORE UPDATE OR DELETE ON public.framework_versions
FOR EACH ROW EXECUTE FUNCTION public.prevent_framework_version_mutation();

CREATE OR REPLACE FUNCTION public.append_framework_version_transition(
    p_source_framework_version_id UUID,
    p_framework_version_id UUID,
    p_opportunity_id UUID,
    p_expected_status TEXT,
    p_expected_source_json JSONB,
    p_transition TEXT,
    p_successor_status TEXT,
    p_successor_json JSONB
)
RETURNS SETOF public.framework_versions
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public
AS $$
DECLARE
    source_row public.framework_versions%ROWTYPE;
    destination_row public.framework_versions%ROWTYPE;
    latest_id UUID;
    expected_target_status TEXT;
BEGIN
    PERFORM pg_advisory_xact_lock(hashtextextended(p_opportunity_id::TEXT, 0));

    SELECT *
    INTO destination_row
    FROM public.framework_versions
    WHERE id = p_framework_version_id;

    IF FOUND THEN
        IF destination_row.opportunity_id = p_opportunity_id
           AND destination_row.framework_json = p_successor_json
           AND destination_row.status = p_successor_status THEN
            RETURN NEXT destination_row;
            RETURN;
        END IF;
        RAISE EXCEPTION 'reserved Framework destination already exists';
    END IF;

    SELECT *
    INTO source_row
    FROM public.framework_versions
    WHERE id = p_source_framework_version_id
      AND opportunity_id = p_opportunity_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'source Framework version not found';
    END IF;
    IF source_row.status <> p_expected_status
       OR source_row.framework_json <> p_expected_source_json THEN
        RAISE EXCEPTION 'source Framework version changed';
    END IF;

    SELECT id
    INTO latest_id
    FROM public.framework_versions
    WHERE opportunity_id = p_opportunity_id
    ORDER BY version_number DESC
    LIMIT 1;

    IF latest_id <> p_source_framework_version_id THEN
        RAISE EXCEPTION 'source Framework version is no longer latest';
    END IF;

    expected_target_status := CASE p_transition
        WHEN 'regenerate' THEN source_row.status
        WHEN 'edit' THEN source_row.status
        WHEN 'confirm' THEN 'confirmed'
        WHEN 'reopen' THEN 'in_review'
        ELSE NULL
    END;
    IF expected_target_status IS NULL
       OR p_successor_status <> expected_target_status
       OR (p_transition IN ('regenerate', 'edit') AND source_row.status NOT IN ('draft', 'in_review'))
       OR (p_transition = 'confirm' AND source_row.status NOT IN ('draft', 'in_review'))
       OR (p_transition = 'reopen' AND source_row.status <> 'confirmed') THEN
        RAISE EXCEPTION 'invalid Framework transition';
    END IF;
    IF (p_successor_json->>'version')::INTEGER <> source_row.version_number + 1
       OR p_successor_json->>'previous_version_id' <> source_row.id::TEXT
       OR p_successor_json->>'status' <> p_successor_status THEN
        RAISE EXCEPTION 'Framework successor metadata is inconsistent';
    END IF;

    RETURN QUERY
    INSERT INTO public.framework_versions (
        id,
        opportunity_id,
        version_number,
        status,
        framework_json,
        created_by
    ) VALUES (
        p_framework_version_id,
        p_opportunity_id,
        source_row.version_number + 1,
        p_successor_status,
        p_successor_json,
        source_row.created_by
    )
    RETURNING *;
END;
$$;

REVOKE INSERT, UPDATE, DELETE ON public.framework_versions FROM authenticated;
REVOKE ALL ON FUNCTION public.append_framework_version_transition(
    UUID, UUID, UUID, TEXT, JSONB, TEXT, TEXT, JSONB
) FROM PUBLIC, authenticated;
GRANT EXECUTE ON FUNCTION public.append_framework_version_transition(
    UUID, UUID, UUID, TEXT, JSONB, TEXT, TEXT, JSONB
) TO service_role;
