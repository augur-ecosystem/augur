"""
AUGUR API


The Augur API provides easy access to some of the most benefecial data that can be collected by the library.
Rather than instantiating data classes or integrations directly, the API provides a layer of abstraction in the form
of functions.  Data that is returns is almost always in the form of a dictionary that can be easily converted into
JSON as necessary.
"""

import datetime

import arrow
import os

import copy

from augur import settings, common
from augur.common.cache_store import UaCachedResultSets

from augur.common import const, cache_store
from augur.models import AugurModel
from augur.models.product import Product
from augur.models.staff import Staff
from augur.models.team import Team
from augur.models.group import Group
from augur.models.workflow import Workflow

CACHE = dict()

__jira = None
__github = None


def get_github():
    from augur.integrations.augurgithub import AugurGithub

    global __github
    if not __github:
        __github = AugurGithub()
    return __github


def get_jira():
    from augur.integrations.augurjira import AugurJira

    global __jira
    if not __jira:
        __jira = AugurJira()
    return __jira


def jql(jql_string, expand=None, max_results=500):
    """
    Does a JIRA jql search on the active instance
    :param jql_string: The JQL string
    :param expand: The fields that should be expanded.
    :param max_results: The maximum number of results to return
    :return: A dictionary containing the issues found.
    """
    return get_jira().execute_jql(jql_string, expand, max_results)


def get_workflow(workflow_id):
    """
    Gets a workflow by ID
    :param workflow_id: The ID of the workflow to retrieve
    :return: Returns a Group object or None if not found
    """
    g = filter(lambda x: x.id == workflow_id, get_workflows())
    return g[0] if g else None


def get_workflows():
    """
    Get a list of all workflows
    :return: Returns a Group object or None if not found
    """
    cached = get_memory_cached_data("_WORKFLOWS_")
    if not cached:
        path_to_csv = os.path.join(settings.main.project.augur_base_dir, 'data/workflows.yaml')
        data = AugurModel.import_from_yaml(path_to_csv, Workflow)
        cached = memory_cache_data(data, "_WORKFLOWS_")
    return cached


def get_group(group_id):
    """
    Gets a group by id
    :param group_id: The ID or name of the group to retrieve
    :return: Returns a Group object or None if not found
    """
    g = filter(lambda x: x.id == group_id, get_groups())
    return g[0] if g else None


def get_groups():
    """
    Gets all groups
    :return: Returns a Group object or None if not found
    """
    cached = get_memory_cached_data("_GROUPS_")
    if not cached:
        path_to_csv = os.path.join(settings.main.project.augur_base_dir, 'data/groups.csv')
        data = AugurModel.import_from_csv(path_to_csv, Group)
        cached = memory_cache_data(data, "_GROUPS_")
    return cached


def get_historic_sprint_stats(team, force_update=False):
    """
    Gets all the sprint objects for a team (decorated with other custom info) and runs them through the
     analyzer to get specific ticket info for each sprint.  This caches both the sprint objects and the
      converted sprint data.
    """
    from augur.fetchers import UaSprintDataFetcher
    fetcher = UaSprintDataFetcher(force_update=force_update, uajira=get_jira())
    return fetcher.fetch(get_history=True, team_id=team)


def get_sprint_info(sprint=None, team='f', force_update=False):
    """
    Returns a timedelta showing the remaining time
    :param sprint: The sprint object returned from get_active_sprint_for_team - will call itself if this is none
    :param team: The team id to get the sprint for.  Defaults to one of the teams if none is given.
    :param force_update: If True, then this will skip the cache and pull from JIRA
    :return: Returns timedelta object with the remaining time in sprint
    """
    from augur.fetchers import UaSprintDataFetcher
    fetcher = UaSprintDataFetcher(force_update=force_update, uajira=get_jira())
    sprint = fetcher.fetch(team_id=team, sprint_id=sprint)

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
    :return: Returns an array of sprint objects.
    """

    team_ob = get_team_by_id(team_id)
    team_sprints_abridged = get_jira().get_sprints_from_board(team_ob.board_id)

    # the initial list can contain sprints from other boards in cases where tickets spent time on
    # both boards.  So we filter out any that do not belong to the team.
    filtered_sprints = [sprint for sprint in team_sprints_abridged if common.sprint_belongs_to_team(sprint, team_id)]

    filtered_sorted_list = sorted(filtered_sprints, key=lambda k: k['sequence'])

    if limit:
        return filtered_sorted_list[-limit:]
    else:
        return filtered_sorted_list


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
            if s['state'] == 'ACTIVE' and not 'overdue' in s:
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


def get_sprint_info_for_team(team_id, sprint_id=const.SPRINT_LAST_COMPLETED, force_update=False):
    """
    This will get sprint data for the the given team and sprint.  You can specify you want the current or the
    most recently closed sprint for the team by using one of the SPRINT_XXX consts.  You can also specify an ID
    of a sprint if you know what you want.  Or you can pass in a sprint object to confirm that it's a valid
    sprint object.  If it is, it will be returned, otherwise a SprintNotFoundException will be thrown.
    :param team_id: The ID of the team
    :param sprint_id: The ID, const, or sprint object.
    :param force_update: If True, then this will skip the cache and pull from JIRA
    :return: Returns a sprint object
    """
    from augur.fetchers import UaSprintDataFetcher
    fetcher = UaSprintDataFetcher(force_update=force_update, uajira=get_jira())
    return fetcher.fetch(team_id=team_id, sprint_id=sprint_id)


def update_current_sprint_stats(force_update=False):
    """
    Used to update the currently stored sprint data for all teams
    :return: Returns a result array containing the teams updated and the number of issues found.
    """
    from augur.fetchers import UaSprintDataFetcher
    fetcher = UaSprintDataFetcher(force_update=force_update, uajira=get_jira())
    return fetcher.fetch(sprint_id=const.SPRINT_CURRENT)


def get_issue_details(key, force_update=False):
    """
    Return details about an issue based on an issue key.  This will pull from mongo if possible.
    :param key: The key of the issue to retrieve
    :param force_update: If True, then this will skip the cache and pull from JIRA
    :return: The issue object
    """
    from augur.fetchers import UaIssueDataFetcher
    fetcher = UaIssueDataFetcher(force_update=force_update, uajira=get_jira())
    return fetcher.fetch(issue_key=key)


def get_issues_details(keys, force_update=False):
    """
    Return details about more than one issue.  This will always pull from Jira
    :param keys: The list of keys of the issues to retrieve
    :param force_update: If True, then this will skip the cache and pull from JIRA
    :return: A list of issue objects
    """
    from augur.fetchers import UaIssueDataFetcher
    fetcher = UaIssueDataFetcher(force_update=force_update, uajira=get_jira())
    return fetcher.fetch(issue_keys=keys)


def get_defect_data(lookback_days=14, force_update=False):
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
    :param force_update: True to skip cache and retrieve data from source
    :return: 
    """
    from augur.fetchers import UaDefectFetcher
    fetcher = UaDefectFetcher(force_update=force_update, uajira=get_jira())
    return fetcher.fetch(lookback_days=lookback_days)


def get_historical_defect_data(num_weeks=8, force_update=False):
    """
    Retrieves abridged data going back X weeks where X = num_weeks
    :param num_weeks: The number of weeks to look at
    :param force_update:  True to skip cache and retrieve data from source
    :return: 
    """
    from augur.fetchers import UaDefectHistoryFetcher
    fetcher = UaDefectHistoryFetcher(force_update=force_update, uajira=get_jira())
    return fetcher.fetch(num_weeks=num_weeks)


def get_releases_since(start, end, force_update=False):
    """
    Gets all releases within the period between start and end
    Returns a dict that looks something like this:
    
        data = ({
            release_date_start: <datetime>,
            release_date_end: <datetime>,
            issues: <list>
        })
        
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

    from augur.fetchers import UaRelease
    fetcher = UaRelease(force_update=force_update, uajira=get_jira())
    return fetcher.fetch(start=start, end=end)


def get_filter_analysis(filter_id, force_update=False):
    """
    Gets the filter's details requested in the arguments
    :param:filter The filter ID
    :return: A dictionary of filter data
    """
    from augur.fetchers import UaMilestoneDataFetcher
    fetcher = UaMilestoneDataFetcher(force_update=force_update, uajira=get_jira())
    return fetcher.fetch(filter_id=filter_id)


def get_epic_analysis(epic_key, force_update=False):
    """
    Gets the epic's details requested in the arguments
    :param:epic The epic key
    :return: A dictionary of epics keyed on the epic key
    """
    from augur.fetchers import UaEpicDataFetcher
    fetcher = UaEpicDataFetcher(force_update=force_update, uajira=get_jira())
    return fetcher.fetch(epic_key=epic_key)


def get_user_worklog(start, end, team_id, username=None, project_key=None, force_update=False):
    """

    :param start: The start date for the logs
    :param end: The end date of the logs
    :param team_id: The Temp Team ID to retrieve worklogs for
    :param username: The username of the user to filter results on (optional)
    :param project_key: The JIRA project to filter results on (optional)
    :param force_update: If True, then this will skip the cache and pull from JIRA
    :return:
    """

    from augur.fetchers import UaWorklogDataFetcher
    fetcher = UaWorklogDataFetcher(force_update=force_update, uajira=get_jira())
    data = fetcher.fetch(start=start, end=end, username=username, team_id=team_id, project_key=project_key)
    return data[0] if isinstance(data, list) else data


def get_dashboard_data(force_update=False):
    """
    This will retrieve all data associated with the dashboard.  It will only return something if data has been
    stored in the last two hours.  If nothing is returned, it will load the data automatically and return that.
    :param force_update: If True, then this will skip the cache and pull from JIRA
    :return: Returns the dashboard data.
    """
    from augur.fetchers import UaDashboardFetcher
    fetcher = UaDashboardFetcher(force_update=force_update, uajira=get_jira())
    data = fetcher.fetch()
    return data[0] if isinstance(data, list) else data


def get_all_developer_info(group_id=None, force_update=False):
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
    :param group_id: The ID of the group to limit results to.
    :param force_update: If True, then this will skip the cache and pull fresh data
    :return:
    """
    from augur.fetchers import UaTeamMetaDataFetcher
    fetcher = UaTeamMetaDataFetcher(group_id=group_id, force_update=force_update, uajira=get_jira())
    return fetcher.fetch()


def get_dev_stats(username, look_back_days=30, force_update=False):
    """
    This will get detailed developer stats for the given user.  The stats will go back the number of days
    specified in look_back_days.  It will use the stats stored in the db if the same parameters were queried in
    the past 12 hours.
    :param username: The username of the dev
    :param look_back_days:  The number of days to go back to look for developers details (in both github and jira)
    :param force_update: If True, then this will skip the cache and pull from JIRA
    :return:
    """
    from augur.fetchers import UaDevStatsDataFetcher
    fetcher = UaDevStatsDataFetcher(force_update=force_update, uajira=get_jira())
    return fetcher.fetch(username=username, look_back_days=look_back_days)


def get_all_dev_stats(force_update=False):
    """
    Gets all developer info plus some aggregate data for each user including total points completed.
    :type force_update: bool
    :return:
    """
    from augur.fetchers import UaOrgStatsFetcher
    return UaOrgStatsFetcher(get_jira(), force_update=force_update).fetch()


def get_consultants():
    """
    Retrieves a list of Staff model objects containing all the known consultants.
    :return: An array of Staff objects. 
    """
    cached = get_memory_cached_data("_CONSULTANT_STAFF_")
    if not cached:
        path_to_csv = os.path.join(settings.main.project.augur_base_dir, 'data/engineering_consultants.csv')
        data = AugurModel.import_from_csv(path_to_csv, Staff)
        cached = memory_cache_data(data, "_CONSULTANT_STAFF_")
    return cached


def get_fulltime_staff():
    """
    Retrieves a list of Staff model objects containing all the known FTEs in the engineering group.
    :return: An array of Staff objects. 
    """
    cached = get_memory_cached_data("_FULLTIME_STAFF_")
    if not cached:
        path_to_csv = os.path.join(settings.main.project.augur_base_dir, 'data/engineering_ftes.csv')
        data = AugurModel.import_from_csv(path_to_csv, Staff)
        cached = memory_cache_data(data, "_FULLTIME_STAFF_")
    return cached


def get_team_by_name(name):
    """
    Returns a team object keyed on the name of the team.  If there is more than one team with the same name it will
    always returns only 1.  There is no guarantee which one, though.
    :param name: The name to search for
    :return: A Team object.
    """
    t = filter(lambda x: x.name == name, get_teams())
    return t[0] if t else None


def get_team_by_id(team_id):
    """
    Returns a team object keyed on the name of the team.  If there is more than one team with the same name it will
    always returns only 1.  There is no guarantee which one, though.
    :param team_id: The team id to search for
    :return: A Team object.
    """
    t = filter(lambda x: x.id == team_id, get_teams())
    return t[0] if t else None


def get_teams_as_dictionary():
    """
    Gets all teams as dictionary instead of a list.  The keys of the dictionary are the team_ids
    :return: Returns a dictionary of Team objects
    """
    return {o.id: o for o in get_teams()}


def get_teams():
    """
    Retrieves a list of team objects containing all the known teams in e-comm
    :return: An array of Team objects. 
    """
    cached = get_memory_cached_data("_TEAMS_")
    if not cached:
        path_to_csv = os.path.join(settings.main.project.augur_base_dir, 'data/teams.csv')
        data = AugurModel.import_from_csv(path_to_csv, Team)
        cached = memory_cache_data(data, "_TEAMS_")
    return cached


def get_products():
    """
    Retrieves a list of product objects containing all the known product groups in e-comm
    :return: An array of Product objects. 
    """
    cached = get_memory_cached_data("_PRODUCTS_")
    if not cached:
        path_to_csv = os.path.join(settings.main.project.augur_base_dir, 'data/products.csv')
        data = AugurModel.import_from_csv(path_to_csv, Product)
        cached = memory_cache_data(data, "_PRODUCTS_")
    return cached


def get_active_epics(force_update=False):
    """
    Retrieves epics that have been actively worked on in the past X days
    :return: A dictionary of epics
    """
    from augur.fetchers import RecentEpicsDataFetcher
    fetch = RecentEpicsDataFetcher(uajira=get_jira(), force_update=force_update)
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
        return copy.deepcopy(CACHE[key])
    else:
        return None


def cache_data(document, key):
    """
    Store arbitrary data in the cache 
    :param document: The data to store (json object)
    :param key: The key to uniquely identify this object with
    :return: None
    """
    mongo = cache_store.UaStatsDb()
    cache = UaCachedResultSets(mongo)
    cache.save_with_key(document, key)
    return document


def get_cached_data(key, override_ttl=None):
    """
    Retrieved data cached using "cache_data" function
    :param key: The unique key used to cache this data
    :param override_ttl: The ttl for the data if different from default (this is the number of seconds to save)
    :return: Returns a JSON object loaded from the cache or None if not found
    """

    mongo = cache_store.UaStatsDb()
    cache = UaCachedResultSets(mongo)
    return cache.load_from_key(key, override_ttl=override_ttl)


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

    # if we have already stored fields, re-use
    fields_json = get_memory_cached_data('custom_fields')
    if not fields_json:
        # cache the fields for later
        fields_json = memory_cache_data(get_jira().jira.fields(), 'custom_fields')

    if fields_json:
        for f in fields_json:
            if f['name'].lower() == name.lower():
                return f['id']

    return None
