"""
This module contains utility functions for formatting various types into
strings in a way that is consistent throughout augur.
"""
import re
import datetime
from math import floor

REGEX_TIMEDELTA = re.compile(r'(?P<days>[\d.]+)d,(?P<hours>[\d.]+)h$')


def unformat_timedelta(value):
    """
    Takes a timedelta that is formatted using the default representation
    and turns it into a timedelta again.  Note that this is not recommended
    and is deprecated
    """
    out = re.match(REGEX_TIMEDELTA, value).groupdict({"days": "0", "hours": "0"})
    return datetime.timedelta(days=int(out['days']), minutes=int(out['hours']))


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
