import arrow

import augur # required - do not remove
from augur.common import cache_store
from augur.fetchers.fetcher import UaDataFetcher


class UaWorklogDataFetcher(UaDataFetcher):
    """
    Retrieves processed worklog data
    """
    def __init__(self, uajira, force_update=False):
        self.start = None
        self.end = None
        self.team_id = None
        self.username = None
        self.project = None
        super(UaWorklogDataFetcher, self).__init__(uajira, force_update)

    def init_cache(self):
        self.cache = cache_store.UaJiraWorklogData(self.uajira.mongo)

    def cache_data(self, data):
        self.recent_data = data
        self.cache.save(self.recent_data)
        return self.recent_data

    def get_cached_data(self):
        self.recent_data = self.cache.load_worklog(start=self.start, end=self.end,
                                                   username=self.username, team_id=self.team_id,
                                                   project=self.project)
        return self.recent_data

    def validate_input(self, **args):
        if not set(args.keys()).issuperset({'start', 'end', 'team_id'}):
            raise LookupError("The worklog data input requires the following input: start, end, team_id")
        else:
            self.start = arrow.get(args['start'])
            self.end = arrow.get(args['end'])
            self.team_id = args['team_id']

            if 'username' not in args and 'project' not in args:
                raise LookupError("You must have a username OR a project in the input parameters")

            if 'username' in args:
                self.username = args['username']
            else:
                self.username = None

            if 'project_key' in args:
                self.project = args['project_key']
            else:
                self.project = None

        return True

    def _fetch(self):

        worklogs = self.uajira.get_worklog_raw(
            start=self.start,
            end=self.end,
            team_id=self.team_id,
            username=self.username,
            project_key=self.project)

        if worklogs:
            return self.cache_data({
                'start': self.start.datetime,
                'end': self.end.datetime,
                'team_id': self.team_id,
                'username': self.username,
                'project': self.project,
                'consultants': worklogs['consultants'],
                'logs': worklogs['logs'],
                'tempo_team_info': worklogs['tempo_team_info']
            })
        else:
            raise Exception("The specified worklogs could not be found")
