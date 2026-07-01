-- ---------------------------------------------------------------------------
-- 04. Sample-ratio-mismatch (SRM) check
-- ---------------------------------------------------------------------------
-- Chi-square of the observed split vs the designed 50/50.
-- With 1 degree of freedom, a statistic above 3.84 means p < 0.05.
-- ---------------------------------------------------------------------------
WITH counts AS (
    SELECT
        SUM(CASE WHEN experiment_group = 'control'   THEN 1 ELSE 0 END) AS n_control,
        SUM(CASE WHEN experiment_group = 'treatment' THEN 1 ELSE 0 END) AS n_treatment,
        COUNT(*)                                                        AS n_total
    FROM ab_test_results
)
SELECT
    n_control,
    n_treatment,
    ROUND(1.0 * n_control / n_total, 4)   AS control_share,
    ROUND(
        (n_control   - n_total / 2.0) * (n_control   - n_total / 2.0) / (n_total / 2.0)
      + (n_treatment - n_total / 2.0) * (n_treatment - n_total / 2.0) / (n_total / 2.0)
    , 4)                                  AS chi_square_stat,
    CASE
        WHEN (n_control   - n_total / 2.0) * (n_control   - n_total / 2.0) / (n_total / 2.0)
           + (n_treatment - n_total / 2.0) * (n_treatment - n_total / 2.0) / (n_total / 2.0)
             > 3.84
        THEN 'FAIL - investigate randomization'
        ELSE 'PASS'
    END                                   AS srm_verdict
FROM counts;
