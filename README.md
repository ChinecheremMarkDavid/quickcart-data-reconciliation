# QuickCart Data Integrity Crisis 

A comprehensive data engineering project that demonstrates data cleaning, reconciliation, and financial analysis skills through a real-world e-commerce scenario.

## 📋 Project Overview
Scenario:
QuickCart, a fast-growing e-commerce startup, has discovered a critical P0 incident: their Marketing dashboard shows different total sales than their bank settlement statement. Finance cannot close the month, and the CEO has escalated this issue.

## Mission:
Establish a single, bank-reconcilable source of truth for total revenue by cleaning messy transaction logs and reconciling multiple data sources.

## 🎯 Business Problem
The Crisis
Marketing's "Total Sales" dashboard: $X
Bank settlement statement: $Y
They don't match! ❌
Root Causes
Raw JSON logs contain inconsistent data formats
Database tables (orders, payments, bank_settlements) are misaligned
Test transactions mixed with production data
Multiple payment attempts per order causing duplicates
Orphan payments with no associated orders


## 🛠️ Technical Skills Demonstrated
### Python
Nested JSON parsing and data extraction
Currency normalization across multiple formats
Data validation and sanitization
File I/O operations (JSONL, CSV)
Object-oriented programming
Error handling and logging

### SQL
Common Table Expressions (CTEs)
Window functions (ROW_NUMBER for deduplication)
Complex JOINs and subqueries
NULL handling with COALESCE
Data reconciliation logic
Aggregation and financial calculations

### Database Technologies
PostgreSQL: Relational data storage and querying
MongoDB: NoSQL archival of raw transaction logs

### Data Engineering Best Practices
Data quality assessment
Deduplication strategies
Idempotent data pipelines
Comprehensive documentation
Version control with Git


## 📁 Project Structure
quickcart-data-reconciliation/
├── .gitignore                    # Excludes sensitive/large files
├── README.md                     # This file
├── requirements.txt              # Python dependencies
├── schema.sql                    # Database schema definition
│
├── scripts/
│   ├── generate_quickcart_data.py    # Synthetic data generator
│   ├── clean_transactions.py          # Python data cleaning script
│   └── load_to_mongodb.py             # MongoDB archival script
│
├── sql/
│   └── reconciliation.sql         # SQL reconciliation analysis
│
├── quickcart_data/               # NOT in Git (generated data)
│   ├── raw_data.jsonl
│   ├── seed_orders.sql
│   ├── seed_payments.sql
│   └── seed_bank_settlements.sql
│
├── output/                       # NOT in Git (results)
│   └── cleaned_transactions.csv
│
└── docs/
    └── analysis_report.md        # Findings and recommendations


## 🚀 Setup Instructions
Prerequisites
Python 3.8+
PostgreSQL 12+
MongoDB 4.4+
pip (Python package manager)


### 1. Clone Repository
bash
git clone https://github.com/yourusername/quickcart-data-reconciliation.git
cd quickcart-data-reconciliation


### 2. Create Virtual Environment
bash
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Mac/Linux)
source venv/bin/activate


### 3. Install Dependencies
bash
pip install -r requirements.txt


### 4. Setup PostgreSQL
Create Database
bash
psql -U postgres
CREATE DATABASE quickcart_db;
\q
Load Schema
bash
psql -U postgres -d quickcart_db -f schema.sql


### 5. Setup Environment Variables
Create .env file:

DATABASE_URL=postgresql://postgres:your_password@localhost:5432/quickcart_db
MONGODB_URI=mongodb://localhost:27017/


### 6. Generate Synthetic Data
bash
cd scripts
python generate_quickcart_data.py --outdir ../quickcart_data
Expected Output:

~150,000 transaction log events
50,000 orders
75,000 payment attempts
70,000 bank settlement rows


### 7. Load Data into PostgreSQL
bash
psql -U postgres -d quickcart_db -f quickcart_data/seed_orders.sql
psql -U postgres -d quickcart_db -f quickcart_data/seed_payments.sql
psql -U postgres -d quickcart_db -f quickcart_data/seed_bank_settlements.sql


### 8. Verify Data Loaded
bash
psql -U postgres -d quickcart_db

SELECT 'orders' as table_name, COUNT(*) FROM orders
UNION ALL
SELECT 'payments', COUNT(*) FROM payments
UNION ALL
SELECT 'bank_settlements', COUNT(*) FROM bank_settlements;


###🎬 Running the Project
Step 1: Clean Transaction Logs (Python)
bash
python scripts/clean_transactions.py
What it does:

Reads quickcart_data/raw_data.jsonl
Normalizes currency formats: "$10.00", "10.00", 1000 → 10.00
Filters out test/sandbox transactions
Removes invalid/incomplete records
Outputs output/cleaned_transactions.csv


### Expected Output:

📊 Processing 150,000 records...
Cleaning: 100%|██████████| 150000/150000
✅ Wrote 95,432 cleaned records

### 📊 CLEANING STATISTICS
Total records processed:        150,000
Valid records output:            95,432
Test transactions filtered:       8,500
Invalid/missing amounts:         35,068


Step 2: Run SQL Reconciliation
bash
psql -U postgres -d quickcart_db -f sql/reconciliation.sql
What it does:

Deduplicates multiple payment attempts using ROW_NUMBER()
Identifies orphan payments (no associated order)
Matches internal payments with bank settlements
Calculates discrepancy gap
Produces finance-grade reconciliation report


### Expected Output:

============================
QUICKCART RECONCILIATION REPORT
============================

METRIC                              AMOUNT (USD)    COUNT
Total Internal Sales (Cleaned)      $8,234,567.89   47,321
Total Bank Settled                  $8,156,234.12   69,845
Orphan Payments (No Order)          $234,567.00     1,234

DISCREPANCY GAP                     $78,333.77      N/A


Step 3: Archive to MongoDB
bash
python scripts/load_to_mongodb.py
What it does:

Loads raw transaction logs into MongoDB
Creates indexes for efficient querying
Handles duplicates gracefully
Provides archival timestamps


### Expected Output:

🔌 Connected to MongoDB database: quickcart
💾 Inserting 150,000 documents to MongoDB...
✅ Total documents in MongoDB: 150,000

📊 MONGODB ARCHIVAL STATISTICS
Successfully inserted:          150,000
Duplicates skipped:                   0


## 📊 Key Results & Findings
Data Quality Issues Found
8,500 test transactions (5.6%) mixed with production data
35,068 records (23.4%) had invalid/missing amount fields
Currency format chaos: 5 different formats across logs
1,234 orphan payments totaling $234,567.00 with no orders


### Reconciliation Insights
Total Successful Sales: $8,234,567.89 (47,321 orders)
Bank Settled Amount: $8,156,234.12
Discrepancy Gap: $78,333.77 (0.95% of sales)


### Root Causes of Discrepancy
Partial settlements due to processing fees
Pending settlements not yet reflected in bank
Orphan payments requiring investigation
Duplicate payment attempts in raw logs


### 💡 Technical Decisions
Why These Technologies?
PostgreSQL:

ACID compliance for financial data
Strong support for complex queries
Window functions for deduplication

MongoDB:

Schema-flexible for varied log structures
Fast writes for archival purposes
Easy querying of nested JSON

Python:

Rich ecosystem for data processing
Easy JSON/CSV manipulation
Readable, maintainable code

Data Cleaning Strategy
Amount Normalization Logic:

python
"$10.00"  → 10.00  # Strip $ and convert
"10.00"   → 10.00  # Already in dollars
1000      → 10.00  # Assume cents if >= 100
null/""   → None   # Filter out

### Deduplication Approach:

sql
ROW_NUMBER() OVER (
    PARTITION BY order_id 
    ORDER BY attempted_at ASC
)
Keeps only the first successful payment per order.

## 🚫 Files NOT in Git
The following are excluded via .gitignore:

quickcart_data/     # Generated data (~500MB)
output/             # Analysis results
venv/               # Python virtual environment
.env                # Database credentials
*.log               # Log files
__pycache__/        # Python cache

Why?

Sensitive credentials
Large generated files
Reproducible from scripts
Environment-specific


### 📈 Performance Metrics
Data Processing
JSON parsing: 150,000 records in ~45 seconds
Currency normalization: 95,432 records processed
SQL reconciliation: Executes in ~3 seconds on 195,000 total rows


### Data Quality
Success rate: 63.6% of raw logs are valid transactions
Test filter accuracy: 100% (based on flags + email patterns)
Deduplication: Reduced 75,000 payments to 47,321 unique


## 🎓 Learning Outcomes
Python Skills
✅ Nested JSON navigation
✅ Type handling and normalization
✅ File I/O with error handling
✅ Object-oriented design
✅ Data validation logic

SQL Skills
✅ CTEs for staged transformations
✅ Window functions for deduplication
✅ Complex JOINs with NULL handling
✅ Financial reconciliation logic
✅ Performance optimization

Data Engineering Concepts
✅ Data quality assessment
✅ Source of truth establishment
✅ Idempotent pipeline design
✅ Documentation and reproducibility

🔧 Troubleshooting
PostgreSQL Connection Failed
bash
# Check if PostgreSQL is running
pg_isready

# Restart PostgreSQL (Mac)
brew services restart postgresql
MongoDB Connection Failed
bash
# Check if MongoDB is running
mongosh

# Start MongoDB (Mac)
brew services start mongodb-community
Python Module Not Found
bash
# Ensure virtual environment is activated
source venv/bin/activate  # Mac/Linux
venv\Scripts\activate     # Windows

# Reinstall dependencies
pip install -r requirements.txt


### 📚 Further Improvements
Future Enhancements
Airflow orchestration for automated daily runs
Data validation tests using Great Expectations
Dashboard visualization with Streamlit or Plotly
Real-time streaming with Kafka for live reconciliation
ML anomaly detection for fraudulent transactions
Docker containerization for portability
CI/CD pipeline with GitHub Actions


### 👤 Author
Mark-David

Database Administrator
Aspiring Data Engineer
LinkedIn: [your-profile]
Email: okoyemarkdavid@gmail.com


### 📝 License
This project is created for educational and portfolio purposes.

### 🙏 Acknowledgments
Synthetic data generator based on industry best practices
Project structure inspired by real-world data engineering scenarios
Special thanks to the data engineering community
📞 Contact
Questions or feedback? Feel free to reach out:

Email: okoyemarkdavid@gmail.com
LinkedIn: [your-profile]
GitHub Issues: [repository-issues-link]
⭐ If you found this project helpful, please consider giving it a star!

