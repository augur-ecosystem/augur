import urllib

from augur import settings
from augur import api
from augur.common import cache_store
from augur.fetchers.fetcher import AugurDataFetcher
from augur.integrations import augurjira

SUPER_IDLE_DAYS = 14
IDLE_DAYS = 5


class AugurDashboardFetcher(AugurDataFetcher):
    """
    Retrieves analyzed data returned from a filter that has been already created in Jira
    """
    def __init__(self,*args,**kwargs):
        super(AugurDashboardFetcher, self).__init__(*args, **kwargs)

    def init_cache(self):
        self.cache = cache_store.AugurDashboardData(self.augurjira.mongo)

    def cache_data(self, data):
        self.recent_data = data
        self.cache.save(self.recent_data)
        return self.recent_data

    def get_cached_data(self):
        self.recent_data = self.cache.load()
        return self.recent_data

    def validate_input(self, **args):
        return True

    def _get_jql_for_idle_tickets(self, idle_days):
        """
        project in (PDC, TOP, POST, ENG, DEF) AND issuetype in (story, task, defect, subtask, bug) AND status not in (resolved, open) AND updated < startOfDay(-2w)
        :return:
        """
        project_jql = augurjira.projects_to_jql(self.context.workflow)
        in_progress_statues = map(lambda x: x.tool_issue_status_name, self.context.workflow.in_progress_statuses())

        if in_progress_statues:
            return "%s and status in ('%s') and updated < -%dd" % (project_jql, "','".join(in_progress_statues), idle_days)
        else:
            None

    def _get_jql_for_orphaned_tickets(self):
        """
        project in (PDC, TOP, POST, ENG, DEF) AND issuetype in (story, task, defect, subtask, bug) AND status not in (resolved, open) AND updated < startOfDay(-2w)
        :return:
        """
        project_jql = augurjira.projects_to_jql(self.context.workflow)
        done_statuses = map(lambda x: x.tool_issue_status_name, self.context.workflow.done_statuses())
        dev_issuetypes = map(lambda x: x.tool_issue_type_name, self.context.workflow.dev_issue_types())

        return "%s and issuetype in ('%s') and issuetype not in subtaskIssueTypes() and status not in ('%s') and \"Epic Link\" is EMPTY" % (project_jql,
                                                                                                       "','".join(dev_issuetypes),
                                                                                                       "','".join(done_statuses))

    def _fetch(self):
        # in this case we try to update the data in the data store since there are more possibilities
        # and we don't have a cron job that updates the data in the background.  So it has to be updated by
        # visits to the page with the same user and the same look back days

        devs = api.get_all_developer_info(context=self.context, force_update=self.force_update)

        # these JQL generators could return None in cases where the data required to generate the JQL is not available.
        idle_jql = self._get_jql_for_idle_tickets(IDLE_DAYS)
        super_idle_jql = self._get_jql_for_idle_tickets(SUPER_IDLE_DAYS)
        orphan_jql = self._get_jql_for_orphaned_tickets()

        idle = api.get_jql_analysis(idle_jql, context=self.context, brief=True) if idle_jql else None
        super_idle = api.get_jql_analysis(super_idle_jql, context=self.context, brief=True) if super_idle_jql else None
        orphaned = api.get_jql_analysis(orphan_jql, context=self.context, brief=True) if orphan_jql else None

        active_epics = api.get_active_epics(context=self.context, force_update=self.force_update)

        def alert_type(low, medium, val):
            return "urgent" if val > medium else "notice" if val > low else "normal"

        data = {
            'devs': devs,
            'num_devs': len(devs['devs']),
            'active_epics': active_epics,
            'idle': {
                'filter': idle_jql,
                'link': "%s/issues/?%s" % (settings.main.integrations.jira.instance,
                                           urllib.urlencode({"jql": idle_jql})),
                'linkText': "View in JIRA",
                'tickets': idle,
                'alert_type': alert_type(20, 50, idle['ticket_count'])

            },
            'super_idle': {
                'filter': super_idle_jql,
                'link': "%s/issues/?%s" % (settings.main.integrations.jira.instance,
                                           urllib.urlencode({"jql": super_idle_jql})),
                'linkText': "View in JIRA",
                'tickets': super_idle,
                'alert_type': alert_type(1, 5, super_idle['ticket_count'])

            },
            'no_epics': {
                'filter': orphan_jql,
                'link': "%s/issues/?%s" % (settings.main.integrations.jira.instance,
                                           urllib.urlencode({"jql": orphan_jql})),
                'linkText': "View in JIRA",
                'tickets': orphaned,
                'alert_type': alert_type(1, 5, orphaned['ticket_count'])
            }
        }

        return self.cache_data(data)
