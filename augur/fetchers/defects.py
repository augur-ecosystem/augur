import datetime
from collections import defaultdict

import arrow

from augur import common
from augur.common import cache_store
from augur.fetchers.fetcher import UaDataFetcher

SEVERITIES = ["Critical", "High", "Medium", "Low"]
PRIORITIES = ["Blocker", "Immediate", "High", "Medium", "Low"]
IMPACTS = ["All", "Large", "Medium", "Small", "Tiny"]


class UaJiraDefectFetcher(UaDataFetcher):
    """
    Retrieves defect data for a given period of time in the past.
    """

    def init_cache(self):
        self.cache = cache_store.UaJiraDefectData(self.uajira.mongo)

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
                return "https://underarmour.atlassian.net/issues/?jql=key in (%s)" % (",".join(issues))
            else:
                return "https://underarmour.atlassian.net/issues/?jql=key in (%s)" % (
                ",".join([i['key'] for i in issues]))

        links = {
            "current_period": {
                "all": generate_link_from_issues(data['current_period']),
                "severity": {key: generate_link_from_issues(value)
                             for (key, value) in data['grouped_by_severity_current'].iteritems()},
                "priority": {key: generate_link_from_issues(value)
                             for (key, value) in data['grouped_by_priority_current'].iteritems()},
                "impact": {key: generate_link_from_issues(value)
                           for (key, value) in data['grouped_by_impact_current'].iteritems()},
            },
            "previous_period": {
                "all": generate_link_from_issues(data['previous_period']),
                "severity": {key: generate_link_from_issues(value)
                             for (key, value) in data['grouped_by_severity_previous'].iteritems()},
                "priority": {key: generate_link_from_issues(value)
                             for (key, value) in data['grouped_by_priority_previous'].iteritems()},
                "impact": {key: generate_link_from_issues(value)
                           for (key, value) in data['grouped_by_impact_previous'].iteritems()},

            }
        }

        return links

    def _fetch(self):

        defects = self.uajira.execute_jql("project in (Engineering, Defects) AND issuetype = Bug "
                                          "AND created >= startOfDay(-%dd) "
                                          "ORDER BY created DESC" % self.lookback_days)

        defects_previous_period = self.uajira.execute_jql("project in (Engineering, Defects) AND issuetype = Bug "
                                                          "AND created >= startOfDay(-%dd) and created <= "
                                                          "startOfDay(-%dd) ORDER BY created DESC"
                                                          % (self.lookback_days * 2, self.lookback_days))

        grouped_by_severity_current = defaultdict(list)
        grouped_by_severity_previous = defaultdict(list)

        grouped_by_priority_current = defaultdict(list)
        grouped_by_priority_previous = defaultdict(list)

        grouped_by_impact_current = defaultdict(list)
        grouped_by_impact_previous = defaultdict(list)

        defects_json = []
        defects_previous_period_json = []

        def get_bug_info(issue):
            sev = issue.fields.customfield_10300.value if issue.fields.customfield_10300 else "NotSet"
            prior = issue.fields.priority.name if issue.fields.priority else "NotSet"
            imp = issue.fields.customfield_16200.value if issue.fields.customfield_16200 else "NotSet"
            return sev, prior, imp

        for defect in defects:
            defects_json.append(defect.raw)
            severity, priority, impact = get_bug_info(defect)
            grouped_by_severity_current[severity].append(defect.key)
            grouped_by_priority_current[priority].append(defect.key)
            grouped_by_impact_current[impact].append(defect.key)

        for defect in defects_previous_period:
            defects_previous_period_json.append(defect.raw)
            severity, priority, impact = get_bug_info(defect)
            grouped_by_severity_previous[severity].append(defect.key)
            grouped_by_priority_previous[priority].append(defect.key)
            grouped_by_impact_previous[impact].append(defect.key)

        stats = {
            "lookback_days": self.lookback_days,
            "current_period": defects_json,
            "previous_period": defects_previous_period_json,
            "grouped_by_severity_current": dict(grouped_by_severity_current),
            "grouped_by_severity_previous": dict(grouped_by_severity_previous),
            "grouped_by_priority_current": dict(grouped_by_priority_current),
            "grouped_by_priority_previous": dict(grouped_by_priority_previous),
            "grouped_by_impact_current": dict(grouped_by_impact_current),
            "grouped_by_impact_previous": dict(grouped_by_impact_previous)
        }

        stats['links'] = self._generate_links(stats)

        return self.cache_data(stats)


class UaJiraDefectHistoryFetcher(UaDataFetcher):
    """
    Retrieves defect data segmented by week over a period of weeks that is given as a parameter
    """

    def init_cache(self):
        self.cache = cache_store.UaJiraDefectHistoryData(self.uajira.mongo)

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

            defects = self.uajira.execute_jql("project in (ENG, DEF) AND issuetype = Bug "
                                              "AND created >= '%s' AND created <= '%s' "
                                              "ORDER BY created DESC" % (start_str, end_str))

            weeks.append({
                "start": start_str,
                "end": end_str,
                "defects": [d.raw for d in defects]
            })

            # shift to previous week.
            start_date = arrow.get(start_date).replace(days=-7)

        stats = {
            "num_weeks": self.num_weeks,
            "weeks": weeks
        }

        return self.cache_data(stats)
