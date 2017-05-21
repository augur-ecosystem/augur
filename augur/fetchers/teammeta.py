import augur
from augur import settings
from augur.common import const, teams, cache_store
from augur.fetchers.fetcher import UaDataFetcher
from augur.models import AugurModel


class UaJiraTeamMetaDataFetcher(UaDataFetcher):
    def init_cache(self):
        self.cache = cache_store.UaAllTeamsData(self.uajira.mongo)

    def cache_data(self, data):
        self.recent_data = data
        self.cache.save(self.recent_data)
        return self.recent_data

    def get_cached_data(self):
        self.recent_data = self.cache.load()
        if self.recent_data:
            # First check to see if the teams that are stored are different than the ones supported.
            # If they are then force a refresh of the cache
            returned_ids = set(map(lambda x: x['id'], self.recent_data[0]['teams'].values()))
            supported_ids = set(teams.get_all_teams().keys())
            if len(returned_ids.difference(supported_ids)) != 0:
                self.recent_data = None
            else:
                # when retrieving from cache, we get a list back by default.  we don't want that.
                if isinstance(self.recent_data, list):
                    self.recent_data = self.recent_data[0]

        return self.recent_data

    def validate_input(self, **args):
        return True

    def _fetch(self):
        team_json = {'teams': {}}
        groups = self.uajira.get_group_data()
        flat = {}
        consultants = augur.api.get_consultants()
        fulltime = augur.api.get_fulltime_staff()
        all_staff = consultants + fulltime

        team_json['consultant_count'] = 0
        team_json['fulltime_count'] = 0
        team_json['engineer_count'] = 0
        team_json['team_count'] = 0
        FUNNELS_BY_TEAM = teams.team_to_funnel_map()
        for group in groups:
            if group.startswith('Team'):
                if group not in const.JIRA_TEAM_EXCLUSIONS and group in const.JIRA_TEAM_BY_FULL_NAME:
                    members = self.uajira.get_group_members(group)
                    for username, member in members.iteritems():
                        team_id = const.JIRA_TEAM_BY_FULL_NAME[group]
                        member['funnel'] = FUNNELS_BY_TEAM[team_id]
                        staff_member = AugurModel.find_model_in_collection(all_staff, "jira_username", username)
                        if staff_member:
                            member['is_consultant'] = True if not staff_member.company or \
                                                              staff_member.company == "Under Armour" else False
                            member['vendor'] = staff_member.company
                            member['start_date'] = staff_member.start_date
                        else:
                            member['is_consultant'] = False
                            member['vendor'] = ""
                            member['start_date'] = ""

                        if username not in flat:
                            member['team_id'] = team_id
                            member['team_name'] = group
                            flat[username] = member

                        if member['is_consultant']:
                            team_json['consultant_count'] += 1
                        else:
                            team_json['fulltime_count'] += 1

                        team_json['engineer_count'] += 1

                    team_json['team_count'] += 1

                    board_id = const.JIRA_TEAMS_RAPID_BOARD[const.JIRA_TEAM_BY_FULL_NAME[group]]
                    board_link = "%s/secure/RapidBoard.jspa?rapidView=%d" % (
                    settings.main.integrations.jira.instance, board_id)
                    team_json['teams'][group] = {
                        'members': members,
                        'board_id': board_id,
                        'board_link': board_link,
                        'id': const.JIRA_TEAM_BY_FULL_NAME[group],
                        'full': group
                    }

        team_json['devs'] = flat

        # Get a flat list of developers

        return self.cache_data(team_json)
