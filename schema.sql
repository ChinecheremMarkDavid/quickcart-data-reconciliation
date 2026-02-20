-- Drop tables if they exist
DROP TABLE IF EXISTS bank_settlements;
DROP TABLE IF EXISTS payments;
DROP TABLE IF EXISTS orders;

-- Orders table
CREATE TABLE orders (
    order_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    customer_email TEXT NOT NULL,
    order_total_cents INTEGER NOT NULL,
    currency TEXT NOT NULL DEFAULT 'USD',
    is_test INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL
);

-- Payments table
CREATE TABLE payments (
    payment_id TEXT PRIMARY KEY,
    order_id TEXT,  -- nullable for orphan payments
    attempt_no INTEGER NOT NULL,
    provider TEXT NOT NULL,
    provider_ref TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('SUCCESS', 'FAILED', 'PENDING')),
    amount_cents INTEGER NOT NULL,
    attempted_at TIMESTAMP NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(order_id)
);

-- Bank settlements table
CREATE TABLE bank_settlements (
    settlement_id TEXT PRIMARY KEY,
    payment_id TEXT,  -- nullable
    provider_ref TEXT,  -- nullable
    status TEXT NOT NULL DEFAULT 'SETTLED',
    settled_amount_cents INTEGER NOT NULL,
    currency TEXT NOT NULL DEFAULT 'USD',
    settled_at TIMESTAMP NOT NULL
);

-- Create indexes for better query performance
CREATE INDEX idx_payments_order_id ON payments(order_id);
CREATE INDEX idx_payments_status ON payments(status);
CREATE INDEX idx_bank_payment_id ON bank_settlements(payment_id);
CREATE INDEX idx_bank_provider_ref ON bank_settlements(provider_ref);
CREATE INDEX idx_orders_is_test ON orders(is_test);

-- Verify tables created
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public'
ORDER BY table_name;