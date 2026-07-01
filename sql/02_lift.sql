-- ---------------------------------------------------------------------------
-- 02. Lift
-- ---------------------------------------------------------------------------
-- Pivots each group's conversion rate onto a row and computes:
--   * absolute lift = treatment rate - control rate (in percentage points)
--   * relative lift = absolute lift / control rate 
-- ---------------------------------------------------------------------------
WITH group_rates AS (
    -- One row per group with its conversion rate
    SELECT
        experiment_group,
        SUM(views)                        AS views,
        SUM(bookings)                     AS bookings,
        1.0 * SUM(bookings) / SUM(views)  AS conversion_rate
    FROM ab_test_results
    GROUP BY experiment_group
),
pivoted AS (
    -- Put control and treatment side by side on one row
    SELECT
        MAX(CASE WHEN experiment_group = 'control'   THEN conversion_rate END) AS control_rate,
        MAX(CASE WHEN experiment_group = 'treatment' THEN conversion_rate END) AS treatment_rate
    FROM group_rates
)
SELECT
    ROUND(control_rate,   5)                                        AS control_rate,
    ROUND(treatment_rate, 5)                                        AS treatment_rate,
    ROUND(treatment_rate - control_rate, 5)                         AS absolute_lift,
    ROUND(100.0 * (treatment_rate - control_rate) / control_rate, 2) AS relative_lift_pct
FROM pivoted;
