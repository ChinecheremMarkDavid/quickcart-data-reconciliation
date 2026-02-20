-- ============================================================================
-- QuickCart Financial Reconciliation Script - POSTGRESQL VERSION
-- Purpose: Produce bank-reconcilable source of truth for total sales
-- Author: [Your Name]
-- Date: 2026-02-20
-- ============================================================================

-- ============================================================================
-- OUTPUT 1: Executive Summary Report
-- ============================================================================

WITH clean_orders AS (
    SELECT 
        order_id,
        customer_id,
        customer_email,
        order_total_cents,
        currency,
        created_at
    FROM orders
    WHERE is_test = 0
        AND order_total_cents > 0
),

successful_payments AS (
    SELECT 
        payment_id,
        order_id,
        provider,
        provider_ref,
        amount_cents,
        attempted_at,
        ROW_NUMBER() OVER (
            PARTITION BY order_id 
            ORDER BY attempted_at ASC
        ) as attempt_rank
    FROM payments
    WHERE status = 'SUCCESS'
        AND order_id IS NOT NULL
        AND amount_cents > 0
),

deduplicated_payments AS (
    SELECT 
        payment_id,
        order_id,
        provider,
        provider_ref,
        amount_cents,
        attempted_at
    FROM successful_payments
    WHERE attempt_rank = 1
),

orphan_payments AS (
    SELECT 
        p.payment_id,
        p.provider,
        p.provider_ref,
        p.amount_cents,
        p.attempted_at,
        p.status
    FROM payments p
    WHERE p.order_id IS NULL
        AND p.status = 'SUCCESS'
        AND p.amount_cents > 0
),

clean_bank_settlements AS (
    SELECT DISTINCT
        settlement_id,
        COALESCE(payment_id, 'UNKNOWN') as payment_id,
        COALESCE(provider_ref, 'UNKNOWN') as provider_ref,
        settled_amount_cents,
        currency,
        settled_at
    FROM bank_settlements
    WHERE status = 'SETTLED'
        AND settled_amount_cents > 0
),

summary_metrics AS (
    SELECT 
        COALESCE(SUM(dp.amount_cents), 0) as total_internal_sales_cents,
        COUNT(dp.payment_id) as total_successful_payments,
        COALESCE(SUM(bs.settled_amount_cents), 0) as total_bank_settled_cents,
        COUNT(DISTINCT bs.settlement_id) as total_bank_settlements,
        COALESCE(SUM(op.amount_cents), 0) as total_orphan_payments_cents,
        COUNT(op.payment_id) as total_orphan_count,
        COUNT(co.order_id) as total_orders
    FROM deduplicated_payments dp
    CROSS JOIN clean_bank_settlements bs
    CROSS JOIN orphan_payments op
    CROSS JOIN clean_orders co
)

SELECT 
    '===================================================================' as report_line
UNION ALL
SELECT 
    'QUICKCART RECONCILIATION REPORT'
UNION ALL
SELECT 
    'Generated: ' || CURRENT_TIMESTAMP::TEXT
UNION ALL
SELECT 
    '==================================================================='
UNION ALL
SELECT ''
UNION ALL
SELECT 
    'METRIC' || REPEAT(' ', 40) || 'AMOUNT (USD)' || REPEAT(' ', 10) || 'COUNT'
UNION ALL
SELECT 
    REPEAT('-', 80)
UNION ALL
SELECT 
    'Total Internal Sales (Cleaned)' || REPEAT(' ', 15) || 
    '$' || ROUND(total_internal_sales_cents / 100.0, 2)::TEXT || REPEAT(' ', 10) ||
    total_successful_payments::TEXT
FROM summary_metrics
UNION ALL
SELECT 
    'Total Bank Settled' || REPEAT(' ', 25) || 
    '$' || ROUND(total_bank_settled_cents / 100.0, 2)::TEXT || REPEAT(' ', 10) ||
    total_bank_settlements::TEXT
FROM summary_metrics
UNION ALL
SELECT 
    'Orphan Payments (No Order)' || REPEAT(' ', 18) || 
    '$' || ROUND(total_orphan_payments_cents / 100.0, 2)::TEXT || REPEAT(' ', 10) ||
    total_orphan_count::TEXT
FROM summary_metrics
UNION ALL
SELECT 
    REPEAT('-', 80)
UNION ALL
SELECT 
    'DISCREPANCY GAP' || REPEAT(' ', 30) || 
    '$' || ROUND((total_internal_sales_cents - total_bank_settled_cents) / 100.0, 2)::TEXT || 
    REPEAT(' ', 10) || 'N/A'
FROM summary_metrics;


-- ============================================================================
-- OUTPUT 2: Detailed Orphan Payments
-- ============================================================================

SELECT '' as separator;
SELECT '====================================================================' as header;
SELECT 'ORPHAN PAYMENTS (No Associated Order)' as title;
SELECT '====================================================================' as header;
SELECT '' as separator;

SELECT 
    payment_id,
    provider,
    provider_ref,
    ROUND(amount_cents / 100.0, 2) as amount_usd,
    attempted_at,
    status
FROM payments
WHERE order_id IS NULL
    AND status = 'SUCCESS'
    AND amount_cents > 0
ORDER BY amount_cents DESC
LIMIT 100;


-- ============================================================================
-- OUTPUT 3: Settlement Mismatches
-- ============================================================================

SELECT '' as separator;
SELECT '====================================================================' as header;
SELECT 'SETTLEMENT MISMATCHES' as title;
SELECT '====================================================================' as header;
SELECT '' as separator;

WITH deduplicated_payments_cte AS (
    SELECT 
        payment_id,
        order_id,
        provider,
        provider_ref,
        amount_cents,
        attempted_at,
        ROW_NUMBER() OVER (
            PARTITION BY order_id 
            ORDER BY attempted_at ASC
        ) as attempt_rank
    FROM payments
    WHERE status = 'SUCCESS'
        AND order_id IS NOT NULL
        AND amount_cents > 0
),

clean_bank_cte AS (
    SELECT DISTINCT
        settlement_id,
        payment_id,
        provider_ref,
        settled_amount_cents,
        settled_at
    FROM bank_settlements
    WHERE status = 'SETTLED'
        AND settled_amount_cents > 0
),

matched_transactions AS (
    SELECT 
        dp.payment_id,
        dp.order_id,
        dp.amount_cents as internal_amount_cents,
        COALESCE(bs.settled_amount_cents, 0) as bank_amount_cents,
        dp.attempted_at,
        bs.settled_at,
        dp.provider,
        dp.provider_ref,
        (dp.amount_cents - COALESCE(bs.settled_amount_cents, 0)) as difference_cents,
        CASE 
            WHEN bs.settlement_id IS NULL THEN 'NOT_SETTLED'
            WHEN dp.amount_cents = bs.settled_amount_cents THEN 'EXACT_MATCH'
            WHEN dp.amount_cents != bs.settled_amount_cents THEN 'PARTIAL_SETTLEMENT'
            ELSE 'UNKNOWN'
        END as match_status
    FROM deduplicated_payments_cte dp
    LEFT JOIN clean_bank_cte bs 
        ON dp.payment_id = bs.payment_id 
        OR dp.provider_ref = bs.provider_ref
    WHERE dp.attempt_rank = 1
)

SELECT 
    payment_id,
    order_id,
    ROUND(internal_amount_cents / 100.0, 2) as internal_usd,
    ROUND(bank_amount_cents / 100.0, 2) as bank_usd,
    ROUND(difference_cents / 100.0, 2) as difference_usd,
    match_status,
    provider,
    attempted_at,
    settled_at
FROM matched_transactions
WHERE match_status IN ('PARTIAL_SETTLEMENT', 'NOT_SETTLED')
ORDER BY ABS(difference_cents) DESC
LIMIT 100;


-- ============================================================================
-- OUTPUT 4: Top 10 Largest Transactions
-- ============================================================================

SELECT '' as separator;
SELECT '====================================================================' as header;
SELECT 'TOP 10 LARGEST TRANSACTIONS' as title;
SELECT '====================================================================' as header;
SELECT '' as separator;

WITH top_payments AS (
    SELECT 
        payment_id,
        order_id,
        amount_cents,
        provider,
        attempted_at,
        ROW_NUMBER() OVER (
            PARTITION BY order_id 
            ORDER BY attempted_at ASC
        ) as attempt_rank
    FROM payments
    WHERE status = 'SUCCESS'
        AND order_id IS NOT NULL
        AND amount_cents > 0
),

clean_orders_cte AS (
    SELECT 
        order_id,
        customer_email
    FROM orders
    WHERE is_test = 0
        AND order_total_cents > 0
)

SELECT 
    tp.payment_id,
    tp.order_id,
    ROUND(tp.amount_cents / 100.0, 2) as amount_usd,
    tp.provider,
    tp.attempted_at,
    co.customer_email
FROM top_payments tp
JOIN clean_orders_cte co ON tp.order_id = co.order_id
WHERE tp.attempt_rank = 1
ORDER BY tp.amount_cents DESC
LIMIT 10;


-- ============================================================================
-- OUTPUT 5: FINAL RECONCILIATION STATEMENT
-- ============================================================================

SELECT '' as separator;
SELECT '====================================================================' as header;
SELECT 'FINAL RECONCILIATION STATEMENT' as title;
SELECT '====================================================================' as header;
SELECT '' as separator;

WITH summary_data AS (
    SELECT 
        (SELECT COALESCE(SUM(amount_cents), 0) 
         FROM (
             SELECT 
                 payment_id, 
                 order_id, 
                 amount_cents, 
                 ROW_NUMBER() OVER (
                     PARTITION BY order_id 
                     ORDER BY attempted_at ASC
                 ) as rn
             FROM payments
             WHERE status = 'SUCCESS' 
                 AND order_id IS NOT NULL 
                 AND amount_cents > 0
         ) p
         WHERE p.rn = 1) as total_internal_sales_cents,
        
        (SELECT COALESCE(SUM(settled_amount_cents), 0) 
         FROM bank_settlements
         WHERE status = 'SETTLED' 
             AND settled_amount_cents > 0) as total_bank_settled_cents,
        
        (SELECT COALESCE(SUM(amount_cents), 0) 
         FROM payments
         WHERE order_id IS NULL 
             AND status = 'SUCCESS' 
             AND amount_cents > 0) as total_orphan_payments_cents
)

SELECT 
    'Expected Sales (Internal)' as description,
    '$' || ROUND(total_internal_sales_cents / 100.0, 2)::TEXT as amount
FROM summary_data
UNION ALL
SELECT 
    'Bank Settled Amount',
    '$' || ROUND(total_bank_settled_cents / 100.0, 2)::TEXT
FROM summary_data
UNION ALL
SELECT 
    'Orphan Payments (Extra Money)',
    '$' || ROUND(total_orphan_payments_cents / 100.0, 2)::TEXT
FROM summary_data
UNION ALL
SELECT 
    '---',
    '---'
UNION ALL
SELECT 
    'DISCREPANCY GAP',
    '$' || ROUND((total_internal_sales_cents - total_bank_settled_cents) / 100.0, 2)::TEXT
FROM summary_data
UNION ALL
SELECT 
    'GAP as % of Sales',
    ROUND(
        ((total_internal_sales_cents - total_bank_settled_cents) * 100.0 / 
        NULLIF(total_internal_sales_cents, 0)), 
        2
    )::TEXT || '%'
FROM summary_data;


-- ============================================================================
-- END OF RECONCILIATION REPORT
-- ============================================================================