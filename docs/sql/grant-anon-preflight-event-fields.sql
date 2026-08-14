-- MANUAL REVIEW ONLY
GRANT SELECT (
    start_time,
    end_time,
    room,
    event_type,
    classification,
    data_quality,
    normalization_status,
    verification_status
) ON TABLE public.events TO anon;
