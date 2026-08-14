-- MANUAL REVIEW ONLY
GRANT SELECT (
    start_time,
    end_time,
    room,
    event_type
) ON TABLE public.events TO anon;
