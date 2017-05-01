import os
import re

import arrow
import datetime
import pytz

__author__ = 'karim'


import comm
import const
import teams
import serializers
import formatting
import projects

import json
import dateutil
from dateutil.parser import parse
from math import sqrt
import const

JIRA_KEY_REGEX = r"([A-Za-z]+\-\d{1,6})"

COMPLETE_STATUSES = ["complete","resolved"]
POSITIVE_RESOLUTIONS = ["fixed", "done", "deployed"]
_CACHE = {}

SITE_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))


class Struct:
    """
        Create objects out of dictionaries like this:
        >>> d = {"test":1,"foo":"bar"}
        >>> s = Struct(**d)
        >>> s.test
    """
    def __init__(self, **entries):
        self.__dict__.update(entries)


def set_cache(namespace, key, value):
    global _CACHE

    if namespace not in _CACHE:
        _CACHE[namespace] = {key: value}
    else:
        _CACHE[namespace][key] = value


def get_cache(namespace, key):
    global _CACHE

    if not isinstance(key, (str, unicode)):
        return None

    return _CACHE[namespace][key] if (namespace in _CACHE and key in _CACHE[namespace]) else None


def get_team_args(uajira, args):
    """
    Gets the teams that are specified on the command line (in a form that is useable by actions).  Or it returns all
    teams if no team was specified.  The information about the teams is pulled from JIRA but the short name associations
    are hard coded as constants in the script
    :param uajira: The UaJira object representing the Jira instance
    :param args: The args that were parsed on the command line
    :return: A dictionary of teams
    """
    custom_teams = {}
    if args.teams is not None and len(args.teams) > 0:
        for t in args.teams:
            t = t.strip()
            team_data = teams.get_team_from_short_name(t)
            if team_data:
                custom_teams[t] = team_data['team_name']
    else:
        custom_teams = teams.get_all_teams().copy()

    # Now get the details for each of the selected teams from the automatically generated
    #   data pulled from JIRA
    team_info = uajira.get_all_developer_info()
    for shortname, info in custom_teams.iteritems():
        if info['team_name'] in team_info['teams']:
            custom_teams[shortname] = team_info['teams'][info['team_name']]

    return custom_teams


def remove_null_fields(issue_fields):
    return dict((k, v) for k, v in issue_fields.iteritems() if v)
    # return {k: v for (k, v) in issue_fields.iteritems() if v}


def jira_store(jira, key, data):
    issue = jira.issue(key)

    try:
        import serializers
        ob_str = json.dumps(data, cls=serializers.UaJsonEncoder)
        issue.update(description=ob_str)
    except TypeError, e:
        print "Invalid JSON: " + e.message
    except ValueError, e:
        print "Invalid JSON: " + e.message


def jira_load(uajira, key):
    issue = uajira.get_jira().issue(key)
    ob_str = issue.fields.description
    try:
        return json.loads(ob_str)
    except TypeError, e:
        print "Invalid JSON: " + e.message
    except ValueError, e:
        print "Invalid JSON: " + e.message

def parse_sprint_info(sprint_string):
    m = re.match(".*\[(.*)\]", sprint_string)
    if m and m.groups() > 1:
        props = m.group(1)
        sprint_ob = {}
        for prop in props.split(","):
            key, value = prop.split("=")

            try:
                # if it's a date, convert it.
                if key in ['startDate', 'endDate', 'completeDate']:
                    sprint_ob[key] = dateutil.parser.parse(value)
            except ValueError:
                pass
            finally:
                if key not in sprint_ob:
                    if value == '<null>':
                        sprint_ob[key] = None
                    else:
                        sprint_ob[key] = value

        return sprint_ob

    return None

def utc_to_local(utc_dt):
    local_tz = pytz.timezone('America/New_York')
    return utc_dt.replace(tzinfo=pytz.utc).astimezone(local_tz)


def extract_jira_tickets(text):
    """
    Gets a list of all the JIRA keys found in the given text
    :param text: The string to search
    :return: A list of strings
    """
    match = re.search(JIRA_KEY_REGEX,text)
    if match:
        return match.groups()
    else:
        return []


def transform_status_string(status):
    return status.lower().replace(' ','_')


def get_week_range(date):
    """
    This will return the start and end of the week in which the given date resides.
    :param date: The source date
    :return: A tuple containing the start and end date of the week (in that order)
    """
    start = date - datetime.timedelta(days=date.weekday())
    end = start + datetime.timedelta(days=6)
    return start,end


def standard_deviation(lst,population=True):

    sd = 0

    try:
        num_items = len(lst)

        if num_items == 0:
            return 0

        mean = sum(lst) / num_items
        differences = [x - mean for x in lst]
        sq_differences = [d ** 2 for d in differences]
        ssd = sum(sq_differences)

        if population is True:
            variance = ssd / num_items
        elif num_items > 1:
            variance = ssd / (num_items - 1)
        else:
            variance = 0

        sd = sqrt(variance)

    except Exception, e:
        print "Problem during calculation of standard deviation: %s"%e.message

    return sd


def get_date_range_from_query_params(request,default_start=None,default_end=None):
    start = request.GET.get('start', None)
    end = request.GET.get('end', None)
    return get_date_range_from_strings(start,end,default_start,default_end)


def get_date_range_from_strings(start,end, default_start=None, default_end=None):
    if not start:
        # Don't go back further than 90 days for the sake of performance and storage.
        start = default_start
    else:
        start = arrow.get(start, "YYYY-MM-DD").floor('day')

    if not end:
        end = default_end
    else:
        end = arrow.get(end, "YYYY-MM-DD").ceil('day')

    return start,end


def simplify_issue(issue):
    return {
        "key": issue.key,
        "severity": issue.fields.customfield_10300.value if issue.fields.customfield_10300 else None,
        "priority": issue.fields.priority.name if issue.fields.priority else None,
        "summary": issue.fields.summary,
        "points": issue.fields.customfield_10002,
        "description": issue.fields.description,
        "devteam":issue.fields.customfield_13306.value if issue.fields.customfield_13306 else None,
        "reporter": issue.fields.reporter.key if issue.fields.reporter else None,
        "assignee": issue.fields.assignee.key if issue.fields.assignee else None,
        "components": [x.name for x in issue.fields.components],
        "sprints": issue.fields.customfield_10401,
        "creator": issue.fields.creator.key
    }


def deep_get(dictionary,*keys):
    """
    Retrieves a deeply nested dictionary key checking for existing keys along the way.  Returns None if any key
    is not found.
    :param dictionary: The dictionary to retrieve the data from.
    :param default: The default value to return if there is a problem during the search
    :param keys: Ordered parameters representing the keys (in the order they should be referenced)
    :return: Returns the value if found, None otherwise.
    """
    return reduce(lambda d, key: d.get(key) if d else None, keys, dictionary)
