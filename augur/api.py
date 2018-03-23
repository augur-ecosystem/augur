"""
AUGUR API

The Augur API provides easy access to some of the most benefecial data 
that can be collected by the library.  While not exhaustive it is meant
to conveniently retrieve the most commonly needed data.

Rather than instantiating data classes or integrations directly, the API 
provides a layer of abstraction in the form of functions.  Data that is 
returned is almost always in the form of a dictionary that can be easily 
converted into JSON as necessary.

Most functions within the api will take an AugurContext object which
defines the constraints within which the data should be retrieved
and interpreted. 

See the Augur readme for some information about how data is organized,
the meaning of groups, workflows, etc.

"""

import datetime
import logging

import copy

from munch import munchify
from pony import orm
from pony.orm import select, delete

from augur import settings
from augur import db
from augur.db import EventLog
from augur.integrations.objects import JiraBoard, BoardMetrics, JiraIssue

CACHE = dict()

__jira = None
__github = None
__context = None

api_logger = logging.getLogger("augurapi")


def set_default_context(context):
    """
    Sets the default context for the API
    :param context: The context object to use by default.
    :return:
    """
    global __context
    __context = context


def get_default_context():
    """
    Returns the default context for the API
    :return: Returns the default context object (AugurContext)
    """
    global __context
    return __context


def get_github():
    """
    Returns the global github integration object
    :return: Returns the global AugurGithub instance
    """
    from augur.integrations.augurgithub import AugurGithub

    global __github
    if not __github:
        __github = AugurGithub()
    return __github


def get_jira():
    """
    Returns the global jira integration object
    :return: Returns the global AugurJira instance
    """
    from augur.integrations.augurjira import AugurJira

    global __jira
    if not __jira:
        __jira = AugurJira()
    return __jira


def get_jira_url():
    return settings.main.integrations.jira.instance


def get_workflow(workflow_id):
    """
    Gets a workflow by ID
    :param workflow_id: The ID of the workflow to retrieve
    :return: Returns a Group object or None if not found
    """
    return db.Workflow[workflow_id]


def get_workflows():
    """
    Get a list of all workflows
    :return: Returns a Group object or None if not found
    """
    return orm.select(w for w in db.Workflow)


def get_group(group_id):
    """
    Gets a group by id
    :param group_id: The ID or name of the group to retrieve
    :return: Returns a Group object or None if not found
    """
    return db.Group[group_id]


def get_groups():
    """
    Gets all groups
    :return: Returns a Group object or None if not found
    """
    return orm.select(g for g in db.Group)[:]


def get_vendors():
    """
    Gets all the vendors stored in the database
    :return: Returns a list of vendors
    """
    return orm.select(v for v in db.Vendor)[:]


def get_issue_details(key):
    """
    Return details about an issue based on an issue key.  This does not pull from any cache.
    :param key: The key of the issue to retrieve
    :return: The issue dict
    """

    issue = JiraIssue(source=get_jira(), key=key)
    if issue.load():
        return issue.issue
    else:
        return None


def get_all_staff(context):
    """
    :param context: The context to use in determining which staff to return (None returns all)
    """
    if not context:
        return orm.select(s for s in db.Staff).order_by(lambda x: x.last_name)[:]
    else:
        context_staff = []
        valid_team_ids = [t.id for t in context.group.teams]
        staff = orm.select(s for s in db.Staff if s.teams)[:]
        for s in staff:
            for t in s.teams:
                if t.id in valid_team_ids:
                    context_staff.append(s)
        return context_staff


def get_staff_member_by_field(first_name=None, last_name=None, email=None, username=None):
    """
    Search for a staff member by fields other than ID.  This will try to match on email first (if given)
    then will try to find it based on first,last name.  First and last name must be given to do the search.
    :param username: One of the stored usernames (e.g. jira or github)
    :param first_name: The first name of the user (if given, last name must also be given)
    :param last_name: The last name of the user (if given, first name must also be given.
    :param email: The email of the user to find.
    :return: Returns a db.Staff object if found, otherwise None.
    """

    def search_by_username():
        try:
            # try searching by first, last name
            return orm.get(s for s in db.Staff if s.github_username == username or
                           s.jira_username == username)
        except (orm.MultipleObjectsFoundError, orm.ObjectNotFound):
            return False

    def search_by_name():
        try:
            # try searching by first, last name
            if first_name and last_name:
                return orm.get(s for s in db.Staff if s.first_name.lower() == first_name.lower() and
                               s.last_name.lower() == last_name.lower())
            elif first_name:
                return orm.get(s for s in db.Staff if s.first_name.lower() == first_name.lower())
            elif last_name:
                return orm.get(s for s in db.Staff if s.last_name.lower() == last_name.lower())

        except (orm.MultipleObjectsFoundError, orm.ObjectNotFound):
            return False

    def search_by_email():
        try:
            # try searching by first, last name
            return orm.get(s for s in db.Staff if s.email.lower() == email.lower())
        except (orm.ObjectNotFound, orm.MultipleObjectsFoundError):
            return False

    result = None
    if username:
        result = search_by_username()

    if not result and email:
        result = search_by_email()

    if not result and (first_name or last_name):
        result = search_by_name()

    return result


def get_team_by_id(team_id):
    """
    Returns a team object keyed on the name of the team.  If there is more than one team with the same name it will
    always returns only 1.  There is no guarantee which one, though.
    :param team_id: The team id to search for
    :return: A Team object.
    """
    return db.Team[team_id]


def get_teams(context=None):
    """
    Retrieves a list of team objects containing all the known teams in e-comm
    :return: An array of Team objects. 
    """
    if not context:
        return select(t for t in db.Team).order_by(lambda x: x.name)[:]
    else:
        return context.group.teams.order_by(lambda x: x.name)


def get_products():
    """
    Retrieves a list of product objects containing all the known product groups in e-comm
    :return: An array of Product objects. 
    """
    return select(p for p in db.Product)


def memory_cache_data(data, key):
    """
    Cache data in memory
    :param data: The data to cache
    :param key: The key to store it under
    :return: Returns the data given in <data>
    """
    global CACHE
    CACHE[key] = copy.deepcopy(data)
    return CACHE[key]


def get_memory_cached_data(key):
    """
    Retrieves data stored in memory under <key>
    :param key: The key to look for in the in-memory cache
    :return: Returns the data or None if not found
    """
    global CACHE
    if key in CACHE:
        return CACHE[key]
    else:
        return None


def get_board_metrics(board_id, context):
    """
    Retrieves information about the backlog  for the given board.
    :param board_id:  The ID of the board to get the backlog from
    :param context: The context to help define how to interpret the data retrieved
    :return: Returns a dict with information about the backlog
    """
    board = JiraBoard(get_jira(), board_id=board_id)
    if board.load():
        metrics = BoardMetrics(context, board)
        return munchify({
            'sprints': metrics.historic_sprint_analysis(),
            'backlog': metrics.backlog_analysis()
        })
    else:
        return None


def get_issue_field_from_custom_name(name):
    """
    Returns the true field name of a jira field based on its friendly name
    :param name: The friendly name of the field
    :return: A string with the true name of a field.
    """
    return get_jira().get_field_by_name(name)


def add_staff(staff_properties):
    """
    Staff properties must include the following:
        * first_name (unicode)
        * last_name (unicode)
        * company (unicode)
        * type (unicode - one of STAFF_TYPES)
        * role (unicode - one of STAFF_ROLES)
        * email (unicode)
        * rate (if consultant)
        * jira_username
        * team (db.Team model)
    :param staff_properties:
    :return: Returns a db.Staff object.
    """
    db.Staff(**staff_properties)
    orm.commit()


def update_staff(staff_id, staff_properties):
    """
    Staff properties can be any subset of the properties that are
    part of the Staff model.
    :param staff_id: The ID of the staff object to update
    :param staff_properties: All or some of the properties in the staff model
    :return:
    """
    s = db.Staff[staff_id]
    if s:
        s.set(**staff_properties)
        orm.commit()
        return s

    return None


def add_team(team_properties):
    """
    Team properties must include the following:
        * name (unicode)
    :param team_properties: At a minimum, contains the required fields necessary to create a team.
    :return: Returns a db.Team object.
    """
    db.Team(**team_properties)
    orm.commit()


def update_team(team_id, team_properties):
    """
    Staff properties can be any subset of the properties that are
    part of the Team model.
    :param team_id: The ID of the team object to update
    :param team_properties: All or some of the properties in the team model
    :return:
    """
    t = db.Team[team_id]
    if t:
        t.set(**team_properties)
        orm.commit()
        return t

    return None


def clear_event_data(days_to_keep=30):
    """
    Remove all logs older than days_to_keep days
    :param days_to_keep: The number of days to keep and remove all other log entries.
    :return: Returns the number of rows deleted
    """
    return delete(
        e for e in EventLog if e.event_time < (datetime.datetime.now() - datetime.timedelta(days=days_to_keep)))


def log_event_data(event_type, event_data):
    """
    Stores a log entry in the database
    :param event_type:
    :param event_data:
    :return:
    """
    event_time = datetime.datetime.now()
    el = EventLog(event_time=event_time, event_type=event_type, event_data=event_data)
    return el is not None
