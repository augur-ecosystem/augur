import datetime
from collections import defaultdict

import arrow

import augur
from augur import common, settings
from augur.common import cache_store, deep_get
from augur.fetchers.fetcher import AugurDataFetcher
from augur.integrations import augurjira
from augur.integrations.augurjira import AugurJira

SEVERITIES = ["Critical", "High", "Medium", "Low"]
PRIORITIES = ["Blocker", "Immediate", "High", "Medium", "Low"]
IMPACTS = ["All", "Large", "Medium", "Small", "Tiny"]


class AugurDefectFetcher(AugurDataFetcher):
    """
    Retrieves defect data for a given period of time in the past.
    """

    def init_cache(self):
        self.cache = cache_store.AugurJiraDefectData(self.augurjira.mongo)

    def cache_data(self, data):
        self.recent_data = data
        self.cache.save(self.recent_data)
        return self.recent_data

    def get_cached_data(self):
        self.recent_data = self.cache.load_defects(self.lookback_days)
        return self.recent_data

    def validate_input(self, **args):
        if 'lookback_days' not in args:
            raise LookupError("You must specify a number of days to look back for metrics")
        else:
            self.lookback_days = int(args['lookback_days'])

        return True

    @staticmethod
    def _generate_links(data):

        def generate_link_from_issues(issues):
            if len(issues) > 0 and isinstance(issues[0], (str, unicode)):
                return "%s/issues/?jql=key in (%s)" % (settings.main.integrations.jira.instance, ",".join(issues))
            else:
                return "%s/issues/?jql=key in (%s)" % (settings.main.integrations.jira.instance,
                                                       ",".join([i['key'] for i in issues]))

        links = {
            "current_period": {
                "all": generate_link_from_issues(data['current_period']),
                "severity": {key: generate_link_from_issues(value)
                             for (key, value) in data['grouped_by_severity_current'].iteritems()},
                "priority": {key: generate_link_from_issues(value)
                             for (key, value) in data['grouped_by_priority_current'].iteritems()},
            },
            "previous_period": {
                "all": generate_link_from_issues(data['previous_period']),
                "severity": {key: generate_link_from_issues(value)
                             for (key, value) in data['grouped_by_severity_previous'].iteritems()},
                "priority": {key: generate_link_from_issues(value)
                             for (key, value) in data['grouped_by_priority_previous'].iteritems()},

            }
        }

        return links

    def _fetch(self):

        defects = self.augurjira.execute_jql(
            "%s AND created >= startOfDay(-%dd) ORDER BY created DESC" %
            (augurjira.defect_filter_to_jql(self.context.workflow.get_defect_project_filters(), True),
                self.lookback_days))

        defects_previous_period = \
            self.augurjira.execute_jql(
                "%s AND created >= startOfDay(-%dd) and created <= startOfDay(-%dd) ORDER BY created DESC"
                % (augurjira.defect_filter_to_jql(self.context.workflow.get_defect_project_filters(), True),
                    self.lookback_days * 2, self.lookback_days))

        grouped_by_severity_current = defaultdict(list)
        grouped_by_severity_previous = defaultdict(list)

        grouped_by_priority_current = defaultdict(list)
        grouped_by_priority_previous = defaultdict(list)

        defects_json = []
        defects_previous_period_json = []

        severity_field_name = augur.api.get_issue_field_from_custom_name('Severity')

        def get_bug_info(issue):
            sev = deep_get(issue,'fields',severity_field_name,'value') or "NotSet"
            prior = deep_get(issue,'fields','priority','name') or "NotSet"
            return sev, prior

        for defect in defects:
            defects_json.append(defect)
            severity, priority = get_bug_info(defect)
            grouped_by_severity_current[severity].append(defect['key'])
            grouped_by_priority_current[priority].append(defect['key'])

        for defect in defects_previous_period:
            defects_previous_period_json.append(defect)
            severity, priority = get_bug_info(defect)
            grouped_by_severity_previous[severity].append(defect['key'])
            grouped_by_priority_previous[priority].append(defect['key'])

        stats = {
            "lookback_days": self.lookback_days,
            "current_period": defects_json,
            "previous_period": defects_previous_period_json,
            "grouped_by_severity_current": dict(grouped_by_severity_current),
            "grouped_by_severity_previous": dict(grouped_by_severity_previous),
            "grouped_by_priority_current": dict(grouped_by_priority_current),
            "grouped_by_priority_previous": dict(grouped_by_priority_previous),
        }

        stats['links'] = self._generate_links(stats)

        return self.cache_data(stats)


class AugurDefectHistoryFetcher(AugurDataFetcher):
    """
    Retrieves defect data segmented by week over a period of weeks that is given as a parameter
    """

    def init_cache(self):
        self.cache = cache_store.AugurJiraDefectHistoryData(self.augurjira.mongo)

    def cache_data(self, data):
        self.recent_data = data
        self.cache.save(self.recent_data)
        return self.recent_data

    def get_cached_data(self):
        self.recent_data = self.cache.load_defects(self.num_weeks)
        return self.recent_data

    def validate_input(self, **args):
        if 'num_weeks' not in args:
            raise LookupError("You must specify a number of weeks to look back for metrics")
        else:
            self.num_weeks = int(args['num_weeks'])

        return True

    def _fetch(self):

        start_date = datetime.datetime.now()
        weeks = []
        for w in range(self.num_weeks):
            start, end = common.get_week_range(start_date)
            start_str = arrow.get(start).floor('day').format("YYYY/MM/DD HH:mm")
            end_str = arrow.get(end).ceil('day').format("YYYY/MM/DD HH:mm")

            defects = self.augurjira.execute_jql(
                "%s AND created >= '%s' AND created <= '%s' ORDER BY created DESC" %
                (augurjira.defect_filter_to_jql(self.context.workflow.get_defect_project_filters(), True),
                 start_str, end_str))

            weeks.append({
                "start": start_str,
                "end": end_str,
                "defects": defects
            })

            # shift to previous week.
            start_date = arrow.get(start_date).replace(days=-7)

        stats = {
            "num_weeks": self.num_weeks,
            "weeks": weeks
        }

        return self.cache_data(stats)
