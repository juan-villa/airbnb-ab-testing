-- ---------------------------------------------------------------------------
-- 01. Overall A/B group comparison
-- ---------------------------------------------------------------------------
-- Compares the control and treatment groups on differing metrics:
-- sample size, traffic, bookings, conversion rate, and revenue per view.
-- ---------------------------------------------------------------------------
SELECT
    experiment_group,
    COUNT(*)                                   AS listings,        -- experiment units
    SUM(views)                                 AS total_views,     -- exposure
    SUM(bookings)                              AS total_bookings,  -- successes
    ROUND(1.0 * SUM(bookings) / SUM(views), 5) AS conversion_rate, -- primary metric
    ROUND(SUM(revenue), 0)                     AS total_revenue,
    ROUND(SUM(revenue) / SUM(views), 4)        AS revenue_per_view -- secondary metric
FROM ab_test_results
GROUP BY experiment_group
ORDER BY experiment_group;
