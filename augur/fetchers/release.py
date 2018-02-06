import arrow
import datetime

from arrow import Arrow

import augur
from augur.common import cache_store, POSSIBLE_DATE_TIME_FORMATS, projects_to_jql
from augur.fetchers.fetcher import AugurDataFetcher


class AugurRelease(AugurDataFetcher):
    """
    Retrieves analyzed data returned from a filter that has been already created in Jira
    """

    def __init__(self, augurjira, context=None, force_update=False):
        super(AugurRelease, self).__init__(augurjira, force_update=force_update, context=context)
        self.start = None
        self.end = None

    def init_cache(self):
        self.cache = cache_store.AugurReleaseData(self.augurjira.mongo)

    def cache_data(self, data):
        self.recent_data = data
        self.cache.save(self.recent_data)
        return self.recent_data

    def get_cached_data(self):
        self.recent_data = self.cache.load_release_data(start=self.start.datetime, end=self.end.datetime,
                                                        context=self.context)

        # when retrieving from cache, we get a list back by default.  we don't want that.
        if isinstance(self.recent_data, list) and len(self.recent_data) > 0:
            self.recent_data = self.recent_data[0]

        return self.recent_data

    def validate_input(self, **args):
        if 'start' not in args or 'end' not in args:
            raise LookupError("You must specify a start and end date for releases")
        else:
            if isinstance(args['start'], Arrow):
                self.start = args['start']
            elif isinstance(args['start'], (str,unicode)):
                self.start = arrow.get(args['start'], POSSIBLE_DATE_TIME_FORMATS).replace(tzinfo=None)
            elif isinstance(args['start'], datetime.datetime):
                self.start = arrow.get(args['start'])
            else:
                raise TypeError("Invalid start date type given.  Must be Arrow, string or datetime")

            if isinstance(args['end'], Arrow):
                self.end = args['end']
            elif isinstance(args['start'], (str,unicode)):
                self.end = arrow.get(args['end'], POSSIBLE_DATE_TIME_FORMATS).replace(tzinfo=None)
            elif isinstance(args['end'], datetime.datetime):
                self.end = arrow.get(args['end'])
            else:
                raise TypeError("Invalid start date type given.  Must be Arrow, string or datetime")

        return True

    def _fetch(self):

        start_str = self.start.format("YYYY/MM/DD HH:mm")
        end_str = self.end.format("YYYY/MM/DD HH:mm")

        analysis = augur.api.get_jql_analysis(
            "%s AND (status in (\"Resolved\") AND status changed to \"Production\" "
            "during ('%s','%s')) order by updated asc" % (projects_to_jql(self.context.workflow), start_str, end_str),
            context=self.context)

        released_tickets = []

        epic_field_name = augur.api.get_issue_field_from_custom_name('Epic Link')
        team_field_name = augur.api.get_issue_field_from_custom_name('Dev Team')
        points_field_name = augur.api.get_issue_field_from_custom_name('Story Points')
        bug_count = 0
        task_story_count = 0
        for key,issue in analysis['issues'].iteritems():

            epic_issue = None
            parent_issue = None
            points = 0

            if issue['fields']['issuetype']['name'].lower() in ('bug','defect'):
                bug_count += 1
            else:
                task_story_count += 1

            if points_field_name in issue['fields']:
                points = issue['fields'][points_field_name]

            if issue['fields']['issuetype']['subtask']:
                # get the parent ticket instead
                parent_key = issue['fields']['parent']['key']
                parent_issue = augur.api.get_issue_details(parent_key)
                if parent_issue:
                    epic_issue = augur.api.get_epic_from_issue(parent_issue)

                    if not points:
                        points = parent_issue['fields'][points_field_name] if points_field_name in parent_issue['fields'] else 0
            else:
                if epic_field_name in issue['fields'] and issue['fields'][epic_field_name]:
                    epic_issue = augur.api.get_epic_from_issue(issue)

            if epic_issue:
                issue['epic_summary'] = "%s: %s" % (epic_issue['key'],epic_issue['fields']['summary']) \
                    if epic_issue else None
            else:
                issue['epic_summary'] = None

            issue['team'] = issue['fields'][team_field_name]['value'] if team_field_name in issue['fields'] else "Unknown"
            issue['parent'] = parent_issue
            issue['points'] = points

            released_tickets.append(issue)

        return self.cache_data({
            'start_date': self.start,
            'end_date': self.end,
            'total_points': analysis['total_points'],
            'bug_count': bug_count,
            'feature_count': task_story_count,
            'issues': released_tickets
        })
