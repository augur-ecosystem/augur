import json
import os
import re

import arrow
import datetime
import pytz
from munch import munchify

import augur
from augur import db

__author__ = 'karim'

from math import sqrt, floor
from dateutil.parser import parse

JIRA_KEY_REGEX = r"([A-Za-z]+\-\d{1,6})"

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


class AugurJsonEncoder(json.JSONEncoder):
    def default(self, obj):
        from augur.context import AugurContext

        if isinstance(obj, datetime.timedelta):
            return obj.total_seconds()
        elif isinstance(obj, datetime.datetime):
            return obj.isoformat()
        elif isinstance(obj, datetime.date):
            return obj.isoformat()
        elif isinstance(obj, Resource):
            return obj.raw
        elif isinstance(obj, AugurContext):
            return {
                "group_id": obj.group.id
            }

        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, obj)


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


def get_date_from_week_number(week_number):
    year = datetime.datetime.now().year
    conversion_str = "%d-W%d" % (year, int(week_number))
    return datetime.datetime.strptime(conversion_str + '-1', "%Y-W%W-%w")


def format_timedelta(value, time_format="{days} days, {hours2}:{minutes2}:{seconds2}", time_format_no_days="{hours}h"):
    """
    Formats timedelta and uses the following options for the formatting string:
        seconds:        Seconds, no padding
        seconds2:       Seconds with zero padding
        minutes:        Minutes, no padding
        minutes:        Minutes with zero padding
        hours:          Hours, no padding
        hours2:         Hours with zero padding
        days:           Days (when used in conjuction with other units - not total)
        years:          Years (when used in conjuction with other units - not total)
        seconds_total:  The total number of seconds
        minutes_total   The total number of minutes
        hours_total:    The total number of hours
        days_total:     The total number of days
        years_total:    The total number of years

        Example:
            "{days} days, {hours2}:{minutes2}:{seconds2}"
        will format into something like:
            "3 days, 02:20:00"
    Args:
        value(datetime.timedelta): The value to format
        time_format(str): The patter to format into (see description for options)
    """
    if hasattr(value, 'seconds'):
        seconds = value.seconds + value.days * 24 * 3600
    else:
        seconds = int(value)

    seconds_total = seconds

    minutes = int(floor(seconds / 60))
    minutes_total = minutes
    seconds -= minutes * 60

    hours = int(floor(minutes / 60))
    hours_total = hours
    minutes -= hours * 60

    days = int(floor(hours / 24))
    days_total = days
    hours -= days * 24

    years = int(floor(days / 365))
    years_total = years
    days -= years * 365

    if days_total > 0:
        return time_format.format(**{
            'seconds': seconds,
            'seconds2': str(seconds).zfill(2),
            'minutes': minutes,
            'minutes2': str(minutes).zfill(2),
            'hours': hours,
            'hours2': str(hours).zfill(2),
            'days': days,
            'years': years,
            'seconds_total': seconds_total,
            'minutes_total': minutes_total,
            'hours_total': hours_total,
            'days_total': days_total,
            'years_total': years_total,
        })
    else:
        return time_format_no_days.format(**{
            'seconds': seconds,
            'seconds2': str(seconds).zfill(2),
            'minutes': minutes,
            'minutes2': str(minutes).zfill(2),
            'hours': hours,
            'hours2': str(hours).zfill(2),
            'days': days,
            'years': years,
            'seconds_total': seconds_total,
            'minutes_total': minutes_total,
            'hours_total': hours_total,
            'days_total': days_total,
            'years_total': years_total
        })
