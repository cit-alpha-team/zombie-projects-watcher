# Zombie Projects Watcher

## Introduction

Zombie Projects Watcher is an automation tool designed to help engineering and finance teams control infrastructure costs on Google Cloud. It identifies potentially unused ("zombie") projects based on criteria such as age and cost, and proactively notifies the owners via Google Chat, encouraging clean-up and reducing waste.

The entire infrastructure is deployed and managed using **Terraform**. While the Terraform script prepares a GCS bucket for future dynamic configuration, the function currently reads its settings from a `config.yaml` file bundled with its source code.

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
    * [**Terraform**](https://learn.hashicorp.com/tutorials/terraform/install-cli): Version 1.0 or higher.
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
* Secret Manager API: `secretmanager.googleapis.com`
* Cloud Storage API: `storage.googleapis.com`

You can run the following `gcloud` command to enable all these APIs at once.
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
    secretmanager.googleapis.com \
    storage.googleapis.com \
    --project ${PROJECT_ID}
```

### Required IAM Roles

The Terraform script will automatically create a service account and assign it all the necessary project-level and organization-level roles.

**Important:** The user or service account running `terraform apply` must have sufficient permissions to create service accounts (`roles/iam.serviceAccountAdmin`) and set IAM policies on the project and organization (`roles/resourcemanager.projectIamAdmin`, `roles/resourcemanager.organizationAdmin`).

The following roles will be assigned to the bot's service account by Terraform:

* **Organization Viewer** (`roles/viewer`): To list all projects across the organization.
* **BigQuery User** (`roles/bigquery.user`): To execute cost-related queries on the billing export dataset.
* **Cloud Run Invoker** (`roles/run.invoker`): To make authenticated calls from Cloud Scheduler.
* **Secret Manager Secret Accessor** (`roles/secretmanager.secretAccessor`): To access the webhook URL secret.
* **Storage Object Viewer** (`roles/storage.objectViewer`): Provisioned by Terraform for future use (dynamic configuration from GCS).


## Prerequisite: Setting Up Billing Data in BigQuery

The tool's ability to report on costs depends on having access to your detailed billing data. This is achieved by exporting your Cloud Billing data to a BigQuery dataset.

### Step 1: Enable Cloud Billing Export to BigQuery

If you haven't done so already, you need to enable the detailed billing data export. This process sends a daily record of your Google Cloud usage and costs to a BigQuery dataset you specify.

For detailed instructions, follow the official Google Cloud guide: [Set up Cloud Billing data export to BigQuery](https://cloud.google.com/billing/docs/how-to/export-data-bigquery).

### Step 2: Identify the Billing Export Table Name

Once your billing data is exporting, locate and copy the full name of the table created by the export process. This is the name you will specify in your `config.yaml`.

The format is typically `project-id.dataset_name.gcp_billing_export_v1_XXXXXX_XXXXXX_XXXXXX`.

*(Optional) For advanced use cases where you prefer to use a pre-aggregated summary, you can create a BigQuery `VIEW` and point the configuration to it. An example query for creating such a view can be found in the `example-bigquery-billing-costs-view.sql` file.*

## Configuration

The tool's behavior is controlled entirely by the `config.yaml` file located in the **root of the project**. For now, this file is bundled directly with the function's source code during deployment.

*Note: The Terraform script also uploads this file to a GCS bucket to prepare for a future enhancement where the configuration can be updated dynamically without redeploying the function.*

### `config.yaml` Details

This file defines the filters for finding projects, notification integrations, and data sources.

#### `filters` section

Defines the criteria for selecting projects to be analyzed.

  * `orgs`: (Required) A list of numeric Google Cloud organization IDs you wish to monitor.
  * `age_minimum_days`: (Required) The minimum age, in days, a project must be to be considered a "zombie".
  * `age_maximum_days`: (Optional) Defines the time window, in days, for cost calculation (e.g., `180` calculates costs for the last 180 days). Set to `0` to use the default behavior (costs since the beginning of the previous month).
  * `users_regex`: (Optional) A list of regular expressions (regex) to exclude projects owned by certain users.
  * `projects`: (Optional) A list of specific project IDs to ignore during the check.
#### `org_info` section

  * `activate`: Set to `true` to enable the bot to fetch and display the full folder path of the project in notifications.

#### `chat` section

Configures Google Chat notifications.

  * `activate`: Set to `true` to enable the integration.
  * `print_only`: If `true`, messages will only be printed to the log and not sent.
  * `secret_manager`: (Required if `chat.activate` is `true`) Configuration to fetch the webhook URL from Google Secret Manager.
    * `project_id`: The project ID where your secret is stored.
    * `secret_id`: The name of the secret containing the webhook URL.
    * `version_id`: The version of the secret to use (e.g., `latest`).
  * `cost_min_to_notify`: The minimum amount (in USD) a project must have cost for a notification to be sent.
  * `cost_alert_threshold`: A cost value that, if exceeded, adds an alert emoji to the message.
  * `cost_alert_emoji`: The emoji to use for the cost alert. Use the Unicode hex code (e.g., `'0x1F631'` for 😱).
  * `users_mapping`: Maps a Google Cloud username (e.g., `johndoe`) to a Chat username (e.g., `john.doe`).

#### `billing` section

Points to your billing data source.

  * `activate`: Set to `true` to include cost information in notifications.
  * `bigquery_client_project`: The project ID where your BigQuery billing export dataset is located.
  * `billing_export_table_name`: (Required if `billing.activate` is `true`) The full name of your BigQuery table containing the detailed billing export data (format: `project.dataset.table_name`).

#### `org_names_mapping` section

Creates human-readable aliases for your numeric organization IDs.

## Deployment with Terraform

### 1. Initial Setup

1.  **Create State Bucket:** Terraform needs a GCS bucket to store its state file. This is a one-time manual setup. Choose a globally unique name.
    ```bash
    gsutil mb gs://<CHOOSE-A-UNIQUE-BUCKET-NAME-FOR-TERRAFORM-STATE>
    ```

2.  **Configure Backend:** In the `infra/` directory, open `backend.tf` and update the `bucket` attribute with the name of the bucket you just created.

3.  **Configure Variables:** In the `infra/` directory, copy the example variables file:
    ```bash
    cp terraform.tfvars.example terraform.tfvars
    ```
    Then, open `terraform.tfvars` and fill in your project's specific values (`project_id`, `organization_id`, `chat_webhook_url`)

### 2. Deploy

1.  **Initialize Terraform:** From inside the `infra/` directory, run:
    ```bash
    terraform init
    ```
2.  **Plan and Apply:** Review the plan and apply the changes to deploy all resources.
    ```bash
    terraform plan
    terraform apply
    ```

## Inputs and Outputs

### Inputs

1.  **Configuration**: The `config.yaml` file, which is bundled with the function source code.
2.  **Google Cloud Data**:
      * The list of projects, folders, and organizations obtained via the Cloud Resource Manager API.
      * Cost data obtained from your billing export table in BigQuery.

### Outputs

1.  **Google Chat Notifications**: Formatted messages sent to the owners of projects that meet the "zombie" criteria. The message includes:
      * Owner's name.
      * A list of problematic projects.
      * The project's age in days.
      * The project's cost within the configured time window.
2.  **(Optional) JSON Dump File**: If the `dump_json_file_name` key is set in `config.yaml`, a JSON file with enriched project data will be saved locally when running in CLI mode.

## Local Development

For testing and manual runs, you can execute the script directly from your machine. The local script will read the `config.yaml` from the project root.

1.  **Install Dependencies:**
    ```bash
    pipenv install --ignore-pipfile --dev
    ```
2.  **Authenticate:**
    ```bash
    gcloud auth application-default login
    ```
3.  **Execute:**
    ```bash
    pipenv run python main.py
    ```
