import logging
from config import CONFIG
from google.cloud import bigquery

logger = logging.getLogger(__name__)

BIGQUERY_CLIENT_PROJECT = CONFIG['billing']['bigquery_client_project'].get()
BILLING_TABLE_FULL_NAME = CONFIG['billing']['billing_export_table_name'].get()
COST_WINDOW_DAYS = CONFIG['filters']['age_maximum_days'].get(int)

def query_billing_info():
    client = bigquery.Client(project=BIGQUERY_CLIENT_PROJECT)

    if COST_WINDOW_DAYS and COST_WINDOW_DAYS > 0:
        date_filter_clause = f"AND PARSE_DATE('%Y-%m-%d', FORMAT_TIMESTAMP('%Y-%m-%d', usage_start_time)) >= DATE_SUB(CURRENT_DATE(), INTERVAL {COST_WINDOW_DAYS} DAY)"
        cost_reference_date = f"DATE_SUB(CURRENT_DATE(), INTERVAL {COST_WINDOW_DAYS} DAY)"
    else:
        date_filter_clause = "AND PARSE_DATE('%Y-%m-%d', FORMAT_TIMESTAMP('%Y-%m-%d', usage_start_time)) >= DATE_SUB(DATE_TRUNC(CURRENT_DATE(), MONTH), INTERVAL 1 MONTH)"
        cost_reference_date = "DATE_SUB(DATE_TRUNC(CURRENT_DATE(), MONTH), INTERVAL 1 MONTH)"

    query = f"""
        SELECT
            billing_account_id,
            project.id AS project_id,
            ROUND(SUM(cost), 2) AS cost_generated,
            currency,
            ({cost_reference_date}) AS cost_reference_start_date
        FROM
            `{BILLING_TABLE_FULL_NAME}`
        WHERE
            project.id IS NOT NULL
            {date_filter_clause}
        GROUP BY
            billing_account_id,
            project.id,
            currency,
            cost_reference_start_date
        ORDER BY
            cost_generated DESC
        LIMIT 1000
    """

    logger.debug('Executing dynamic cost query:\n%s', query)
    query_job = client.query(query)
    results = query_job.result()
    
    results_by_project = {}
    for row in results:
        results_by_project[row.project_id] = {
            'billingAccountName': row.billing_account_id,
            'billingAccountId': row.billing_account_id,
            'projectId': row.project_id,
            'costGenerated': row.cost_generated,
            'currency': row.currency,
            'costReferenceStartDate': row.cost_reference_start_date.strftime('%Y-%m-%d')
        }

    return results_by_project

