from augur import common
from augur import settings
from augur import api
from augur.common import cache_store
from augur.integrations.uajira.data.uajiradata import UaJiraDataFetcher

FILTER_IDLE = 33280
FILTER_SUPER_IDLE = 32389
FILTER_ORPHANED = 32390
FILTER_UNPOINTED = 32388


class UaJiraDashboardFetcher(UaJiraDataFetcher):
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

        devs = api.get_all_developer_info()

        def get_issue_seconds_in_progress(idx, issue_iter):
            return issue_iter['time_in_progress'] + \
                   issue_iter['time_integration'] + \
                   issue_iter['time_quality_review'] + \
                   issue_iter['time_staging'] + \
                   issue_iter['time_production'] + \
                   issue_iter['time_blocked']

        # For 7 day run of completed tickets, get more information than just the count of tickets
        completed_tickets = api.get_filter_analysis("33690")

        real_tickets = []
        tickets_with_no_time_in_progress = []
        tickets_abandoned = []
        real_story_points = 0.0
        for issue in completed_tickets['issues'].values():

            if issue['resolution'] in common.POSITIVE_RESOLUTIONS:
                if issue['time_in_progress'] > 0:
                    real_tickets.append(issue)
                    real_story_points += issue['points']
                else:
                    tickets_with_no_time_in_progress.append(issue)
            else:
                tickets_abandoned.append(issue)

        # Average time to complete
        average_seconds_in_progress = \
            reduce(get_issue_seconds_in_progress, real_tickets, 0) / len(completed_tickets['issues'])

        idle = api.get_filter_analysis(FILTER_IDLE)
        super_idle = api.get_filter_analysis(FILTER_SUPER_IDLE)
        no_epics = api.get_filter_analysis(FILTER_ORPHANED)
        unpointed_in_progress = api.get_filter_analysis(FILTER_UNPOINTED)

        def alert_type(low, medium, val):
            return "urgent" if val > medium else "notice" if val > low else "normal"

        data = {
            'devs': devs,
            'num_devs': len(devs['devs']),
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

            },
            'unpointed_in_progress': {
                'filter': FILTER_UNPOINTED,
                'link': "%s/issues/?filter=%d" % (settings.main.integrations.jira.instance, FILTER_UNPOINTED),
                'linkText': "View in JIRA",
                'tickets': unpointed_in_progress,
                'alert_type': alert_type(1, 5, unpointed_in_progress['ticket_count'])

            },
            'completed_this_sprint': {
                'filter': "33688",
                'tickets': real_tickets,
                'points': real_story_points,
                'average_time_to_complete': average_seconds_in_progress,
                'average_point_size': round(real_story_points / len(real_tickets) if len(real_tickets) > 0 else 0, 2),
                'abandoned': tickets_abandoned + tickets_with_no_time_in_progress
            }
        }

        return self.cache_data(data)
