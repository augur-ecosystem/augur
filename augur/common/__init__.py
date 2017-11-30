import os
import re

import arrow
import datetime
import pytz

import augur

__author__ = 'karim'


import comm
import const
import serializers
import formatting

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


def sprint_belongs_to_team(sprint, team_id):
    """
    Makes a decision about whether the given sprint (represented by a dict returned by the _sprints method
    :param sprint: The abridged version of the sprict dict.
    :param team: The team id
    :return: Returns the True if the sprint belongs to the given team, false otherwise
    """
    sprint_name_parts = sprint['name'].split('-')
    team_from_sprint = ""
    team_from_id = augur.api.get_team_by_id(team_id)
    if len(sprint_name_parts) > 1:
        team_from_sprint = sprint_name_parts[1].strip()

    if not team_from_sprint:
        is_valid_sprint = False
    elif team_from_id.name not in team_from_sprint and team_from_sprint not in team_from_id.name:
        # this checks both directions because it might be that the sprint name uses a
        #   shortened version of the team's name.
        is_valid_sprint = False
    else:
        is_valid_sprint = True

    return is_valid_sprint


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


def deep_get(dictionary, *keys):
    """
    Retrieves a deeply nested dictionary key checking for existing keys along the way.  Returns None if any key
    is not found.
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