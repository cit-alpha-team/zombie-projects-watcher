import os
import json
import logging
import requests
from pprint import pformat
from config import CONFIG
from datetime import datetime as dt
import time
from google.cloud import secretmanager

logger = logging.getLogger(__name__)


ORGS_NAME_MAPPING = CONFIG['org_names_mapping'].get()
CHAT_ACTIVATED = CONFIG['chat']['activate'].get(bool)
USERS_MAP = CONFIG['chat']['users_mapping'].get()
PRINT_ONLY = CONFIG['chat']['print_only'].get(bool)
COST_ALERT_THRESHOLD = CONFIG['chat']['cost_alert_threshold'].get(float)
COST_ALERT_EMOJI = CONFIG['chat']['cost_alert_emoji'].get()
COST_MIN_TO_NOTIFY = CONFIG['chat']['cost_min_to_notify'].get(float)

def get_webhook_url_from_secret_manager():
    """Fetches the webhook URL from Google Secret Manager."""
    secret_manager_config = CONFIG['chat']['secret_manager']
    project_id = secret_manager_config['project_id'].get()
    secret_id = secret_manager_config['secret_id'].get()
    version_id = secret_manager_config['version_id'].get()

    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")

def send_message(message):
    try:
        webhook_url = get_webhook_url_from_secret_manager()
    except Exception as e:
        logger.error("Failed to get webhook URL from Secret Manager: %s", e)
        return

    logger.info('Sending Chat message:\n%s', message)
    if PRINT_ONLY:
        return
    message_headers = {'Content-Type': 'application/json; charset=UTF-8'}
    message_data = {
        'text': message
    }
    message_data_json = json.dumps(message_data, indent=2)
    response = requests.post(
        webhook_url, data=message_data_json, headers=message_headers)
    if response.status_code != 200:
        logger.error('Error sending message to Chat. Error: %s, Response: %s', response.status_code, pformat(response.text))


def _get_message(user_to_mention):
    if user_to_mention == 'NO_OWNER':
        return "I've noticed there are no owners for the following projects:\n\n"
    return "Hey *@{}*, I've noticed you are one of the owners of the following projects:\n\n".format(user_to_mention)


def send_messages_to_chat(projects_by_owner):
    number_of_notified_projects = 0
    total_cost_of_notified_projects = 0.0
    if not CHAT_ACTIVATED:
        logger.info('Chat integration is not active.')
        return

    for owner in projects_by_owner.keys():
        user_to_mention = USERS_MAP.get(owner, owner)
        message = _get_message(user_to_mention)
        send_message_to_this_owner = False
        sorted_projects = sorted(projects_by_owner.get(owner), key=lambda p: p.get('costSincePreviousMonth', 0.0), reverse=True)
        for project in sorted_projects:    
            project_id = project.get('projectId')
            org = ORGS_NAME_MAPPING.get(project.get('org'))
            path = project.get('path')
            created_days_ago = int(project.get('createdDaysAgo'))
            cost = project.get('costSincePreviousMonth', 0.0)
            currency = project.get('costCurrency', '$')
            emoji = ''
            emoji_codepoint = chr(int(COST_ALERT_EMOJI, base = 16))
            cost_alert_emoji = "{} ".format(emoji_codepoint)
            if cost <= COST_MIN_TO_NOTIFY:
                logger.debug('- `{}/{}`, will not be in the message, due to its cost being lower than the minimum warning value'\
                    .format(owner, project_id))
            else:
                if cost > COST_ALERT_THRESHOLD:
                    emoji = ' ' + cost_alert_emoji
                send_message_to_this_owner = True
                message += "`{}/{}{}` created `{} days ago`, costing *`{}`* {}.{}\n\n"\
                    .format(org, path, project_id, created_days_ago, cost, currency, emoji)
                number_of_notified_projects = number_of_notified_projects + 1
                total_cost_of_notified_projects += cost
        message += "\nIf these projects are not being used anymore, please consider `deleting them to reduce infra costs` and clutter."

        if send_message_to_this_owner:
            send_message(message)
            time.sleep(1)

    today_weekday=dt.today().strftime('%A')
    final_of_execution_message = f'''Happy {today_weekday}!
Today I found *{number_of_notified_projects} projects* with costs higher
than the defined notification threshold of ${COST_MIN_TO_NOTIFY} 🪙, totaling *${total_cost_of_notified_projects:.2f}*.

*Note*: Including only costs from the beginning of the previous month.'''
    send_message(final_of_execution_message)
