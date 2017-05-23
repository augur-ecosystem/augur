from augur import settings
from augur import api
from augur.common import cache_store
from augur.fetchers.fetcher import UaDataFetcher

FILTER_IDLE = 33280
FILTER_SUPER_IDLE = 32389
FILTER_ORPHANED = 32390
FILTER_UNPOINTED = 32388


class UaDashboardFetcher(UaDataFetcher):
    """
    Retrieves analyzed data returned from a filter that has been already created in Jira
    """

    def init_cache(self):
        self.cache = cache_store.UaDashboardData(self.uajira.mongo)

    def cache_data(self, data):
        self.recent_data = data
        self.cache.save(self.recent_data)
        return self.recent_data

    def get_cached_data(self):
        self.recent_data = self.cache.load()
        return self.recent_data

    def validate_input(self, **args):
        return True

    def _fetch(self):
        # in this case we try to update the data in the data store since there are more possibilities
        # and we don't have a cron job that updates the data in the background.  So it has to be updated by
        # visits to the page with the same user and the same look back days

        devs = api.get_all_developer_info(self.force_update)

        idle = api.get_filter_analysis(FILTER_IDLE)
        super_idle = api.get_filter_analysis(FILTER_SUPER_IDLE)
        no_epics = api.get_filter_analysis(FILTER_ORPHANED)

        active_epics = api.get_active_epics(self.force_update)

        def alert_type(low, medium, val):
            return "urgent" if val > medium else "notice" if val > low else "normal"

        data = {
            'devs': devs,
            'num_devs': len(devs['devs']),
            'active_epics': active_epics,
            'idle': {
                'filter': FILTER_IDLE,
                'link': "%s/issues/?filter=%d" % (settings.main.integrations.jira.instance, FILTER_IDLE),
                'linkText': "View in JIRA",
                'tickets': idle,
                'alert_type': alert_type(20, 50, idle['ticket_count'])

            },
            'super_idle': {
                'filter': FILTER_SUPER_IDLE,
                'link': "%s/issues/?filter=%d" % (settings.main.integrations.jira.instance, FILTER_SUPER_IDLE),
                'linkText': "View in JIRA",
                'tickets': super_idle,
                'alert_type': alert_type(1, 5, super_idle['ticket_count'])

            },
            'no_epics': {
                'filter': FILTER_ORPHANED,
                'link': "%s/issues/?filter=%d" % (settings.main.integrations.jira.instance, FILTER_ORPHANED),
                'linkText': "View in JIRA",
                'tickets': no_epics,
                'alert_type': alert_type(1, 5, no_epics['ticket_count'])
            }
        }

        return self.cache_data(data)
