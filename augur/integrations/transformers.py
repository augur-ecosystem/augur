import arrow
from jira import Issue

import augur
from augur.common import deep_get
from augur.integrations.uajira import get_jira
from augur.models.staff import Staff
from augur.models.ticket import Ticket, TicketType


def transform_issuetype_to_augur_ticket_type(issuetype):
    if not issuetype:
        return None

    type = TicketType()
    type.id = issuetype['id']
    type.name = issuetype['name']
    type.is_child = issuetype['subtask']

    type_map = {
        "Sub-Task": Ticket.SubTask,
        "Bug": Ticket.Bug,
        "Story": Ticket.Story,
        "Task": Ticket.Task,
        "Epic": Ticket.Epic,
    }

    # default to a task if the type is not in the map and it's a parent type, Subtask otherwise.
    type.type = type_map[issuetype['name']] if issuetype['name'] in type_map else \
        Ticket.SubTask if type.is_child else Ticket.Task

    return type


def transform_jira_user_to_augur_staff(user):

    if not user:
        return None

    if not isinstance(user, dict):
        raise TypeError("User is expected to be a dictionary object")

    staff = Staff()
    staff.jira_username = user['name']
    staff.email = user['emailAddress']

    try:
        # try to split into two names assuming the first name is first.
        staff.first_name,staff.last_name = user['displayName'].split(" ")
    except:
        # otherwise just set first name to entire string
        staff.first_name = user['displayName']

    staff.avatar_url = user['avatarUrls']['48x48']
    return staff


def transform_jira_issue_to_augur_ticket(issue):

    jira = get_jira()

    ticket = Ticket()
    if isinstance(issue, Issue):
        # convert to raw format (dictionary)
        issue = issue.raw

    story_point_field = jira.get_issue_field_from_custom_name("Story Points")
    dev_team_field = jira.get_issue_field_from_custom_name("Dev Team")

    ticket.summary = issue.get('summary',"")
    ticket.description = deep_get(issue, 'fields','description')
    ticket.points = deep_get(issue,'fields',story_point_field)

    jira_issue_type = deep_get(issue,'fields','issuetype')
    if jira_issue_type:
        ticket.type = transform_issuetype_to_augur_ticket_type(jira_issue_type)

    team_name = deep_get(issue,'fields',dev_team_field)
    if team_name:
        ticket.team = augur.api.get_team_from_name(team_name)

    ticket.assignee = transform_jira_user_to_augur_staff(issue['assignee'])
    ticket.reporter = transform_jira_user_to_augur_staff(issue['reporter'])

    try:
        ticket.created = arrow.get(deep_get(issue,'created'))
    except TypeError:
        ticket.created = None

    try:
        ticket.updated = arrow.get(deep_get(issue,'updated'))
    except TypeError:
        ticket.updated = None

    ticket.labels = deep_get(issue,'labels') or []

    for subtask in issue['subtasks']:
        ticket.subtasks.append(transform_jira_issue_to_augur_ticket(subtask))


def issue_list_to_augur_ticket_list(issues):
    """
    Converts a list of Jira issues into a list of augur issues.  
    :param issues: The list of jira issues.  This can be a collection of Issue objects
        or a list of issue dicts.
    :return: Returns a list of Ticket objects.
    """
    return map(lambda x: transform_jira_issue_to_augur_ticket(x), issues)


