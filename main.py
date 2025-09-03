import logging
import logging.config
import json
from pprint import pformat
from datetime import datetime as dt
import traceback as tb
from googleapiclient import discovery
from google.cloud import asset_v1
from google.api_core.exceptions import Forbidden

from logging_config import setup_logging
import functions_framework

setup_logging()
logger = logging.getLogger(__name__)

from config import CONFIG
from utils import (
    extract_username,
    group_projects_by_owner
)
from filters import (
    filter_projects_matching_org_level,
    filter_older_than,
    filter_owners,
    filter_users,
    filter_whitelisted_projects,
    filter_whitelisted_users
)
from billing import query_billing_info
# from slack import send_messages_to_slack
from chat import send_messages_to_chat


ORGS_FILTER = CONFIG['filters']['orgs'].get()
PROJECTS_FILTER = CONFIG['filters']['projects'].get() or []
USERS_REGEX_FILTER = CONFIG['filters']['users_regex'].get() or []
AGE_MINIMUM_DAYS_FILTER = CONFIG['filters']['age_minimum_days'].get(int)
SLACK_ACTIVATED = CONFIG['slack']['activate'].get(bool)
CHAT_ACTIVATED = CONFIG['chat']['activate'].get(bool)
BILLING_ACTIVATED = CONFIG['billing']['activate'].get(bool)
DUMP_JSON_FILE_NAME = CONFIG['dump_json_file_name'].get()
ORGS_ACTIVATED = CONFIG['org_info']['activate'].get(bool)

DEBUG_ENRICHED_PROJECTS = CONFIG['debug']['enriched_projects'].get(bool)
DEBUG_FILTERED_BY_PROJECTS = CONFIG['debug']['filtered_by_projects'].get(bool)
DEBUG_FILTERED_BY_USERS = CONFIG['debug']['filtered_by_users'].get(bool)
DEBUG_FILTERED_BY_AGE = CONFIG['debug']['filtered_by_age'].get(bool)
DEBUG_GROUPED_BY_OWNERS = CONFIG['debug']['grouped_by_owners'].get(bool)
DEBUG_FILTERED_BY_ORGS = CONFIG['debug']['filtered_by_org'].get(bool)

@functions_framework.http
def http_request(request):
    now = dt.now()
    date_value = dt.strftime(now, "%Y-%m-%dT%H:%M:%S.%fZ")
    message = ''
    status_code = ''
    try:
        message, status_code =  main()
    except Exception as err:
        logging.exception(err)
        exception_message =  tb.format_exc().splitlines()
        message = exception_message[-1].capitalize()
        message = message.replace('<',' ')
        message = message.replace('>',' ')
        message = 'An error occurred. Details: ' + message
        for item in message.split():
            if item.isnumeric():
               status_code = item
            else:
                status_code = 500
    finally:
        message = (message + ' on ' +  date_value + '!')
    return message, status_code

def main():
    asset_client = asset_v1.AssetServiceClient()

    logger.info('Building folder ID to Name map.')
    folder_map = _get_folder_display_names(asset_client, ORGS_FILTER)

    logger.info('Retrieving Projects.')
    active_projects = _get_projects(asset_client, ORGS_FILTER)

    logger.info('Calculating Project age information.')
    enriched_projects = _enrich_project_info_with_age(active_projects)

    logger.info('Retrieving Project owners information.')
    enriched_projects = _enrich_project_info_with_owners(asset_client, enriched_projects)
    
    if ORGS_ACTIVATED:
        logger.info('Retrieving Project organization information.')
        enriched_projects = _enrich_project_info_with_org_and_path(asset_client, enriched_projects, folder_map)
    else:
        logger.info('Project organization information is not active.')

    if BILLING_ACTIVATED:
        logger.info('Retrieving Project cost information.')
        enriched_projects = _enrich_project_info_with_costs(enriched_projects)
    else:
        logger.info('Project cost information is not active.')

    if DEBUG_ENRICHED_PROJECTS:
        logger.debug('Projects with enriched information:\n%s', pformat(enriched_projects))

    if DUMP_JSON_FILE_NAME:
        logger.debug('Dumping info to JSON file %s.', DUMP_JSON_FILE_NAME)
        with open(DUMP_JSON_FILE_NAME, 'w') as fp:
            json.dump(enriched_projects, fp, indent=2, sort_keys=True)

    logger.info('Filtering Projects by project.')
    project_filtered = [
        p for p in enriched_projects
        if p.get('name', '').split('/')[-1] not in PROJECTS_FILTER
    ]


    if DEBUG_FILTERED_BY_PROJECTS:
        logger.debug('Project filter applied:\n%s', pformat(project_filtered))

    logger.info('Filtering Projects by user.')
    user_filtered = list(filter(filter_whitelisted_users(
        USERS_REGEX_FILTER), project_filtered))

    if DEBUG_FILTERED_BY_USERS:
        logger.debug('User filter applied:\n%s', pformat(user_filtered))

    logger.info('Filtering Projects by age.')
    older_projects = list(filter(filter_older_than(
        AGE_MINIMUM_DAYS_FILTER), user_filtered))

    if DEBUG_FILTERED_BY_AGE:
        logger.debug('Aged Projects filter applied:\n%s', pformat(older_projects))

    logger.info('Filtering Projects by org level.')

    org_projects = list(filter(filter_projects_matching_org_level(
        ORGS_FILTER), older_projects))

    if DEBUG_FILTERED_BY_ORGS:
        logger.debug('Project by orgs:\n%s', pformat(org_projects))

    logger.info('Grouping Projects by owner(s).')
    projects_by_owner = group_projects_by_owner(org_projects)

    if DEBUG_GROUPED_BY_OWNERS:
        logger.debug('Project by owner:\n%s', pformat(projects_by_owner))

    if SLACK_ACTIVATED:
        logger.info('Sending Slack messages.')
        # send_messages_to_slack(projects_by_owner)
        logger.info('All messages sent.')
    else:
        logger.info('Slack integration is not active.')

    if CHAT_ACTIVATED:
        logger.info('Sending Chat messages.')
        send_messages_to_chat(projects_by_owner)
        logger.info('All messages sent.')
    else:
        logger.info('Chat integration is not active.')

    logger.info('Happy Friday! :)')

    response_message = "Success "
    response_code = 200

    return response_message, response_code

def _get_projects(asset_client, orgs):
    all_projects = []
    for org_id in orgs:
        scope = f"organizations/{org_id}"
        try:
            response = asset_client.search_all_resources(
                request={
                    "scope": scope,
                    "asset_types": ["cloudresourcemanager.googleapis.com/Project"],
                    "read_mask": "name,createTime,project,organization,folders,displayName",
                }
            )
            for resource in response:
                project = {
                    'name': resource.name,
                    'projectId': resource.project,
                    'displayName': resource.display_name,
                    'createTime': resource.create_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                    'organization': resource.organization,
                    'folders': resource.folders,
                }
                all_projects.append(project)
        except Exception as e:
            logger.error(f"Error fetching projects in organization {org_id} with Cloud Asset: {e}")
    return all_projects

def _enrich_project_info_with_owners(asset_client, projects):
    for project in projects:
        project_id_value = project.get('projectId')
        project['vpc_blocked'] = False
        if project_id_value.startswith('projects/'):
            project_id_value = project_id_value.split('/')[-1]

        scope = f"projects/{project_id_value}"
        owners_list = []

        try:
            response = asset_client.search_all_iam_policies(
                request={"scope": scope, "query": "policy:roles/owner"}
            )
            for policy in response:
                for binding in policy.policy.bindings:
                    if binding.role == "roles/owner":
                        for member in binding.members:
                            if member.startswith("user:"):
                                owners_list.append(member.removeprefix("user:"))
        except Forbidden as e:
            if "vpcServiceControlsUniqueIdentifier" in str(e):
                logger.warning(f"Project {project_id_value} is protected by VPC-SC. Could not fetch owners.")
                project['vpc_blocked'] = True
            else:
                logger.error(f"Permission error when fetching owners for project {project_id_value}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error when fetching owners for project {project_id_value}: {e}")

        project['owners'] = list(set(owners_list))
        project['owners_id'] = _get_owners_id(project.get('owners'))
        logger.debug('Owners for Project %s: %s', project_id_value, project.get('owners'))
    return projects

def _enrich_project_info_with_age(projects):
    for project in projects:
        project['createdDaysAgo'] = _get_created_days_ago(project)
    return projects

def _enrich_project_info_with_costs(projects):
    costs_by_project = query_billing_info()
    for project in projects:
        project_name_full = project.get('name', '')
        project_id_for_billing = project_name_full.split('/')[-1]
        project['costSincePreviousMonthFull'] =\
            _get_cost_since_previous_month_full(costs_by_project, project_id_for_billing)
        project['costSincePreviousMonth'] =\
            _get_cost_since_previous_month_value(costs_by_project, project_id_for_billing)
        project['costCurrency'] =\
            _get_cost_currency(costs_by_project, project_id_for_billing)
        project['costBillingAccountName'] =\
            _get_cost_billing_account_name(costs_by_project, project_id_for_billing)
        project['costBillingAccountId'] =\
            _get_cost_billing_account_id(costs_by_project, project_id_for_billing)

        logger.debug('Cost for Project %s: %s %s (Billing account: %s, Id: %s)',
            project_id_for_billing, project.get('costSincePreviousMonth'),
            project.get('costCurrency'), project.get('costBillingAccountName'),
            project.get('costBillingAccountId'))
    return projects

def _enrich_project_info_with_org_and_path(asset_client, projects, folder_map):
    for project in projects:
        project['org'] = project.get('organization', '').split('/')[-1]
        folder_ids = [f.split('/')[-1] for f in project.get('folders', [])]
        folder_names = [folder_map.get(fid, fid) for fid in folder_ids]
        project['path'] = '/'.join(reversed(folder_names)) + '/' if folder_names else ''

        logger.debug('Organization root for Project %s: %s', project.get('projectId'), project.get('org'))
        logger.debug('Path for Project %s: %s', project.get('projectId'), project.get('path'))
    return projects

def _get_cost_since_previous_month_full(costs_by_project, project_id):
    cost = costs_by_project.get(project_id, {})
    return cost


def _get_cost_since_previous_month_value(costs_by_project, project_id):
    cost = _get_cost_since_previous_month_full(costs_by_project, project_id)
    if not cost:
        return 0.0
    else:
        return cost.get('costGenerated', 0.0)


def _get_cost_currency(costs_by_project, project_id):
    cost = _get_cost_since_previous_month_full(costs_by_project, project_id)
    if not cost:
        return '$'
    else:
        return cost.get('currency', '$')


def _get_cost_billing_account_name(costs_by_project, project_id):
    cost = _get_cost_since_previous_month_full(costs_by_project, project_id)
    if not cost:
        return 'Unknown'
    else:
        return cost.get('billingAccountName', 'Unknown')


def _get_cost_billing_account_id(costs_by_project, project_id):
    cost = _get_cost_since_previous_month_full(costs_by_project, project_id)
    if not cost:
        return 'Unknown'
    else:
        return cost.get('billingAccountId', 'Unknown')


def _get_owners_id(owners):
    usernames = set([extract_username(user) for user in owners])
    return list(usernames)

def _get_folder_display_names(asset_client, orgs):
    folder_map = {}
    for org_id in orgs:
        scope = f"organizations/{org_id}"
        try:
            response = asset_client.search_all_resources(
                request={
                    "scope": scope,
                    "asset_types": ["cloudresourcemanager.googleapis.com/Folder"],
                    "read_mask": "name,displayName",
                }
            )
            for resource in response:
                folder_id = resource.name.split('/')[-1]
                folder_map[folder_id] = resource.display_name
        except Exception as e:
            logger.error(f"Erro ao buscar as pastas na organização {org_id}: {e}")
    return folder_map


def _get_created_days_ago(project):
    now = dt.now()
    create_time = project.get('createTime')
    create_date_value = dt.strptime(create_time, "%Y-%m-%dT%H:%M:%S.%fZ")
    delta = now - create_date_value
    return delta.days


if __name__ == '__main__':
    main()

