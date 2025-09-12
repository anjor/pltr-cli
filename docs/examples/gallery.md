# Examples Gallery

Real-world examples and use cases for pltr-cli. Copy, adapt, and use these examples for your own data analysis and automation needs.

## 📤 Data Import/Export Examples

### CSV Upload to Foundry
Complete examples for uploading CSV files to Foundry datasets. See [CSV Upload Examples](csv-upload.md) for:
- Simple CSV upload to new dataset with automatic schema application
- Batch CSV processing
- Transaction management for safe uploads
- Schema inference and management (using `pltr dataset schema apply`)
- Large file handling with progress tracking
- Error handling and retry logic
- Python scripts for programmatic uploads

## 📊 Data Analysis Examples

### 1. Sales Performance Dashboard

Generate a comprehensive sales analysis report:

```bash
#!/bin/bash
# sales_dashboard.sh - Generate daily sales dashboard

DATE=$(date +%Y-%m-%d)
OUTPUT_DIR="reports/sales_$DATE"
mkdir -p "$OUTPUT_DIR"

echo "Generating sales dashboard for $DATE..."

# 1. Overall sales metrics
pltr sql execute "
  SELECT
    DATE(order_date) as date,
    COUNT(*) as total_orders,
    SUM(order_value) as total_revenue,
    AVG(order_value) as avg_order_value,
    COUNT(DISTINCT customer_id) as unique_customers
  FROM sales_data
  WHERE DATE(order_date) = '$DATE'
  GROUP BY DATE(order_date)
" --format json --output "$OUTPUT_DIR/daily_summary.json"

# 2. Sales by category
pltr sql execute "
  SELECT
    product_category,
    COUNT(*) as orders,
    SUM(order_value) as revenue,
    ROUND(SUM(order_value) * 100.0 / SUM(SUM(order_value)) OVER(), 2) as revenue_pct
  FROM sales_data s
  JOIN product_data p ON s.product_id = p.id
  WHERE DATE(s.order_date) = '$DATE'
  GROUP BY product_category
  ORDER BY revenue DESC
" --format csv --output "$OUTPUT_DIR/category_breakdown.csv"

# 3. Top performing sales reps
pltr sql execute "
  SELECT
    sales_rep_name,
    COUNT(*) as deals_closed,
    SUM(order_value) as total_revenue,
    AVG(order_value) as avg_deal_size
  FROM sales_data
  WHERE DATE(order_date) = '$DATE'
  GROUP BY sales_rep_name
  ORDER BY total_revenue DESC
  LIMIT 10
" --format table

echo "Dashboard generated in $OUTPUT_DIR"
```

### 2. Customer Segmentation Analysis

Analyze customer behavior patterns:

```bash
#!/bin/bash
# customer_segmentation.sh

echo "Running customer segmentation analysis..."

# 1. Customer lifetime value calculation
pltr sql execute "
  WITH customer_metrics AS (
    SELECT
      customer_id,
      COUNT(*) as total_orders,
      SUM(order_value) as lifetime_value,
      AVG(order_value) as avg_order_value,
      DATEDIFF(MAX(order_date), MIN(order_date)) as customer_lifespan_days
    FROM sales_data
    GROUP BY customer_id
  )
  SELECT
    CASE
      WHEN lifetime_value >= 10000 THEN 'VIP'
      WHEN lifetime_value >= 5000 THEN 'High Value'
      WHEN lifetime_value >= 1000 THEN 'Medium Value'
      ELSE 'Low Value'
    END as customer_segment,
    COUNT(*) as customer_count,
    AVG(lifetime_value) as avg_lifetime_value,
    AVG(total_orders) as avg_orders,
    AVG(customer_lifespan_days) as avg_lifespan_days
  FROM customer_metrics
  GROUP BY customer_segment
  ORDER BY avg_lifetime_value DESC
" --format csv --output customer_segments.csv

# 2. Churn risk analysis
pltr sql execute "
  SELECT
    customer_id,
    MAX(order_date) as last_order_date,
    DATEDIFF(CURRENT_DATE, MAX(order_date)) as days_since_last_order,
    COUNT(*) as total_orders,
    SUM(order_value) as lifetime_value,
    CASE
      WHEN DATEDIFF(CURRENT_DATE, MAX(order_date)) > 90 THEN 'High Risk'
      WHEN DATEDIFF(CURRENT_DATE, MAX(order_date)) > 60 THEN 'Medium Risk'
      ELSE 'Low Risk'
    END as churn_risk
  FROM sales_data
  GROUP BY customer_id
  HAVING days_since_last_order > 30
  ORDER BY days_since_last_order DESC
" --format csv --output churn_analysis.csv

echo "Customer segmentation analysis completed"
```

## 🏭 Operational Analytics

### 3. Manufacturing Quality Control

Monitor production quality metrics:

```bash
#!/bin/bash
# quality_control.sh - Daily quality monitoring

SHIFT_DATE=$(date +%Y-%m-%d)

# 1. Defect rate analysis
pltr sql execute "
  SELECT
    production_line,
    shift_number,
    COUNT(*) as units_produced,
    SUM(CASE WHEN quality_status = 'DEFECT' THEN 1 ELSE 0 END) as defects,
    ROUND(
      SUM(CASE WHEN quality_status = 'DEFECT' THEN 1 ELSE 0 END) * 100.0 / COUNT(*),
      2
    ) as defect_rate_pct
  FROM production_data
  WHERE DATE(production_timestamp) = '$SHIFT_DATE'
  GROUP BY production_line, shift_number
  ORDER BY defect_rate_pct DESC
" --format table

# 2. Equipment performance
pltr sql execute "
  SELECT
    equipment_id,
    AVG(efficiency_score) as avg_efficiency,
    SUM(downtime_minutes) as total_downtime,
    COUNT(CASE WHEN status = 'MAINTENANCE' THEN 1 END) as maintenance_events
  FROM equipment_metrics
  WHERE DATE(timestamp) = '$SHIFT_DATE'
  GROUP BY equipment_id
  HAVING total_downtime > 30
  ORDER BY total_downtime DESC
" --format csv --output equipment_issues.csv

# 3. Quality trend over time
pltr sql execute "
  SELECT
    DATE(production_timestamp) as date,
    AVG(CASE WHEN quality_status = 'PASS' THEN 1.0 ELSE 0.0 END) * 100 as pass_rate,
    COUNT(*) as total_units
  FROM production_data
  WHERE production_timestamp >= DATE_SUB('$SHIFT_DATE', INTERVAL 7 DAY)
  GROUP BY DATE(production_timestamp)
  ORDER BY date
" --format json --output quality_trend.json
```

### 4. Financial Reporting Automation

Generate automated financial reports:

```bash
#!/bin/bash
# financial_report.sh - Monthly financial summary

MONTH=$(date -d "last month" +%Y-%m)
REPORT_DIR="financial_reports/$MONTH"
mkdir -p "$REPORT_DIR"

# 1. Revenue summary
pltr sql execute "
  SELECT
    'Revenue Summary' as metric_category,
    SUM(amount) as total_amount,
    COUNT(*) as transaction_count,
    AVG(amount) as avg_transaction
  FROM financial_transactions
  WHERE DATE_FORMAT(transaction_date, '%Y-%m') = '$MONTH'
    AND transaction_type = 'REVENUE'
" --format json --output "$REPORT_DIR/revenue_summary.json"

# 2. Expense breakdown
pltr sql execute "
  SELECT
    expense_category,
    SUM(amount) as total_expense,
    COUNT(*) as transaction_count,
    ROUND(SUM(amount) * 100.0 / (
      SELECT SUM(amount)
      FROM financial_transactions
      WHERE DATE_FORMAT(transaction_date, '%Y-%m') = '$MONTH'
        AND transaction_type = 'EXPENSE'
    ), 2) as percentage_of_total
  FROM financial_transactions
  WHERE DATE_FORMAT(transaction_date, '%Y-%m') = '$MONTH'
    AND transaction_type = 'EXPENSE'
  GROUP BY expense_category
  ORDER BY total_expense DESC
" --format csv --output "$REPORT_DIR/expense_breakdown.csv"

# 3. Cash flow analysis
pltr sql execute "
  SELECT
    WEEK(transaction_date) as week_number,
    SUM(CASE WHEN transaction_type = 'REVENUE' THEN amount ELSE 0 END) as weekly_revenue,
    SUM(CASE WHEN transaction_type = 'EXPENSE' THEN -amount ELSE 0 END) as weekly_expenses,
    SUM(CASE WHEN transaction_type = 'REVENUE' THEN amount ELSE -amount END) as net_cash_flow
  FROM financial_transactions
  WHERE DATE_FORMAT(transaction_date, '%Y-%m') = '$MONTH'
  GROUP BY WEEK(transaction_date)
  ORDER BY week_number
" --format csv --output "$REPORT_DIR/cash_flow.csv"

echo "Financial report generated in $REPORT_DIR"
```

## 🎯 Ontology-Based Examples

### 5. Employee Directory and Org Chart

Work with organizational data using ontology:

```bash
#!/bin/bash
# org_analysis.sh - Organizational analysis

ONTOLOGY_RID="ri.ontology.main.ontology.hr"

# 1. Department overview
pltr ontology object-aggregate $ONTOLOGY_RID Employee \
  '{"count": "count", "avg_tenure": "avg"}' \
  --group-by department \
  --format table

# 2. Management hierarchy
pltr ontology object-list $ONTOLOGY_RID Employee \
  --properties "name,title,department,manager,directReports" \
  --format json --output org_structure.json

# 3. Skills inventory by department
pltr ontology object-list $ONTOLOGY_RID Employee \
  --properties "name,department,skills,certifications" \
  --format csv --output skills_inventory.csv

# 4. Find all direct reports for a manager
MANAGER_ID="john.doe"
pltr ontology object-linked $ONTOLOGY_RID Employee $MANAGER_ID manages \
  --properties "name,title,startDate,performance" \
  --format table

# 5. Get employee details with all relationships
pltr ontology object-get $ONTOLOGY_RID Employee $MANAGER_ID \
  --properties "name,title,department,manager,directReports,projects,skills"
```

### 6. Project Portfolio Management

Track projects and resources:

```bash
#!/bin/bash
# project_portfolio.sh

ONTOLOGY_RID="ri.ontology.main.ontology.projects"

# 1. Active projects overview
pltr ontology object-list $ONTOLOGY_RID Project \
  --properties "name,status,priority,startDate,endDate,budget,team" \
  --format csv --output active_projects.csv

# 2. Resource allocation analysis
pltr ontology object-aggregate $ONTOLOGY_RID ProjectAssignment \
  '{"total_hours": "sum", "avg_allocation": "avg"}' \
  --group-by "employeeId,projectId" \
  --format json --output resource_allocation.json

# 3. Project timeline and dependencies
pltr ontology object-list $ONTOLOGY_RID Project \
  --properties "name,dependencies,milestones,riskLevel" \
  --format json --output project_timeline.json

# 4. Find overallocated resources
pltr ontology query-execute $ONTOLOGY_RID findOverallocatedEmployees \
  --parameters '{"threshold": 40}' \
  --format table

# 5. Budget utilization by project
pltr ontology object-list $ONTOLOGY_RID Project \
  --properties "name,budget,actualSpend,forecastSpend" \
  --format csv --output budget_analysis.csv
```

## 🚀 Automation and Integration

### 7. CI/CD Data Pipeline

Integrate pltr-cli into CI/CD workflows:

```yaml
# .github/workflows/data-pipeline.yml
name: Data Pipeline

on:
  schedule:
    - cron: '0 6 * * *'  # Daily at 6 AM
  workflow_dispatch:

jobs:
  data-extraction:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install pltr-cli
        run: pip install pltr-cli

      - name: Extract data
        env:
          FOUNDRY_TOKEN: ${{ secrets.FOUNDRY_TOKEN }}
          FOUNDRY_HOST: foundry.company.com
        run: |
          # Extract daily metrics
          pltr sql execute "
            SELECT
              DATE(timestamp) as date,
              COUNT(*) as daily_events,
              SUM(value) as daily_total
            FROM events_table
            WHERE DATE(timestamp) = CURRENT_DATE - 1
          " --format json --output daily_metrics.json

          # Validate data quality
          row_count=$(pltr sql execute "SELECT COUNT(*) as count FROM events_table WHERE DATE(timestamp) = CURRENT_DATE - 1" --format json | jq -r '.[0].count')
          if [ "$row_count" -lt 100 ]; then
            echo "Error: Insufficient data for yesterday"
            exit 1
          fi

      - name: Upload to storage
        run: |
          # Upload to cloud storage or send to monitoring system
          curl -X POST -F "file=@daily_metrics.json" \
            https://monitoring.company.com/upload
```

### 8. Slack Integration for Alerts

Send automated alerts to Slack:

```bash
#!/bin/bash
# alert_system.sh - Monitor and alert on data anomalies

SLACK_WEBHOOK="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

# 1. Check for data quality issues
ANOMALY_COUNT=$(pltr sql execute "
  SELECT COUNT(*) as count
  FROM data_quality_checks
  WHERE status = 'FAILED'
    AND check_date = CURRENT_DATE
" --format json | jq -r '.[0].count')

if [ "$ANOMALY_COUNT" -gt 0 ]; then
  MESSAGE="🚨 Data Quality Alert: $ANOMALY_COUNT failed checks detected today"
  curl -X POST -H 'Content-type: application/json' \
    --data "{\"text\":\"$MESSAGE\"}" \
    "$SLACK_WEBHOOK"
fi

# 2. Check system performance
SLOW_QUERIES=$(pltr sql execute "
  SELECT COUNT(*) as count
  FROM query_performance_log
  WHERE execution_time_seconds > 300
    AND query_date >= CURRENT_DATE - 1
" --format json | jq -r '.[0].count')

if [ "$SLOW_QUERIES" -gt 5 ]; then
  MESSAGE="⚠️ Performance Alert: $SLOW_QUERIES slow queries detected in last 24 hours"
  curl -X POST -H 'Content-type: application/json' \
    --data "{\"text\":\"$MESSAGE\"}" \
    "$SLACK_WEBHOOK"
fi

# 3. Send daily summary
SUMMARY=$(pltr sql execute "
  SELECT
    COUNT(*) as total_records,
    AVG(processing_time) as avg_processing_time,
    SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) as successful_jobs
  FROM daily_job_summary
  WHERE job_date = CURRENT_DATE
" --format json)

RECORDS=$(echo "$SUMMARY" | jq -r '.[0].total_records')
AVG_TIME=$(echo "$SUMMARY" | jq -r '.[0].avg_processing_time')
SUCCESS_JOBS=$(echo "$SUMMARY" | jq -r '.[0].successful_jobs')

MESSAGE="📊 Daily Summary: $RECORDS records processed, $SUCCESS_JOBS successful jobs, avg time: ${AVG_TIME}s"
curl -X POST -H 'Content-type: application/json' \
  --data "{\"text\":\"$MESSAGE\"}" \
  "$SLACK_WEBHOOK"
```

## 📈 Advanced Analytics

### 9. Time Series Forecasting Data Prep

Prepare data for machine learning models:

```bash
#!/bin/bash
# ml_data_prep.sh - Prepare time series data for forecasting

OUTPUT_DIR="ml_datasets/$(date +%Y%m%d)"
mkdir -p "$OUTPUT_DIR"

# 1. Historical sales data with features
pltr sql execute "
  SELECT
    DATE(order_date) as date,
    SUM(order_value) as daily_revenue,
    COUNT(*) as daily_orders,
    COUNT(DISTINCT customer_id) as unique_customers,
    AVG(order_value) as avg_order_value,
    DAYOFWEEK(order_date) as day_of_week,
    MONTH(order_date) as month,
    CASE WHEN DAYOFWEEK(order_date) IN (1,7) THEN 1 ELSE 0 END as is_weekend
  FROM sales_data
  WHERE order_date >= DATE_SUB(CURRENT_DATE, INTERVAL 2 YEAR)
  GROUP BY DATE(order_date)
  ORDER BY date
" --format csv --output "$OUTPUT_DIR/sales_timeseries.csv"

# 2. External factors (holidays, campaigns)
pltr sql execute "
  SELECT
    date,
    is_holiday,
    holiday_name,
    marketing_campaign_active,
    campaign_type,
    campaign_budget
  FROM external_factors
  WHERE date >= DATE_SUB(CURRENT_DATE, INTERVAL 2 YEAR)
  ORDER BY date
" --format csv --output "$OUTPUT_DIR/external_factors.csv"

# 3. Product category trends
pltr sql execute "
  SELECT
    DATE(order_date) as date,
    product_category,
    SUM(order_value) as category_revenue,
    COUNT(*) as category_orders
  FROM sales_data s
  JOIN product_data p ON s.product_id = p.id
  WHERE order_date >= DATE_SUB(CURRENT_DATE, INTERVAL 2 YEAR)
  GROUP BY DATE(order_date), product_category
  ORDER BY date, product_category
" --format csv --output "$OUTPUT_DIR/category_trends.csv"

echo "ML datasets prepared in $OUTPUT_DIR"
```

### 10. Customer Journey Analysis

Analyze customer touchpoints and conversion paths:

```bash
#!/bin/bash
# customer_journey.sh

ONTOLOGY_RID="ri.ontology.main.ontology.marketing"

# 1. Touchpoint sequence analysis
pltr sql execute "
  WITH customer_touchpoints AS (
    SELECT
      customer_id,
      touchpoint_type,
      touchpoint_timestamp,
      ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY touchpoint_timestamp) as touchpoint_sequence
    FROM customer_interactions
    WHERE touchpoint_timestamp >= DATE_SUB(CURRENT_DATE, INTERVAL 90 DAY)
  )
  SELECT
    touchpoint_sequence,
    touchpoint_type,
    COUNT(*) as frequency,
    COUNT(DISTINCT customer_id) as unique_customers
  FROM customer_touchpoints
  WHERE touchpoint_sequence <= 5
  GROUP BY touchpoint_sequence, touchpoint_type
  ORDER BY touchpoint_sequence, frequency DESC
" --format csv --output touchpoint_analysis.csv

# 2. Conversion funnel
pltr ontology object-aggregate $ONTOLOGY_RID CustomerJourney \
  '{"count": "count"}' \
  --group-by "stage,conversionStatus" \
  --format json --output conversion_funnel.json

# 3. Channel attribution
pltr sql execute "
  SELECT
    first_touch_channel,
    last_touch_channel,
    COUNT(*) as conversions,
    SUM(conversion_value) as total_value,
    AVG(days_to_convert) as avg_conversion_time
  FROM customer_conversions
  WHERE conversion_date >= DATE_SUB(CURRENT_DATE, INTERVAL 30 DAY)
  GROUP BY first_touch_channel, last_touch_channel
  ORDER BY total_value DESC
" --format csv --output channel_attribution.csv

echo "Customer journey analysis completed"
```

## 🛡️ Monitoring and Alerting

### 11. Data Freshness Monitoring

Monitor data pipeline health:

```bash
#!/bin/bash
# data_freshness.sh - Monitor data pipeline freshness

# Function to send alert
send_alert() {
  local message="$1"
  echo "ALERT: $message"
  # Add your alerting mechanism here (email, Slack, PagerDuty, etc.)
}

# 1. Check critical tables
CRITICAL_TABLES=("sales_data" "customer_data" "product_data" "financial_transactions")

for table in "${CRITICAL_TABLES[@]}"; do
  LAST_UPDATE=$(pltr sql execute "
    SELECT MAX(updated_timestamp) as last_update
    FROM $table
  " --format json | jq -r '.[0].last_update')

  HOURS_OLD=$(pltr sql execute "
    SELECT TIMESTAMPDIFF(HOUR, MAX(updated_timestamp), NOW()) as hours_old
    FROM $table
  " --format json | jq -r '.[0].hours_old')

  if [ "$HOURS_OLD" -gt 24 ]; then
    send_alert "Table $table is $HOURS_OLD hours old (last update: $LAST_UPDATE)"
  fi
done

# 2. Check data volumes
pltr sql execute "
  SELECT
    table_name,
    record_count,
    last_update,
    CASE
      WHEN record_count < expected_min_records THEN 'LOW_VOLUME'
      WHEN TIMESTAMPDIFF(HOUR, last_update, NOW()) > 24 THEN 'STALE'
      ELSE 'OK'
    END as status
  FROM data_health_check
  WHERE status != 'OK'
" --format table
```

## 🔄 Interactive Examples

### 12. Interactive Data Exploration Session

Example of using shell mode for analysis:

```bash
# Start interactive session
pltr shell --profile production

# Interactive exploration session:
```

```
pltr> # Start with understanding what's available
pltr> ontology list

pltr> # Pick an interesting ontology
pltr> ontology object-type-list ri.ontology.main.ontology.sales

pltr> # Explore customer data
pltr> ontology object-list ri.ontology.main.ontology.sales Customer --properties "name,type,revenue" --page-size 10

pltr> # Check specific customer
pltr> ontology object-get ri.ontology.main.ontology.sales Customer "CUST-12345" --properties "name,totalRevenue,lastOrderDate,orders"

pltr> # Quick SQL analysis
pltr> sql execute "SELECT COUNT(*) FROM customer_orders WHERE order_date >= '2025-01-01'"

pltr> # Dive deeper into recent trends
pltr> sql execute "
  SELECT
    DATE(order_date) as date,
    COUNT(*) as orders,
    SUM(order_value) as revenue
  FROM customer_orders
  WHERE order_date >= DATE_SUB(CURRENT_DATE, INTERVAL 7 DAY)
  GROUP BY DATE(order_date)
  ORDER BY date
"

pltr> # Export findings
pltr> sql execute "SELECT * FROM recent_analysis" --format csv --output findings.csv

pltr> exit
```

---

## 💡 Tips for Adapting Examples

### Customization Guidelines

1. **Replace placeholders**: Update table names, column names, and RIDs to match your environment
2. **Adjust time periods**: Modify date ranges to suit your analysis needs
3. **Add your metrics**: Include KPIs specific to your business
4. **Customize output**: Change format and file paths as needed
5. **Add error handling**: Include proper error checking for production use

### Common Adaptations

```bash
# Replace these placeholders with your actual values:
ONTOLOGY_RID="ri.ontology.main.ontology.YOUR_ONTOLOGY"
TABLE_NAME="your_table_name"
DATE_COLUMN="your_date_column"
VALUE_COLUMN="your_value_column"

# Adjust date ranges:
CURRENT_DATE - 1          # Yesterday
INTERVAL 7 DAY            # Last week
INTERVAL 30 DAY           # Last month
DATE_SUB(CURRENT_DATE, INTERVAL 90 DAY)  # Last quarter
```

### Production Considerations

- Add proper error handling and logging
- Use environment variables for sensitive data
- Implement retry logic for network issues
- Add data validation before processing
- Use appropriate timeouts for long-running queries
- Consider pagination for large datasets

---

💡 **Remember**: These examples provide patterns and starting points. Always adapt them to your specific data structure, business logic, and security requirements!
