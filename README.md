
# Zombie Projects Watcher

## Introduction

Zombie Projects Watcher is an automation tool designed to help engineering and finance teams control infrastructure costs on Google Cloud. It identifies potentially unused ("zombie") projects based on criteria such as age and cost, and proactively notifies the owners via Google Chat, encouraging clean-up and reducing waste.

The tool operates as a Cloud Function, which can be triggered via HTTP and scheduled for periodic execution (e.g., daily or weekly) using Cloud Scheduler.

**Notification Example (Google Chat):**

![Example Chat message](example-chat-message.png?raw=true "Example Chat message")

## Requirements

Before you configure and deploy, ensure your environment meets the following requirements:

* **Google Cloud Project:** A project to host the Cloud Function and Cloud Scheduler.
* **Billing Enabled:** Billing must be enabled for the project.
* **Local Environment**:
    * [**Python**](https://www.python.org/downloads/): Version 3.13 or higher.
    * [**pipenv**](https://pipenv.pypa.io/en/latest/installation.html): For dependency management.
    * [**Google Cloud SDK**](https://cloud.google.com/sdk/docs/install): The `gcloud` command-line tool, configured and authenticated.
* **Billing Data in BigQuery**: You must have your Cloud Billing data exporting to a BigQuery dataset. See the prerequisite section below for instructions.

### APIs
The following APIs must be enabled in your project:

* Cloud Functions API: `cloudfunctions.googleapis.com`
* Cloud Run Admin API: `run.googleapis.com`
* Cloud Build API: `cloudbuild.googleapis.com`
* Cloud Scheduler API: `cloudscheduler.googleapis.com`
* Cloud Resource Manager API: `cloudresourcemanager.googleapis.com`
* BigQuery API: `bigquery.googleapis.com`
* Identity and Access Management (IAM) API: `iam.googleapis.com`

You can run the following `gcloud` command to enable all these APIs at once.

Replace `<YOUR-PROJECT-ID>` with your actual project ID.
```bash
export PROJECT_ID=<YOUR-PROJECT-ID>

gcloud services enable \
    cloudfunctions.googleapis.com \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    cloudscheduler.googleapis.com \
    cloudresourcemanager.googleapis.com \
    bigquery.googleapis.com \
    iam.googleapis.com \
    --project ${PROJECT_ID}
```
### Required IAM Roles

To successfully deploy and run the Zombie Projects Watcher, the following IAM roles are required. They should be granted to the appropriate principal (user or service account).

#### For the Deployer Account

The user that runs the `gcloud functions deploy` command needs the following roles on the project:

* **Cloud Functions Admin** (`roles/cloudfunctions.admin`): To deploy and manage the Cloud Function itself.
* **Cloud Run Admin** (`roles/run.admin`): As 2nd gen functions run on Cloud Run, this is needed to manage the underlying service.
* **Service Account User** (`roles/iam.serviceAccountUser`): Required to grant the function permission to act as its designated service account.

You can run the following commands to assign roles to the user:

```bash
export PROJECT_ID="your-gcp-project-id"
export DEPLOYER_USER_EMAIL="user-you-deploy-with@example.com"
export SA_EMAIL="your-sa@your-gcp-project-id.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="user:${DEPLOYER_USER_EMAIL}" \
    --role="roles/cloudfunctions.admin"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="user:${DEPLOYER_USER_EMAIL}" \
    --role="roles/run.admin"

gcloud iam service-accounts add-iam-policy-binding ${SA_EMAIL} \
    --member="user:${DEPLOYER_USER_EMAIL}" \
    --role="roles/iam.serviceAccountUser"
```

#### For the Service Account

The service account that the function uses to execute needs the following roles to access other Google Cloud APIs:

* **Viewer** (`roles/viewer`) granted at the **Organization level**: To list all projects, folders, and get IAM policies to identify owners.
* **BigQuery User** (`roles/bigquery.user`) granted at the **Project level**: To execute cost-related queries on the billing export dataset.
* **Cloud Run Invoker** (`roles/run.invoker`): granted at the **Project level**: To make authenticated calls to the Cloud Run service endpoint.

You can run the following commands to assign roles to the service account:

```bash
export ORG_ID="your-organization-id"
export PROJECT_ID="your-gcp-project-id"
export SA_EMAIL="your-sa@your-gcp-project-id.iam.gserviceaccount.com"

gcloud organizations add-iam-policy-binding ${ORG_ID} \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/viewer"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/bigquery.user"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/run.invoker"
```

## Prerequisite: Setting Up Billing Data in BigQuery

The tool's ability to report on costs depends on having access to your detailed billing data. This is achieved by exporting your Cloud Billing data to a BigQuery dataset and then creating a specific `VIEW` for the tool to query.

### Step 1: Enable Cloud Billing Export to BigQuery

If you haven't done so already, you need to enable the detailed billing data export. This process sends a daily record of your Google Cloud usage and costs to a BigQuery dataset you specify.

For detailed instructions, follow the official Google Cloud guide: [Set up Cloud Billing data export to BigQuery](https://cloud.google.com/billing/docs/how-to/export-data-bigquery).

### Step 2: Create the Cost Aggregation View

Once your billing data is exporting, create a BigQuery `VIEW`. A view is a virtual table based on the result of an SQL query. This provides a simplified and efficient way for the bot to get the exact cost data it needs.

1.  Navigate to the **BigQuery** section in the Google Cloud Console.
2.  Select the project where your billing export is located.
3.  Open the SQL query editor.
4.  Paste the query below, making sure to **update the table name in the `FROM` clause** to match your billing export table.
5.  Click **"Save"** and choose **"Save view"**. Give it the name that you will later specify in your `config.yaml` (e.g., `costs_per_project`).

**SQL Query to Create the View:**

```sql
SELECT
    '<billing-account-name>' AS billing_account_name
,   billing_account_id
,   project.id AS project_id
,   ROUND(SUM(cost), 2) AS cost_generated
,   currency
,   DATE_SUB(DATE_TRUNC(current_date, MONTH), INTERVAL 1 MONTH) AS cost_reference_start_date
FROM
    `<Your-big-query-table>`
WHERE
    project.id IS NOT NULL
    AND PARSE_DATE("%Y-%m-%d", FORMAT_TIMESTAMP("%Y-%m-%d", usage_start_time))
          >= DATE_SUB(DATE_TRUNC(current_date, MONTH), INTERVAL 1 MONTH)
GROUP BY
    billing_account_name
,   billing_account_id
,   project.id
,   currency
,   cost_reference_start_date
```

## Configuration

The tool's behavior is controlled entirely by the `config.yaml` file. To get started, copy the example file.

**Command:**

```bash
cp example-config.yaml config.yaml
```

Next, edit `config.yaml` with your specific information.

### `config.yaml` Details

This file defines the filters for finding projects, notification integrations, and data sources.

#### `filters` section

Defines the criteria for selecting projects to be analyzed.

  * `orgs`: (Required) A list of numeric Google Cloud organization IDs you wish to monitor.
  * `age_minimum_days`: (Required) The minimum age, in days, a project must be to be considered a "zombie".
  * `users_regex`: (Optional) A list of regular expressions (regex) to exclude projects owned by certain users. Useful for ignoring projects from management accounts or executives.
  * `projects`: (Optional) A list of specific project IDs to ignore during the check.

#### `org_info` section

  * `activate`: Set to `true` to enable the bot to fetch and display the full folder path of the project in notifications.

#### `chat` section

Configures Google Chat notifications.

  * `activate`: Set to `true` to enable the integration.
  * `print_only`: If `true`, messages will only be printed to the log and not sent. Useful for debugging.
  * `webhook_url`: The webhook URL for the Google Chat space where messages will be sent.
  * `cost_min_to_notify`: The minimum amount (in USD) a project must have cost (since the previous month) for a notification to be sent.
  * `cost_alert_threshold`: A cost value that, if exceeded, adds an alert emoji to the message.
  * `cost_alert_emoji`: The emoji to use for the cost alert. Use the Unicode hex code (e.g., `'0x1F631'` for 😱).
  * `users_mapping`: Maps a Google Cloud username (e.g., `johndoe`) to a Chat username (e.g., `john.doe`) so that mentions (`@`) work correctly.

#### `billing` section

Points to your billing data source.

  * `activate`: Set to `true` to include cost information in notifications.
  * `bigquery_client_project`: The project ID where your BigQuery billing export dataset is located.
  * `cost_view_full_name`: The full name of the BigQuery view you created in the prerequisite step (format: `project.dataset.view_name`).

#### `org_names_mapping` section

Creates human-readable aliases for your numeric organization IDs.

**Example:**

```yaml
org_names_mapping:
  '1055058813388': 'My Tech Company'
```

This will cause messages to display "My Tech Company" instead of the numeric ID.

## Inputs and Outputs

### Inputs

1.  **Configuration**: The fully populated `config.yaml` file.
2.  **Google Cloud Data**:
      * The list of projects, folders, and organizations obtained via the Cloud Resource Manager API.
      * Cost data obtained from your billing export view in BigQuery.

### Outputs

1.  **Google Chat Notifications**: Formatted messages sent to the owners of projects that meet the "zombie" criteria. The message includes:
      * Owner's name.
      * A list of problematic projects.
      * The full project path (if `org_info` is active).
      * The project's age in days.
      * The project's cost since the previous month.
      * An alert emoji if the cost exceeds `cost_alert_threshold`.
2.  **(Optional) JSON Dump File**: If the `dump_json_file_name` key is set in `config.yaml`, a JSON file containing all enriched project data will be saved locally.

## Installation and Usage

### 1\. Install Dependencies

Clone the repository, install dependencies using `pipenv`, and create your configuration file from the example.

```bash
pipenv install --ignore-pipfile --dev
cp example-config.yaml config.yaml
```

### 2\. Usage as a Local Command (CLI)

For testing and manual runs, you can execute the script directly from your machine.

**Authentication:**
First, authenticate your user account so the script has the necessary permissions.

```bash
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```


**Execution:**
Use `pipenv` to run the main script within the correct virtual environment.

```bash
pipenv run python main.py
```

### 3\. Deployment as a Google Cloud Function

For automation, the recommended method is to deploy the code as a Cloud Function.

**Deploy Command:**
Run the command below in your terminal from the project's root folder. Replace the values as needed.

```bash
gcloud functions deploy YOUR_FUNCTION_NAME \
    --entry-point=http_request \
    --runtime python313 \
    --trigger-http \
    --service-account=YOUR_SERVICE_ACCOUNT@YOUR_PROJECT.iam.gserviceaccount.com \
    --timeout=600
```

  * `YOUR_FUNCTION_NAME`: The name you want to give your function (e.g., `zombie-project-bot`).
  * `YOUR_SERVICE_ACCOUNT`: The service account the function will use to run. It needs the required IAM permissions (e.g., Viewer, BigQuery User).
  * `--timeout`: Increases the function's timeout (in seconds) to prevent "timeout" errors in environments with many projects.


### 4\. Scheduling Automatic Execution:

After deployment, use Cloud Scheduler to create a job that calls your function's URL on your desired schedule. To ensure the function can only be triggered by the scheduler, deploy it as private (the default) and use OIDC authentication.

Scheduler Creation Command:
Run the gcloud command below to create a job that runs every day at 1 PM. Remember to replace the placeholder values.

```bash
gcloud scheduler jobs create http YOUR_JOB_NAME \
    --schedule="0 13 * * *" \
    --time-zone="America/Sao_Paulo" \
    --location=YOUR_FUNCTION_REGION \
    --uri="YOUR_FUNCTION_TRIGGER_URL" \
    --http-method=POST \
    --oidc-service-account-email="YOUR_SERVICE_ACCOUNT@YOUR_PROJECT.iam.gserviceaccount.com"
```


* `YOUR_JOB_NAME:` A name for your scheduler job (e.g., zombie-project-bot-trigger).
* `YOUR_FUNCTION_REGION:` The region where you deployed your function (e.g., us-central1).
* `YOUR_FUNCTION_TRIGGER_URL:` The trigger URL provided after a successful deployment.
* `YOUR_SERVICE_ACCOUNT:` The same service account used to deploy the function. It will need the Cloud Run Invoker role to have permission to trigger the function.