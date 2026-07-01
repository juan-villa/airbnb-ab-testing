-- ---------------------------------------------------------------------------
-- 03. Segment breakdown
-- ---------------------------------------------------------------------------
-- Conversion lift within each borough x room type segment.
-- Segments under 20k views are excluded as noise.
-- ---------------------------------------------------------------------------
WITH segment_rates AS (
    SELECT
        l.neighbourhood_group             AS borough,
        l.room_type,
        r.experiment_group,
        SUM(r.views)                      AS views,
        SUM(r.bookings)                   AS bookings,
        1.0 * SUM(r.bookings) / SUM(r.views) AS conversion_rate
    FROM ab_test_results AS r
    JOIN listings        AS l ON l.id = r.id
    GROUP BY l.neighbourhood_group, l.room_type, r.experiment_group
)
SELECT
    borough,
    room_type,
    SUM(views)                                                       AS total_views,
    ROUND(MAX(CASE WHEN experiment_group = 'control'
              THEN conversion_rate END), 5)                          AS control_rate,
    ROUND(MAX(CASE WHEN experiment_group = 'treatment'
              THEN conversion_rate END), 5)                          AS treatment_rate,
    ROUND(100.0 * (
        MAX(CASE WHEN experiment_group = 'treatment' THEN conversion_rate END)
      - MAX(CASE WHEN experiment_group = 'control'   THEN conversion_rate END)
    ) / MAX(CASE WHEN experiment_group = 'control' THEN conversion_rate END), 2)
                                                                     AS relative_lift_pct
FROM segment_rates
GROUP BY borough, room_type
HAVING SUM(views) > 20000
ORDER BY borough, room_type;
