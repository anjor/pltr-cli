# Common Workflows

This guide covers real-world data analysis patterns and workflows using pltr-cli. Learn how to combine commands effectively for common tasks.

## 📊 Data Analysis Workflows

### Basic Data Exploration

Start your analysis by understanding what data is available:

```bash
# 1. List available ontologies to understand data structure
pltr ontology list --format table

# 2. Explore a specific ontology
pltr ontology get ri.ontology.main.ontology.abc123

# 3. See what object types are available
pltr ontology object-type-list ri.ontology.main.ontology.abc123

# 4. Check current user permissions
pltr admin user current
```

### SQL-Based Analysis Workflow

For traditional SQL analysis:

```bash
# 1. Start with a simple count to test connectivity
pltr sql execute "SELECT COUNT(*) FROM my_dataset"

# 2. Explore data structure
pltr sql execute "DESCRIBE my_dataset"

# 3. Sample data exploration
pltr sql execute "SELECT * FROM my_dataset LIMIT 10" --format table

# 4. Run analysis and export results
pltr sql execute "
  SELECT category,
         COUNT(*) as total_count,
         AVG(value) as avg_value
  FROM my_dataset
  WHERE date_column >= '2025-01-01'
  GROUP BY category
  ORDER BY total_count DESC
" --format csv --output analysis_results.csv

# 5. For long-running queries, use async pattern
QUERY_ID=$(pltr sql submit "SELECT * FROM huge_dataset WHERE complex_condition")
pltr sql wait $QUERY_ID --format json --output results.json
```

### Ontology-Based Analysis Workflow

For object-oriented data exploration:

```bash
# 1. Explore object types in your ontology
ONTOLOGY_RID="ri.ontology.main.ontology.abc123"
pltr ontology object-type-list $ONTOLOGY_RID

# 2. Get detailed info about an object type
pltr ontology object-type-get $ONTOLOGY_RID Employee

# 3. List objects with specific properties
pltr ontology object-list $ONTOLOGY_RID Employee \
  --properties "name,department,startDate" \
  --format json --output employees.json

# 4. Analyze specific objects
pltr ontology object-get $ONTOLOGY_RID Employee "john.doe" \
  --properties "name,department,manager,projects"

# 5. Find linked objects
pltr ontology object-linked $ONTOLOGY_RID Employee "john.doe" worksOn \
  --properties "name,status,deadline"

# 6. Aggregate data
pltr ontology object-aggregate $ONTOLOGY_RID Employee \
  '{"count": "count", "avg_salary": "avg"}' \
  --group-by department \
  --format csv --output department_stats.csv
```

## 🔄 Data Pipeline Workflows

### ETL Pipeline with pltr-cli

Create repeatable data extraction and transformation pipelines:

```bash
#!/bin/bash
# pipeline.sh - Daily data extraction pipeline

# Set environment
export FOUNDRY_TOKEN="$PRODUCTION_TOKEN"
export FOUNDRY_HOST="foundry.company.com"

# 1. Extract data
echo "Extracting daily sales data..."
pltr sql execute "
  SELECT date, product_id, quantity, revenue
  FROM sales_data
  WHERE date = CURRENT_DATE - 1
" --format csv --output daily_sales.csv

# 2. Extract related data
echo "Extracting product information..."
pltr ontology object-list ri.ontology.main.ontology.products Product \
  --properties "id,name,category,price" \
  --format json --output products.json

# 3. Generate summary report
echo "Generating summary..."
pltr sql execute "
  SELECT
    category,
    SUM(quantity) as total_quantity,
    SUM(revenue) as total_revenue,
    COUNT(DISTINCT product_id) as unique_products
  FROM sales_data s
  JOIN product_data p ON s.product_id = p.id
  WHERE s.date = CURRENT_DATE - 1
  GROUP BY category
  ORDER BY total_revenue DESC
" --format table

echo "Pipeline completed. Data saved to daily_sales.csv and products.json"
```

### Data Quality Monitoring

Monitor data quality across your datasets:

```bash
#!/bin/bash
# data_quality_check.sh

# 1. Check for null values
pltr sql execute "
  SELECT
    'null_check' as check_type,
    SUM(CASE WHEN important_field IS NULL THEN 1 ELSE 0 END) as null_count,
    COUNT(*) as total_count
  FROM critical_dataset
"

# 2. Check for duplicates
pltr sql execute "
  SELECT
    'duplicate_check' as check_type,
    COUNT(*) - COUNT(DISTINCT id) as duplicate_count
  FROM critical_dataset
"

# 3. Check data freshness
pltr sql execute "
  SELECT
    'freshness_check' as check_type,
    MAX(updated_date) as latest_update,
    DATEDIFF(CURRENT_DATE, MAX(updated_date)) as days_old
  FROM critical_dataset
"

# 4. Export comprehensive data profile
pltr sql execute "
  SELECT
    COUNT(*) as total_rows,
    COUNT(DISTINCT id) as unique_ids,
    MIN(created_date) as earliest_record,
    MAX(created_date) as latest_record,
    AVG(numeric_field) as avg_value
  FROM critical_dataset
" --format json --output data_profile.json
```

## 🏢 Administrative Workflows

### User Management Workflow

Common admin tasks for managing users and groups:

```bash
# 1. Get current user info
pltr admin user current

# 2. List all users and export for review
pltr admin user list --format csv --output all_users.csv

# 3. Search for specific users
pltr admin user search "john" --format table

# 4. Check user permissions
pltr admin user markings john.doe@company.com

# 5. Group management
pltr admin group list --format table
pltr admin group create "Data Science Team" --description "ML and Analytics Team"

# 6. Get group details
pltr admin group get data-science-team --format json --output group_info.json
```

### Security Audit Workflow

Audit user access and permissions:

```bash
#!/bin/bash
# security_audit.sh

echo "Starting security audit..."

# 1. Export all users
pltr admin user list --format json --output audit_users.json

# 2. Export all groups
pltr admin group list --format json --output audit_groups.json

# 3. Check admin users (requires manual review of output)
pltr admin user search "admin" --format csv --output potential_admins.csv

# 4. Generate audit report timestamp
echo "Audit completed at $(date)" > audit_timestamp.txt

echo "Security audit files generated:"
echo "- audit_users.json"
echo "- audit_groups.json"
echo "- potential_admins.csv"
echo "- audit_timestamp.txt"
```

## 📈 Analytical Workflows

### Time Series Analysis

Analyze trends over time:

```bash
# 1. Daily trends
pltr sql execute "
  SELECT
    DATE(timestamp) as date,
    COUNT(*) as daily_count,
    AVG(value) as daily_average
  FROM time_series_data
  WHERE timestamp >= DATE_SUB(CURRENT_DATE, INTERVAL 30 DAY)
  GROUP BY DATE(timestamp)
  ORDER BY date
" --format csv --output daily_trends.csv

# 2. Weekly aggregation
pltr sql execute "
  SELECT
    YEAR(timestamp) as year,
    WEEK(timestamp) as week,
    SUM(value) as weekly_total,
    COUNT(*) as weekly_count
  FROM time_series_data
  WHERE timestamp >= DATE_SUB(CURRENT_DATE, INTERVAL 12 WEEK)
  GROUP BY YEAR(timestamp), WEEK(timestamp)
  ORDER BY year, week
" --format json --output weekly_analysis.json
```

### Cohort Analysis

Analyze user behavior over time:

```bash
# 1. User registration cohorts
pltr sql execute "
  SELECT
    DATE_FORMAT(registration_date, '%Y-%m') as cohort_month,
    COUNT(*) as cohort_size
  FROM users
  GROUP BY DATE_FORMAT(registration_date, '%Y-%m')
  ORDER BY cohort_month
" --format table

# 2. Activity retention analysis
pltr sql execute "
  WITH cohorts AS (
    SELECT
      user_id,
      DATE_FORMAT(MIN(activity_date), '%Y-%m') as cohort_month
    FROM user_activity
    GROUP BY user_id
  )
  SELECT
    c.cohort_month,
    COUNT(DISTINCT c.user_id) as cohort_size,
    COUNT(DISTINCT a.user_id) as active_users
  FROM cohorts c
  LEFT JOIN user_activity a ON c.user_id = a.user_id
    AND a.activity_date >= DATE_SUB(CURRENT_DATE, INTERVAL 30 DAY)
  GROUP BY c.cohort_month
  ORDER BY c.cohort_month
" --format csv --output retention_analysis.csv
```

## 🚀 Interactive Workflows

### Exploratory Data Analysis with Shell Mode

Use interactive mode for ad-hoc analysis:

```bash
# Start interactive session
pltr shell --profile production

# In shell mode, explore data interactively:
```

```
pltr> admin user current
pltr> ontology list
pltr> ontology object-type-list ri.ontology.main.ontology.abc123
pltr> sql execute "SELECT COUNT(*) FROM interesting_dataset"
pltr> sql execute "SELECT column1, COUNT(*) FROM interesting_dataset GROUP BY column1 LIMIT 10"
pltr> exit
```

### Iterative Query Development

Develop complex queries incrementally:

```bash
pltr shell

# Start simple
pltr> sql execute "SELECT * FROM dataset LIMIT 5"

# Add filtering
pltr> sql execute "SELECT * FROM dataset WHERE category = 'important' LIMIT 10"

# Add aggregation
pltr> sql execute "SELECT category, COUNT(*) FROM dataset GROUP BY category"

# Build final complex query
pltr> sql execute "
  SELECT
    category,
    subcategory,
    COUNT(*) as count,
    AVG(value) as avg_value,
    STDDEV(value) as stddev_value
  FROM dataset
  WHERE created_date >= '2025-01-01'
  GROUP BY category, subcategory
  HAVING COUNT(*) >= 10
  ORDER BY avg_value DESC
" --format csv --output final_analysis.csv

pltr> exit
```

## 🔄 Automation Workflows

### Scheduled Data Exports

Create automated reports using cron:

```bash
# crontab entry for daily reports at 6 AM
# 0 6 * * * /path/to/daily_report.sh

#!/bin/bash
# daily_report.sh

# Set date for file naming
DATE=$(date +%Y%m%d)

# Export daily metrics
pltr sql execute "
  SELECT
    date,
    total_sales,
    total_customers,
    avg_order_value
  FROM daily_metrics
  WHERE date = CURRENT_DATE - 1
" --format csv --output "daily_report_${DATE}.csv"

# Export to monitoring system (example with curl)
# curl -X POST -F "file=@daily_report_${DATE}.csv" https://monitoring.company.com/upload
```

### CI/CD Data Validation

Validate data quality in deployment pipelines:

```bash
#!/bin/bash
# validate_data.sh - Use in CI/CD pipeline

# Set exit on error
set -e

echo "Validating data quality..."

# 1. Check row counts
ROW_COUNT=$(pltr sql execute "SELECT COUNT(*) FROM production_table" --format json | jq -r '.[0].count')

if [ "$ROW_COUNT" -lt 1000 ]; then
  echo "ERROR: Row count too low: $ROW_COUNT"
  exit 1
fi

# 2. Check for nulls in critical fields
NULL_COUNT=$(pltr sql execute "SELECT COUNT(*) FROM production_table WHERE critical_field IS NULL" --format json | jq -r '.[0].count')

if [ "$NULL_COUNT" -gt 0 ]; then
  echo "ERROR: Found $NULL_COUNT null values in critical_field"
  exit 1
fi

echo "Data validation passed!"
```

## 🎯 Performance Optimization

### Efficient Query Patterns

Best practices for large datasets:

```bash
# 1. Use async for long-running queries
QUERY_ID=$(pltr sql submit "SELECT * FROM huge_table WHERE complex_condition")
echo "Query submitted: $QUERY_ID"

# 2. Check status periodically
pltr sql status $QUERY_ID

# 3. Get results when ready
pltr sql wait $QUERY_ID --timeout 3600 --format csv --output results.csv

# 4. For multiple large queries, submit all first
Q1=$(pltr sql submit "SELECT * FROM table1 WHERE condition1")
Q2=$(pltr sql submit "SELECT * FROM table2 WHERE condition2")
Q3=$(pltr sql submit "SELECT * FROM table3 WHERE condition3")

# Then wait for all
pltr sql wait $Q1 --format csv --output results1.csv &
pltr sql wait $Q2 --format csv --output results2.csv &
pltr sql wait $Q3 --format csv --output results3.csv &
wait  # Wait for all background jobs to complete
```

### Batch Operations

Process multiple items efficiently:

```bash
#!/bin/bash
# batch_process.sh

# Read list of dataset RIDs from file
while IFS= read -r dataset_rid; do
  echo "Processing dataset: $dataset_rid"

  pltr dataset get "$dataset_rid" --format json --output "dataset_${dataset_rid##*.}.json"

  # Add small delay to avoid overwhelming the API
  sleep 1
done < dataset_rids.txt

echo "Batch processing completed"
```

## 📝 Best Practices

### Workflow Organization

1. **Use profiles** for different environments
2. **Script repetitive tasks** for consistency
3. **Export intermediate results** for debugging
4. **Use meaningful file names** with timestamps
5. **Log command outputs** for audit trails

### Error Handling

```bash
#!/bin/bash
# robust_workflow.sh

# Function to handle errors
handle_error() {
  echo "Error on line $1"
  exit 1
}

# Set error handler
trap 'handle_error $LINENO' ERR

# Verify authentication before starting
if ! pltr verify --profile production; then
  echo "Authentication failed"
  exit 1
fi

# Continue with workflow...
```

### Resource Management

- **Use appropriate timeouts** for long queries
- **Clean up temporary files** after processing
- **Monitor query costs** in your organization
- **Use pagination** for large result sets
- **Cancel queries** that are no longer needed

---

💡 **Pro Tips:**
- Use `pltr shell` for interactive exploration
- Combine `pltr sql submit` and `pltr sql wait` for efficient parallel processing
- Export to JSON for programmatic processing, CSV for spreadsheet analysis
- Use `--output` flag to save results for later analysis
- Set up shell completion with `pltr completion install` for faster command entry
