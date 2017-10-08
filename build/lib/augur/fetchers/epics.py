import augur
from augur.common import deep_get, cache_store
from augur.fetchers import AugurDataFetcher
from augur.integrations import augurjira


class RecentEpicsDataFetcher(AugurDataFetcher):
    """
    Retrieves epics that have tickets that are in current,open sprints
    """

    def init_cache(self):
        self.cache = cache_store.RecentEpicData(self.augurjira.mongo)

    def cache_data(self, data):
        self.recent_data = data
        self.cache.save(self.recent_data)
        return self.recent_data

    def get_cached_data(self):
        self.recent_data = self.cache.load_recent_epics(context=self.context)
        return self.recent_data

    def validate_input(self, **args):
        return True

    def _get_jql_for_unresolved_tickets_in_open_sprints(self):
        """
        :return:
        """
        project_jql = augurjira.projects_to_jql(self.context.workflow)
        in_progress_statues = map(lambda x: x.tool_issue_status_name, self.context.workflow.in_progress_statuses())
        return "%s and sprint in openSprints() and " \
               "sprint not in futureSprints() and status in ('%s')" % \
               (project_jql, "','".join(in_progress_statues))

    def _fetch(self):

        jql = self._get_jql_for_unresolved_tickets_in_open_sprints()
        active_issues = self.augurjira.execute_jql(jql)

        epics = {}
        total_active_issues = 0
        for issue in active_issues:
            total_active_issues += 1
            epic_key = deep_get(issue, 'fields', augur.api.get_issue_field_from_custom_name('Epic Link'))
            if epic_key:
                if epic_key in epics:
                    epics[epic_key]["issues"].append(issue)
                else:
                    epics[epic_key] = {
                        "issues": [issue],
                        "info": None
                    }

        if len(epics) > 0:
            active_epics = self.augurjira.execute_jql("key in ('%s')" % "','".join(epics.keys()))
            for epic in active_epics:
                epics[epic['key']]["info"] = epic

        return self.cache_data({
            'total_active_issues': total_active_issues,
            'epics': epics
        })
