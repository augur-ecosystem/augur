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

import arrow

import copy

from collections import defaultdict
from jira import JIRAError
from pony import orm
from pony.orm import select, delete
from pony.orm import serialization

from augur import common
from augur.common.cache_store import AugurCachedResultSets

from augur.common import const, cache_store, project_key_from_issue_key
from augur import db
from augur.common.const import SPRINT_SORTBY_ENDDATE
from augur.db import EventLog
from augur.integrations.objects.board import JiraBoard

CACHE = dict()

__jira = None
__github = None
__context = None

api_logger = logging.getLogger("augurapi")


class AugurContext(object):
    """
    This contains information that is used by the Augur library to identify constraints that should be
    used when requesting data.  The Context object is defined by a "Group".  Groups 
    are associated with a workflow, teams and other information.  Many functions within
    augur will require a context object in order to know how to filter and interpret data.
    """

    def __init__(self, group_id):
        self._group = get_group(group_id)
        self._workflow = self.group.workflow

    @property
    def workflow(self):
        return self._workflow

    @property
    def group(self):
        return self._group


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


def jql(jql_string, expand=None, include_changelog=False, max_results=500):
    """
    Does a JIRA jql search on the active instance
    :param include_changelog: If True, this will exclude changelogs from the response (sometimes, these can be extremely
                long).
    :param jql_string: The JQL string
    :param expand: The fields that should be expanded.
    :param max_results: The maximum number of results to return
    :return: A dictionary containing the issues found.
    """
    return get_jira().execute_jql(jql_string, include_changelog, expand, max_results)


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


def get_sprint_info(team_id, sprint=None, context=None, force_update=False):
    """
    Returns a timedelta showing the remaining time
    :param sprint: The sprint object returned from get_active_sprint_for_team - will call itself if this is none
    :param context: The context object to use during requests (defaults to using the default context if not given)
    :param team_id: The team id to get the sprint for.  Defaults to one of the teams if none is given.
    :param force_update: If True, then this will skip the cache and pull from JIRA
    :return: Returns timedelta object with the remaining time in sprint
    """

    context = context or get_default_context()
    from augur.fetchers import AugurSprintDataFetcher
    fetcher = AugurSprintDataFetcher(context=context, force_update=force_update, augurjira=get_jira())
    sprint = fetcher.fetch(team_id=team_id, sprint_id=sprint)

    if sprint:
        return {
            "sprint": sprint['sprint'],
            "timeLeftInSprint": sprint['sprint']['endDate'] - datetime.datetime.now()
        }
    else:
        return None


def get_abridged_sprint_list_for_team(team_id, limit=None):
    """
    Gets a list of sprints for the given team.  Will always load this from Jira.  It will also add some data. The 
    list is returned in sequence order which is usually the order in which the sprints occured in time.
    :param team_id: The ID of the team to retrieve sprints for.
    :param limit: The number of sprints back to go (limit=5 would mean only the last 5 sprints.
    :return: JiraSprintCollection
    """

    board = JiraBoard(get_jira(), team_id=team_id, restrict_sprints_with_team_name=True)
    if board.load():
        return board.get_sprints()

    team_ob = get_team_by_id(team_id)
    if team_ob.agile_board:
        try:
            team_sprints_abridged = get_jira().jira.sprints(board_id=team_ob.agile_board.jira_id, maxResults=0)
        except JIRAError, e:
            if e.status_code == 404:
                api_logger.error("Could not find the Agile Board with ID %d" % team_ob.agile_board.jira_id)
                team_sprints_abridged = []
            else:
                raise e
    else:
        team_sprints_abridged = []
        api_logger.warning("No agile board has been defined for this team")

    # the initial list can contain sprints from other boards in cases where tickets spent time on
    # both boards.  So we filter out any that do not belong to the team.
    if team_sprints_abridged:
        filtered_sprints = [sprint for sprint in team_sprints_abridged
                            if common.find_team_name_in_string(team_ob.name, sprint['name'])]

        filtered_sorted_list = sorted(filtered_sprints, key=lambda k: k['sequence'])
    else:
        filtered_sorted_list = []

    if limit:
        return filtered_sorted_list[-limit:]
    else:
        return filtered_sorted_list


def get_epics_from_sprint(sprint, context):
    """
    Gets a list of all epics associated with the given sprint.
    :param context: The context used to filter results
    :param sprint: The object returned from get_sprint_info_for_team
    :return: Returns a dictionary containing all the epics
    """
    assert context
    assert sprint

    epics = {}
    points_field_name = get_issue_field_from_custom_name('Story Points')
    epic_link_field_name = get_issue_field_from_custom_name('Epic Link')
    assert points_field_name
    assert epic_link_field_name

    team_ob = orm.get(t for t in db.Team if sprint['board_id'] == t.agile_board.jira_id)
    projects = context.workflow.get_projects(key_only=True)

    def update_epic_data(epics_inner, issue_inner):

        # ignore any issues that are not part of the context.
        if project_key_from_issue_key(issue['key']).upper() not in projects:
            return None

        if 'currentEstimateStatistic' not in issue_inner and 'estimateStatisticRequired' not in issue_inner:
            # this is the full blow issue_inner dict
            points = issue_inner['fields'][points_field_name] if points_field_name in issue_inner['fields'] else 0.0
            status = issue_inner['fields']['status']['name']
            issue_type = issue_inner['fields']['issuetype']
            done = context.workflow.is_resolved(status.lower(), issue_inner['resolution'])
            epic_key = common.deep_get(issue_inner, 'fields', epic_link_field_name) or "NONE"

        else:
            if 'currentEstimateStatistic' in issue_inner and issue_inner['currentEstimateStatistic']:
                # this is the abbreviated form of the issue_inner dict (returned by sprint endpoints)
                points = float(issue_inner['currentEstimateStatistic']['statFieldValue']['value']
                               if 'value' in issue_inner['currentEstimateStatistic']['statFieldValue'] else 0.0)
            else:
                points = 0.0

            status = issue_inner['status']['name']
            issue_type = issue_inner['typeName']
            done = issue_inner['done']
            epic_key = common.deep_get(issue_inner, 'epicField', 'epicKey') or "NONE"

        if epic_key not in epics_inner:

            epic_info = None
            if epic_key != "NONE":
                epic_info = get_epic_analysis(epic_key, context=context, brief=True, force_update=False)

            epics_inner[epic_key] = {
                "key": epic_key,
                "text": epic_info['milestone']['fields']['summary'] if epic_key != "NONE" else "No epic assigned",
                "analysis": epic_info or {},
                "sprint_completed_points": 0.0,
                "sprint_total_points": 0.0,
                "sprint_incomplete_points": 0.0,
                "issues": [],
                "devs": [],
                "teams": []
            }

        assignee = issue_inner['assigneeKey'] if 'assigneeKey' in issue_inner else ""
        epics_inner[epic_key]['issues'].append({
            "key": issue_inner['key'],
            "summary": issue_inner['summary'],
            "assignee": assignee,
            "status": status,
            "issue_type": issue_type,
            "points": points
        })

        if assignee:
            if assignee not in epics_inner[epic_key]["devs"]:
                epics_inner[epic_key]["devs"].append(assignee)

            if team_ob.name not in epics_inner[epic_key]["teams"]:
                epics_inner[epic_key]['teams'].append(team_ob.name)

        if done:
            epics_inner[epic_key]['sprint_completed_points'] += points
        else:
            epics_inner[epic_key]['sprint_incomplete_points'] += points

        epics_inner[epic_key]['sprint_total_points'] += points

        # return the epic that was created/updated.
        return epics_inner[epic_key]

    cache_key = 'sprint_epics_%s' % str(sprint['team_sprint_data']['sprint']['id'])
    cached_data = get_cached_data(cache_key)
    if not cached_data:
        for issue in sprint['team_sprint_data']['contents']['completedIssues']:
            update_epic_data(epics, issue)

        for issue in sprint['team_sprint_data']['contents']['issuesNotCompletedInCurrentSprint']:
            update_epic_data(epics, issue)
        cache_data({'data': epics}, cache_key, storage_type="sprint_epics")
    else:
        epics = cached_data[0]['data']

    return epics


def get_sprint_history_by_team(team, context, sort_by=SPRINT_SORTBY_ENDDATE, descending=True, limit=None):
    """
    Gets a list of sprints for the given team.  This will load from cache in some cases and get the most recent
     when it makes to do so.
    :param context:
    :param limit:
    :param descending:
    :param sort_by:
    :param team: The ID of the team to retrieve sprints for.
    :return: Returns an array of sprint objects.
    """
    ua_sprints = get_abridged_sprint_list_for_team(team, limit)
    sprintdict_list = []

    for s in ua_sprints:
        # get_detailed... will handle caching
        sprint_ob = get_detailed_sprint_info_for_team(team, s['id'], context=context)

        if sprint_ob:
            sprintdict_list.append(sprint_ob)

    def sort_by_end_date(cmp1, cmp2):
        return -1 if cmp1['team_sprint_data']['sprint']['endDate'] < cmp2['team_sprint_data']['sprint'][
            'endDate'] else 1

    SORT_KEYS = {
        SPRINT_SORTBY_ENDDATE: sort_by_end_date
    }

    if sort_by in SORT_KEYS:
        return sorted(sprintdict_list, cmp=SORT_KEYS[sort_by], reverse=descending)
    else:
        return sprintdict_list


def get_detailed_sprint_info_for_team(team_id, sprint_id, context):
    """
    This will get sprint data for the the given team and sprint.  You can specify you want the current or the
    most recently closed sprint for the team by using one of the SPRINT_XXX consts.  You can also specify an ID
    of a sprint if you know what you want.  Or you can pass in a sprint object to confirm that it's a valid
    sprint object.  If it is, it will be returned, otherwise a SprintNotFoundException will be thrown.
    :param context:
    :param team_id: The ID of the team
    :param sprint_id: The ID, const, or sprint object.
    :return: Returns a sprint object
    """

    # We either don't have anything cached or we decided not to use it.  So start from scratch by retrieving
    # the detailed sprint data from Jira
    sprint_abridged = get_abridged_team_sprint(team_id, sprint_id)

    if not sprint_abridged:
        return None

    team_object = get_team_by_id(team_id)
    sprint_ob = get_jira().jira.sprint_report(team_object.get_agile_board_jira_id(), sprint_abridged['id'])

    if not sprint_ob:
        return None

    # convert date strings to actual dates.
    common.clean_detailed_sprint_info(sprint_ob)

    now = datetime.datetime.now().replace(tzinfo=None)

    if sprint_ob['sprint']['state'] == 'ACTIVE':
        sprint_ob['actual_length'] = now - sprint_ob['sprint']['startDate']
        sprint_ob['overdue'] = sprint_ob['actual_length'] > datetime.timedelta(days=16)
    else:
        sprint_ob['actual_length'] = sprint_ob['sprint']['completeDate'] - sprint_ob['sprint']['startDate']

        # not applicable if the sprint is complete or happens in the future.
        sprint_ob['overdue'] = False

    # Get point completion standard deviation
    standard_dev_map = defaultdict(int)
    total_completed_points = 0
    projects = context.workflow.get_projects(key_only=True)
    for issue in sprint_ob['contents']['completedIssues']:

        # ignore any issues that are not part of the context.
        if project_key_from_issue_key(issue['key']).upper() not in projects:
            continue

        points = issue.get('currentEstimateStatistic', {}).get('statFieldValue', {'value': 0}).get('value', 0)
        total_completed_points += points
        if 'assignee' in issue:
            standard_dev_map[issue['assignee']] += points
        else:
            print "Found a completed issue without an assignee - %s" % issue['key']

    std_dev = common.standard_deviation(standard_dev_map.values())

    # Replace "null" with 0
    for val in ('completedIssuesEstimateSum', 'issuesNotCompletedEstimateSum', 'puntedIssuesEstimateSum'):
        if val in sprint_ob['contents'] and isinstance(sprint_ob['contents'][val], dict) and \
                sprint_ob['contents'][val]['text'] == 'null':
            sprint_ob['contents'][val]['text'] = "0"

    if sprint_ob['contents']['issueKeysAddedDuringSprint']:
        # get issues that were added during the sprint that are part of this context.
        results = get_jira().execute_jql("(%s) and key in ('%s')" %
                                         (common.projects_to_jql(context.workflow),
                                          "','".join(sprint_ob['contents']['issueKeysAddedDuringSprint'].keys())))

        sprint_ob['contents']['issueKeysAddedDuringSprint'] = results

    if sprint_ob['contents']['issuesNotCompletedInCurrentSprint']:
        incomplete_keys = [x['key'] for x in sprint_ob['contents']['issuesNotCompletedInCurrentSprint']]

        # get all the incomplete tickets that are part of this context
        incomplete_in_sprint_jql = "(%s) and key in ('%s')" % (common.projects_to_jql(context.workflow),
                                                               "','".join(incomplete_keys))

        results = get_jira().execute_jql_with_analysis(incomplete_in_sprint_jql, total_only=False, context=context)

        sprint_ob['contents']['issuesNotCompletedInCurrentSprint'] = results['issues'].values()
        sprint_ob['contents']['incompleteIssuesFullDetail'] = results['issues'].values()

    team_stats = {
        "team_name": team_object.name,
        "team_id": team_id,
        "sprint_id": sprint_id,
        "board_id": team_object.agile_board.jira_id,
        "std_dev": std_dev,
        "contributing_devs": standard_dev_map.keys(),
        "team_sprint_data": sprint_ob,
        "total_completed_points": total_completed_points
    }

    return team_stats


def get_sprint_by_id(team_id, sprint_id, context):
    """
    This will get sprint data for the the given sprint.  You can specify you want the current or the
    most recently closed sprint for the team by using one of the SPRINT_XXX consts.  You can also specify an ID
    of a sprint if you know what you want.  Or you can pass in a sprint object to confirm that it's a valid
    sprint object.  If it is, it will be returned, otherwise a SprintNotFoundException will be thrown.
    :param context:
    :param team_id: The ID of the team
    :param sprint_id: The ID, const, or sprint object.
    :return: Returns a sprint object
    """

    # We either don't have anything cached or we decided not to use it.  So start from scratch by retrieving
    # the detailed sprint data from Jira
    sprint_abridged = get_abridged_team_sprint(team_id, sprint_id)

    if not sprint_abridged:
        return None

    team_object = get_team_by_id(team_id)
    sprint_ob = get_jira().jira.sprint_report(team_object.get_agile_board_jira_id(), sprint_abridged['id'])

    if not sprint_ob:
        return None

    # convert date strings to actual dates.
    common.clean_detailed_sprint_info(sprint_ob)

    now = datetime.datetime.now().replace(tzinfo=None)

    if sprint_ob['sprint']['state'] == 'ACTIVE':
        sprint_ob['actual_length'] = now - sprint_ob['sprint']['startDate']
        sprint_ob['overdue'] = sprint_ob['actual_length'] > datetime.timedelta(days=16)
    else:
        sprint_ob['actual_length'] = sprint_ob['sprint']['completeDate'] - sprint_ob['sprint']['startDate']

        # not applicable if the sprint is complete or happens in the future.
        sprint_ob['overdue'] = False

    # Get point completion standard deviation
    standard_dev_map = defaultdict(int)
    total_completed_points = 0
    projects = context.workflow.get_projects(key_only=True)
    for issue in sprint_ob['contents']['completedIssues']:

        # ignore any issues that are not part of the context.
        if common.project_key_from_issue_key(issue['key']).upper() not in projects:
            continue

        points = issue.get('currentEstimateStatistic', {}).get('statFieldValue', {'value': 0}).get('value', 0)
        total_completed_points += points
        if 'assignee' in issue:
            standard_dev_map[issue['assignee']] += points
        else:
            print "Found a completed issue without an assignee - %s" % issue['key']

    std_dev = common.standard_deviation(standard_dev_map.values())

    # Replace "null" with 0
    for val in ('completedIssuesEstimateSum', 'issuesNotCompletedEstimateSum', 'puntedIssuesEstimateSum'):
        if val in sprint_ob['contents'] and isinstance(sprint_ob['contents'][val], dict) and \
                sprint_ob['contents'][val]['text'] == 'null':
            sprint_ob['contents'][val]['text'] = "0"

    if sprint_ob['contents']['issueKeysAddedDuringSprint']:
        # get issues that were added during the sprint that are part of this context.
        results = get_jira().execute_jql("(%s) and key in ('%s')" %
                                         (common.projects_to_jql(context.workflow),
                                          "','".join(sprint_ob['contents']['issueKeysAddedDuringSprint'].keys())))

        sprint_ob['contents']['issueKeysAddedDuringSprint'] = results

    if sprint_ob['contents']['issuesNotCompletedInCurrentSprint']:
        incomplete_keys = [x['key'] for x in sprint_ob['contents']['issuesNotCompletedInCurrentSprint']]

        # get all the incomplete tickets that are part of this context
        issues_not_completed_jql = "(%s) and key in ('%s')" % \
                                   (common.projects_to_jql(context.workflow), "','".join(incomplete_keys))
        results = get_jira().execute_jql_with_analysis(issues_not_completed_jql, total_only=False, context=context)

        sprint_ob['contents']['issuesNotCompletedInCurrentSprint'] = results['issues'].values()
        sprint_ob['contents']['incompleteIssuesFullDetail'] = results['issues'].values()

    team_stats = {
        "team_name": team_object.name,
        "team_id": team_id,
        "sprint_id": sprint_id,
        "board_id": team_object.agile_board.jira_id,
        "std_dev": std_dev,
        "contributing_devs": standard_dev_map.keys(),
        "team_sprint_data": sprint_ob,
        "total_completed_points": total_completed_points
    }

    return team_stats


def get_abridged_team_sprint(team_id, sprint_id=const.SPRINT_CURRENT):
    """
    Retrieves the sprint object identified by the given ID.  If the given object
    is a sprint object already it will be returned.  Otherwise, the sprint ID will be looked up in JIRA
    :param team_id:
    :param sprint_id: Either one of the SPRINT_XXX consts, an ID, or a sprint object.
    :return: Returns a sprint object or throws a TeamSprintNotFoundException
    """

    def get_key(item):
        return item['sequence']

    sprints = get_abridged_sprint_list_for_team(team_id)
    sprints = sorted(sprints, key=get_key, reverse=True)

    sprint = None

    if sprint_id == const.SPRINT_LAST_COMPLETED:
        # Note: get_issue_sprints returns results that are sorted in descending order by end date
        for s in sprints:
            if s['state'] == 'FUTURE':
                continue
            if s['state'] == 'ACTIVE' and 'overdue' not in s:
                # this is an active sprint that is not completed yet.
                continue
            elif s['state'] == 'ACTIVE' and 'overdue' in s:
                # this is a sprint that should have been marked complete but hasn't been yet
                sprint = s
            elif s['state'] == 'CLOSED':
                # this is the first sprint that is not marked as active so we can assume that it's the last
                # completed sprint.
                sprint = s
                break

    elif sprint_id == const.SPRINT_BEFORE_LAST_COMPLETED:
        # Note: get_issue_sprints returns results that are sorted in descending order by end date
        sprint_last = None
        sprint_before_last = None
        for s in sprints:
            if s['state'] == 'CLOSED':
                # this is the first sprint that is not marked as active so we can assume that it's the last
                # completed sprint.
                if not sprint_last:
                    # so we've gotten to the most recently closed one but we're looking for the one before that.
                    sprint_last = s
                else:
                    # this is the one before the last one.
                    sprint_before_last = s
                    break

        sprint = sprint_before_last

    elif sprint_id == const.SPRINT_CURRENT:
        # Note: get_issue_sprints returns results that are sorted in descending order by end date
        for s in sprints:
            if s['state'] == 'ACTIVE':
                # this is an active sprint that is not completed yet.
                sprint = s
                break
            else:
                continue

    elif isinstance(sprint_id, dict):
        # a sprint object was given instead of just an id
        sprint = sprint_id
    else:
        # Note: get_issue_sprints returns results that are sorted in descending order by end date
        for s in sprints:
            if s['id'] == sprint_id:
                sprint = s
                break
            else:
                continue

    return sprint


def get_sprint(sprint_id=const.SPRINT_LAST_COMPLETED, team_id=None):
    """
    This will get sprint data for the the given team and sprint.  You can specify you want the current or the
    most recently closed sprint for the team by using one of the SPRINT_XXX consts.  You can also specify an ID
    of a sprint if you know what you want.  Or you can pass in a sprint object to confirm that it's a valid
    sprint object.  If it is, it will be returned, otherwise a SprintNotFoundException will be thrown.
    :param sprint_id: The ID, const, or sprint object.
    :param team_id: The ID of the team - only required if using a "special" sprint ID like SPRINT_LAST_COMPLETED
    :return: Returns a tuple containing the board and the sprint object
    """
    if isinstance(sprint_id,(str,unicode)) and team_id is None:
        api_logger.error("You must specify a team if requesting by special sprint ID")
        return None, None

    board = JiraBoard(get_jira(), team_id=team_id, restrict_sprints_with_team_name=True, max_sprints=2,
                      include_sprint_reports=True)
    if board.load():
        sprint = None

        if sprint_id  == const.SPRINT_CURRENT:
            sprint = board.get_most_recent_active_sprint()
        elif sprint_id == const.SPRINT_LAST_COMPLETED:
            sprint = board.get_most_recent_closed_sprint()
        elif isinstance(sprint_id,int):
            sprint = board.get_sprint(sprint_id)

        return board,sprint
    else:
        return None,None

def update_current_sprint_stats(context=None, force_update=False):
    """
    Used to update the currently stored sprint data for all teams
    :param force_update:
    :param context: The context object to use during requests (defaults to using the default context if not given)
    :return: Returns a result array containing the teams updated and the number of issues found.
    """
    context = context or get_default_context()
    from augur.fetchers import AugurSprintDataFetcher
    fetcher = AugurSprintDataFetcher(context=context, force_update=force_update, augurjira=get_jira())
    return fetcher.fetch(sprint_id=const.SPRINT_CURRENT)


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
    return get_jira().get_issue(key)


def get_epic_from_issue(issue):
    """
    Retrieves the epic issue from the given key
    :param issue: The issue to find the epic
    :return: Returns a dict containing the issue
    """
    return get_jira().get_associated_epic(issue)


def get_defect_data(lookback_days=14, context=None, force_update=False):
    """
    Retrieves defect analytics for the past X days where X is the lookback_days value given.  The results are returned
    as a dictionary that looks something like this:
    
        stats = {
            lookback_days: <int>,
            current_period: defects_json,
            previous_period: defects_previous_period_json,
            grouped_by_severity_current: dict(grouped_by_severity_current),
            grouped_by_severity_previous: dict(grouped_by_severity_previous),
            grouped_by_priority_current: dict(grouped_by_priority_current),
            grouped_by_priority_previous: dict(grouped_by_priority_previous),
            grouped_by_impact_current: dict(grouped_by_impact_current),
            grouped_by_impact_previous: dict(grouped_by_impact_previous),
            links = dict({
                current_period: dict({
                    all: dict()
                    severity: dict()
                    priority: dict()
                    impact: dict()                
                })
                previous_period: dict({
                    all: dict()
                    severity: dict()
                    priority: dict()
                    impact: dict()                
                })
            })
    :param lookback_days: Number of days to lookback for defects
    :param context: The context object to use during requests (defaults to using the default context if not given)
    :param force_update: True to skip cache and retrieve data from source
    :return: 
    """
    context = context or get_default_context()
    from augur.fetchers import AugurDefectFetcher
    fetcher = AugurDefectFetcher(context=context, force_update=force_update, augurjira=get_jira())
    return fetcher.fetch(lookback_days=lookback_days)


def get_historical_defect_data(num_weeks=8, context=None, force_update=False):
    """
    Retrieves abridged data going back X weeks where X = num_weeks
    :param num_weeks: The number of weeks to look at
    :param context: The context object to use during requests (defaults to using the default context if not given)
    :param force_update:  True to skip cache and retrieve data from source
    :return: 
    """
    context = context or get_default_context()
    from augur.fetchers import AugurDefectHistoryFetcher
    fetcher = AugurDefectHistoryFetcher(context=context, force_update=force_update, augurjira=get_jira())
    return fetcher.fetch(num_weeks=num_weeks)


def get_releases_since(start, end, context=None, force_update=False):
    """
    Gets all releases within the period between start and end
    Returns a dict that looks something like this:
    
        data = ({
            release_date_start: <datetime>,
            release_date_end: <datetime>,
            issues: <list>
        })
        
    :param context:
    :param force_update:
    :param start: An arrow object containing the start date/time
    :param end: An arrow object containing the end date/time
    :return: A dictionary of of data describing the release pipeline
    """

    if not start:
        # default to yesterday's releases
        start = arrow.get(datetime.datetime.now()).replace(days=-1).floor()
        end = start.ceil()

    elif start and not end:
        # default to the given start date and the end of that day
        start = arrow.get(start).floor('day')
        end = start.ceil('day')

    from augur.fetchers import AugurRelease
    fetcher = AugurRelease(context=context, force_update=force_update, augurjira=get_jira())
    return fetcher.fetch(start=start, end=end)


def get_filter_analysis(filter_id, brief=False, context=None, force_update=False):
    """
    Gets the filter's details requested in the arguments
    :param force_update:
    :param filter_id The filter ID
    :param brief A shortened version of the analysis that takes less time to retrieve
    :param context: The context object to use during requests (defaults to using the default context if not given)
    :return: A dictionary of filter data
    """
    context = context or get_default_context()
    from augur.fetchers import AugurMilestoneDataFetcher
    fetcher = AugurMilestoneDataFetcher(force_update=force_update, augurjira=get_jira(), context=context)
    return fetcher.fetch(filter_id=filter_id, brief=brief)


def get_jql_analysis(jql_str, brief=False, context=None, force_update=False):
    """
    Gets the jql results details requested in the arguments
    :param force_update:
    :param brief:
    :param jql_str The JQL to use to get results.
    :param context: The context object to use during requests (defaults to using the default context if not given)
    :return: A dictionary of filter data
    """
    context = context or get_default_context()
    from augur.fetchers import AugurMilestoneDataFetcher
    fetcher = AugurMilestoneDataFetcher(force_update=force_update, augurjira=get_jira(), context=context)
    return fetcher.fetch(jql=jql_str, brief=brief)


def get_epic_analysis(epic_key, context, brief=False, force_update=False):
    """
    Gets the epic's details requested in the arguments
    :param force_update: Ignores cache and retrieves from source
    :param brief: True to only return totals and not issue details.
    :param epic_key: The key for the epic to analyze
    :param context: The context object to use during requests (defaults to using the default context if not given)
    :return: A dictionary of epics keyed on the epic key
    """
    context = context or get_default_context()
    from augur.fetchers import AugurMilestoneDataFetcher
    fetcher = AugurMilestoneDataFetcher(force_update=force_update, context=context, augurjira=get_jira())
    return fetcher.fetch(epic_key=epic_key, brief=brief)


def get_user_worklog(start, end, team_id, username=None, project_key=None, context=None, force_update=False):
    """

    :param start: The start date for the logs
    :type start: datetime, date, str, float, int
    :param end: The end date of the logs
    :type end: datetime, date, str, float, int
    :param team_id: The Temp Team ID to retrieve worklogs for
    :param username: The username of the user to filter results on (optional)
    :param project_key: The JIRA project to filter results on (optional)
    :param context: The context object to use during requests (defaults to using the default context if not given)
    :param force_update: If True, then this will skip the cache and pull from JIRA
    :return: A dictionary of user worklog data
    :rtype: dict
    """
    context = context or get_default_context()
    from augur.fetchers import AugurWorklogDataFetcher
    fetcher = AugurWorklogDataFetcher(force_update=force_update, augurjira=get_jira(), context=context)
    data = fetcher.fetch(start=start, end=end, username=username, team_id=team_id, project_key=project_key)
    return data[0] if isinstance(data, list) else data


def get_dashboard_data(context=None, force_update=False):
    """
    This will retrieve all data associated with the dashboard.  It will only return something if data has been
    stored in the last two hours.  If nothing is returned, it will load the data automatically and return that.
    :param force_update: If True, then this will skip the cache and pull from JIRA
    :param context: The context object to use during requests (defaults to using the default context if not given)
    :return: Returns the dashboard data.
    """
    context = context or get_default_context()
    from augur.fetchers import AugurDashboardFetcher
    fetcher = AugurDashboardFetcher(force_update=force_update, context=context, augurjira=get_jira())
    data = fetcher.fetch()
    return data[0] if isinstance(data, list) else data


def get_all_developer_info(context=None, force_update=False):
    """
    Retrieves all the developers organized by team along with some basic user info.
    Looks something like this:

    {
        "devs" : {
            "hnuss" : {
                "active" : true ,
                "team_id" : "hb" ,
                "fullname" : "Harley Nuss" ,
                "email" : "hnuss@underarmour.com" ,
                "team_name" : "Team Hamburglar"
            }
        },...

    }
    :param context: The context object to use during requests (defaults to using the default context if not given)
    :param force_update: If True, then this will skip the cache and pull fresh data
    :return:
    """
    context = context or get_default_context()
    from augur.fetchers import AugurTeamMetaDataFetcher
    fetcher = AugurTeamMetaDataFetcher(context=context, force_update=force_update, augurjira=get_jira())
    f = fetcher.fetch()
    return f


def get_dev_stats(username, look_back_days=30, context=None, force_update=False):
    """
    This will get detailed developer stats for the given user.  The stats will go back the number of days
    specified in look_back_days.  It will use the stats stored in the db if the same parameters were queried in
    the past 12 hours.
    :param username: The username of the dev
    :param look_back_days:  The number of days to go back to look for developers details (in both github and jira)
    :param context: The context object to use during requests (defaults to using the default context if not given)
    :param force_update: If True, then this will skip the cache and pull from JIRA
    :return:
    """
    context = context or get_default_context()
    from augur.fetchers import AugurDevStatsDataFetcher
    fetcher = AugurDevStatsDataFetcher(context=context, force_update=force_update, augurjira=get_jira())
    return fetcher.fetch(username=username, look_back_days=look_back_days)


def get_all_dev_stats(context=None, force_update=False):
    """
    Gets all developer info plus some aggregate data for each user including total points completed.
    :param context: The context object to use during requests (defaults to using the default context if not given)
    :type force_update: bool
    :return:
    """
    context = context or get_default_context()
    from augur.fetchers import AugurOrgStatsFetcher
    return AugurOrgStatsFetcher(get_jira(), context=context, force_update=force_update).fetch()


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


def get_staff_member_by_github_username(username):
    """
    Searches staff based on a given github username
    :param username: The github username t osearch for
    :return: Returns a db.Staff object or None if not found
    """
    assert username
    try:
        return orm.get(s for s in db.Staff if s.github_username == username)
    except (orm.MultipleObjectsFoundError, orm.ObjectNotFound):
        return None


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


def get_consultants(active_only=True):
    """
    Retrieves a list of Staff model objects containing all the known consultants.
    :type active_only: bool
    :param active_only: Set to True if you want to only retrieve active consultants
    :return: An array of Staff objects.
    """
    if active_only:
        return orm.select(t for t in db.Staff if t.type == "Consultant" and t.status == "Active")
    else:
        return orm.select(t for t in db.Staff if t.type == "Consultant")


def get_fulltime_staff():
    """
    Retrieves a list of Staff model objects containing all the known FTEs in the engineering group.
    :return: An array of Staff objects. 
    """
    return orm.select(t for t in db.Staff if t.type == "FTE")


def get_team_by_name(name):
    """
    Returns a team object keyed on the name of the team.  If there is more than one team with the same name it will
    always returns only 1.  There is no guarantee which one, though.
    :param name: The name to search for
    :return: A Team object.
    """
    return orm.get(t for t in db.Team if t.name == name)


def get_team_by_id(team_id):
    """
    Returns a team object keyed on the name of the team.  If there is more than one team with the same name it will
    always returns only 1.  There is no guarantee which one, though.
    :param team_id: The team id to search for
    :return: A Team object.
    """
    return db.Team[team_id]


def get_teams_as_dictionary(context=None):
    """
    Gets all teams as dictionary instead of a list.  The keys of the dictionary are the team_ids
    :return: Returns a dictionary of Team objects
    """
    teams = get_teams(context)
    return serialization.to_dict(teams)


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


def get_active_epics(context=None, force_update=False):
    """
    Retrieves epics that have been actively worked on in the past X days
    :param force_update:
    :param context: The context object to use during requests (defaults to using the default context if not given)
    :return: A dictionary of epics
    """
    context = context or get_default_context()
    from augur.fetchers import RecentEpicsDataFetcher
    fetch = RecentEpicsDataFetcher(context=context, augurjira=get_jira(), force_update=force_update)
    return fetch.fetch()


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
    return get_jira().get_board_metrics(board_id, context)


def cache_data(document, key, storage_type=None):
    """
    Store arbitrary data in the cache 
    :param document: The data to store (json object)
    :param key: The key to uniquely identify this object with
    :param storage_type: The storage_type is a way of further disambiguating this cached value from
                            other cached values in the collection.  For example, cache type
                            might be "engineering_report"
    :return: Returns a mongo document array
    """
    mongo = cache_store.AugurStatsDb()
    cache = AugurCachedResultSets(mongo)
    cache.save_with_key(document, key, storage_type=storage_type)
    return document


def get_cached_data(key, override_ttl=None):
    """
    Retrieved data cached using "cache_data" function
    :param key: The unique key used to cache this data
    :param override_ttl: The ttl for the data if different from default (this is the number of seconds to save)
    :return: Returns a JSON object loaded from the cache or None if not found
    """

    mongo = cache_store.AugurStatsDb()
    cache = AugurCachedResultSets(mongo)
    return cache.load_from_key(key, override_ttl=override_ttl, context=get_default_context())


def simplify_issue(issue):
    """
    Removes unnecessary data from JIRA issue object and returns a simplified dictionary
    :param issue:
    :return:
    """
    severity_field_name = get_issue_field_from_custom_name('Severity')
    dev_team_field_name = get_issue_field_from_custom_name('Dev Team')
    points_field_name = get_issue_field_from_custom_name('Story Points')
    sprint_field_name = get_issue_field_from_custom_name('Sprint')
    return {
        "key": issue['key'],
        "severity": common.deep_get(issue, 'fields', severity_field_name, 'value'),
        "priority": common.deep_get(issue, 'fields', 'priority', 'name'),
        "summary": common.deep_get(issue, 'fields', 'summary'),
        "points": common.deep_get(issue, 'fields', points_field_name),
        "description": common.deep_get(issue, 'fields', 'description'),
        "devteam": common.deep_get(issue, 'fields', dev_team_field_name, 'value'),
        "reporter": common.deep_get(issue, 'fields', 'reporter', 'key'),
        "assignee": common.deep_get(issue, 'fields', 'assignee', 'key'),
        "components": [x['name'] for x in issue['fields']['components']],
        "sprints": common.deep_get(issue, 'fields', sprint_field_name),
        "creator": common.deep_get(issue, 'fields', 'creator', 'key')
    }


def get_issue_field_from_custom_name(name):
    """
    Returns the true field name of a jira field based on its friendly name
    :param name: The friendly name of the field
    :return: A string with the true name of a field.
    """
    return get_jira().get_field_by_name(name)


def get_projects_by_category(category):
    """
    Gets all projects with the given category
    :param category:
    :return:
    """
    cache_key = "projects_%s" % category
    projects = get_cached_data(cache_key)
    if not projects:
        projects = get_jira().jira.get_projects_with_category(category)
        cache_data({'data': projects}, cache_key)
    else:
        projects = projects[0]['data']

    return projects


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


def add_staff_to_team(team, staff):
    """
    Adds a staff member to a team.
    :param team: The db.Team object
    :param staff: The db.Staff object to add
    :type team: db.Team
    :type staff: db.Staff
    :return:
    """
    assert (team and staff)
    staff.teams.add(staff)


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
