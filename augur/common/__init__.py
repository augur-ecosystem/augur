import os
import re
import string

import arrow
import datetime
import pytz
from munch import munchify

import augur
from augur import db

__author__ = 'karim'


import comm
import const
import serializers
import formatting

from math import sqrt
from dateutil.parser import parse

import const

JIRA_KEY_REGEX = r"([A-Za-z]+\-\d{1,6})"

COMPLETE_STATUSES = ["complete","resolved"]
POSITIVE_RESOLUTIONS = ["fixed", "done", "deployed"]
_CACHE = {}

# Note: The order matters in this list.  Time based matches are first to ensure that
#   the time is not truncated in cases where date matches are found then the rest of the
#   list is skipped.
POSSIBLE_DATE_TIME_FORMATS = [
    "YYYY-MM-DD HH:mm",
    "MM-DD-YYYY HH:mm",
    "MM/DD/YYYY HH:mm",
    "YYYY/MM/DD HH:mm",
    "MM/DD/YYYY HH:mm",
    "M/D/YYYY HH:mm",
    "M/D/YY HH:mm",
]

POSSIBLE_DATE_FORMATS = [
    "YYYY-MM-DD",
    "MM-DD-YYYY",
    "MM/DD/YYYY",
    "YYYY/MM/DD",
    "M/D/YYYY",
    "M/D/YY",
]

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


def remove_null_fields(d):
    """
    Takes a dictionary and returns a new dictionary with fields that have null values.
    :param d: A dictionary to remove null fields from
    :return:
    """
    return dict((k, v) for k, v in d.iteritems() if v is not None)


def clean_issue(issue):
    """
    This will put commonly used fields at the root of the dictionary and remove all of the custom fields that are
    empty.
    :param issue: A dict that is the the issue to clean
    :return: Returns a dictionary.
    """
    points_field_name = augur.api.get_issue_field_from_custom_name('Story Points')
    points = augur.common.deep_get(issue, 'fields', points_field_name)
    status = augur.common.deep_get(issue, 'fields', 'status', 'name') or ''
    resolution = augur.common.deep_get(issue, 'fields', 'resolution', 'name') or ''
    return {
        'key': issue['key'],
        'summary': augur.common.deep_get(issue, 'fields', 'summary'),
        'assignee': augur.common.deep_get(issue, 'fields', 'assignee', 'name') or 'unassigned',
        'description': augur.common.deep_get(issue, 'fields', 'description'),
        'fields': remove_null_fields(issue['fields']),
        'points': float(points if points else 0.0),
        'status': status.lower(),
        'changelog': augur.common.deep_get(issue,'changelog'),
        'resolution': resolution.lower(),
    }


def find_team_name_in_string(team_name, string_to_search):
    """
    Utility that searches the given string for the given team name.  It does the work of stripping out the
    word "Team" from the team_name for you so it's more permissive than just doing a substring search.

    :param team_name: The name of the team
    :param string_to_search: The source string to search for the team name
    :return: Returns the True if the name was found, False otherwise.
    """
    # Remove the word "Team" from the team name (if necessary)
    team_replace = re.compile(re.escape('team'), re.IGNORECASE)
    team_name = team_replace.sub('', team_name).strip()
    return team_name.lower() in string_to_search.lower()


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
    return match.groups() or []


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


def deep_get(dictionary, *keys):
    """
    Retrieves a deeply nested dictionary key checking for existing keys along the way.  
    Returns None if any key is not found.
    :param dictionary: The dictionary to retrieve the data from.
    :param default: The default value to return if there is a problem during the search
    :param keys: Ordered parameters representing the keys (in the order they should be referenced)
    :return: Returns the value if found, None otherwise.
    """
    default = None
    return reduce(lambda d, key: d.get(key) if d else default, keys, dictionary)


def calc_weekends(start_day, end_day):
    """
    Calculate the number of weekends in a given date range.
    :param start_day: Start of the range (datetime)
    :param end_day: End of the range  (datetime)
    :return: Returns the number of weekend
    """
    duration = end_day - start_day
    days_until_weekend = [5, 4, 3, 2, 1, 1, 6]
    adjusted_duration = duration - days_until_weekend[start_day]
    if adjusted_duration < 0:
        weekends = 0
    else:
        weekends = (adjusted_duration/7)+1
    if start_day == 5 and duration % 7 == 0:
        weekends += 1
    return weekends


def clean_detailed_sprint_info(sprint_data):
    """
    Takes the given sprint object and cleans it up to replace the date time values to actual python datetime objects.
    :param sprint_data:
    :return:
    """
    # convert date strings to dates
    for key, value in sprint_data['sprint'].iteritems():
        if key in ['startDate', 'endDate', 'completeDate']:
            try:
                sprint_data['sprint'][key] = parse(value)
            except ValueError:
                sprint_data['sprint'][key] = None


def status_to_dict_key(status):
    if isinstance(status, db.ToolIssueStatus):
        status_str = status.tool_issue_status_name
    else:
        status_str = status

    return "%s" % status_str.lower().replace(" ", "_")


def clean_username(username):
    """
    This cleans up a username to ensure it doesn't have any characters that would interfere with things
    like mongo storage, dict key use, database storage, etc.
    :param username:
    :return:
    """
    return username.replace(".", "_")


@staticmethod
def estimate_time_spent_in_hours(issue, statuses):
    """
    Calculates the number of hours spent on a ticket based only on the time spent in a given
    status.  This is useful when the engineer has not been keeping track of work hours using the work log
    feature in Jira.
    :param issue: The issue dict (as retrieved through augurjira)
    :param statuses: A list of statuses (strings).
    :return: Returns a float that equals the number of hours calculated.
    """
    assert issue

    total_hours = 0.0
    for status in statuses:
        timing = AugurJira.get_issue_status_timing_info(issue,status)
        if timing:
            timing = Munch(timing)
            total_hours += timing.total_time.hours()
            if timing.total_time.days() > 0:
                # if more than a day then we have to adjust the total hours to take into account
                #   that people don't work 24 hours a day. We also have to make sure that we exclude
                #   weekend hours.
                num_weekends = calc_weekends(timing.start_time, timing.end_time)
                num_weekend_days = num_weekends*2
                num_work_days = timing.total_time.days() - num_weekend_days
                total_hours += num_work_days*8
    return total_hours


def get_issue_status_timing_info(issue, status):
    """
    Gets a single tickets timing information including when in started, ended and the total time in the status.
    :param issue: The ticket in dictionary form
    :param status: The ToolIssueStatus to look for.
    :return: Returns a dict containing:
                start_time: datetime when the issue first started in the status
                end_time: datetime when the issue last left the status
                total_time: timedelta with the total time in status
    """
    status_name = status.tool_issue_status_name
    track_time = None
    total_time = datetime.timedelta()

    if 'changelog' not in issue or not issue['changelog']:
        return {
            "start_time":None,
            "end_time":None,
            "total_time":datetime.timedelta(seconds=0)
        }

    history_list = issue['changelog']['histories']

    # added sorting past > present because the API is inconsistently ordering the results.
    history_list.sort(key=lambda x: x['id'], reverse=False)

    start_time = None
    end_time = None
    for history in history_list:
        items = history['items']

        for item in items:
            if item['field'] == 'status' and item['toString'].lower() == status_name.lower():
                # start status
                track_time = parse(history['created'])
                if not start_time:
                    start_time = track_time

                break
            elif track_time and item['field'] == 'status' and item['fromString'].lower() == status_name.lower():
                # end status
                if track_time:
                    # only recalculate if track_time has a value.  It can happen that track_time has no
                    # value if the API only returns X number of historical items and the
                    total_time += (parse(history['created']) - track_time)
                track_time = None
                break

    if track_time and not total_time:
        # In this case the issue is currently in the requested status which means we need to set the "end" time to
        #   NOW because there's no record of the *next* status to subtract from.
        end_time = utc_to_local(datetime.datetime.now())
        total_time = end_time - track_time
    else:
        end_time = track_time

    return munchify({
        "start_time":start_time,
        "end_time":end_time,
        "total_time":total_time
    })

def get_time_in_status(issue, status):
    """
    Gets a single tickets time in a given status.  Calculates by looking at the history for the issue
    and adding up all the time that the ticket was in the given status.
    :param issue: The ticket in dictionary form
    :param status: The ToolIssueStatus to look for.
    :return: Returns the datetime.timedelta time in status.
    """
    timing_info = get_issue_status_timing_info(issue,status)
    if timing_info:
        return timing_info['total_time']
    else:
        return None


def project_key_from_issue_key(issue_key):
    """
    Gets the project key from an issue key
    :param issue_key: The issue key to parse
    :return: Returns None if invalid issue key given.
    """
    try:
        project_key, val = issue_key.split("-")
        return project_key
    except ValueError:
        return None


def positive_resolution_jql(workflow):
    """
    Returns a JQL segment that filters based on done statuses and positive resolutions for the given workflow.
     > e.g. ((status in (resolve,closed) and resolution in ("fixed","done", "complete")
    :param workflow: The workflow object to use as a source for information about what constitutes positive resolution
    :return: Returns the JQL
    """
    done_statuses = [d.tool_issue_status_name for d in workflow.done_statuses()]
    done_resolutions = [d.tool_issue_resolution_name for d in workflow.positive_resolutions()]

    return "(status in (\"%s\") and resolution in (\"%s\"))" % ('","'.join(done_statuses), '","'.join(done_resolutions))


def defect_filter_to_jql(defect_filters, include_issue_types=True):
    jql_list = []
    for d in defect_filters:
        if include_issue_types:
            jql_list.append("(project = %s and issuetype in ('%s'))" %
                            (d.project_key, "','".join(d.get_issue_types_as_string_list())))
        else:
            jql_list.append("(project = %s)" % d.project_key)

    return "((%s))" % ") OR (".join(jql_list)


def projects_to_jql(workflow):
    """
    Gets the projects information and returns a jql string that can be embedded directly into a larger jql
    :return: Returns a string containing the jql
    """
    keys = []
    for p in workflow.projects:
        keys.append(p.tool_project_key)

    categories = []
    for c in workflow.categories:
        categories.append(c.tool_category_name)

    jql_projects = ""
    jql_categories = ""
    if len(keys) > 0:
        jql_projects = "project in (%s)" % ",".join(keys)

    if len(categories) > 0:
        jql_categories = "category in ('%s')" % "','".join(categories)

    if jql_projects and jql_categories:
        return "((%s) OR (%s))" % (jql_projects, jql_categories)
    else:
        return jql_projects if jql_projects else jql_categories