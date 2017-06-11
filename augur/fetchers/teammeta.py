import augur
import augur.api
from augur import settings
from augur.common import const, cache_store
from augur.fetchers.fetcher import UaDataFetcher
from augur.models import AugurModel


class UaTeamMetaDataFetcher(UaDataFetcher):
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
            supported_ids = set(augur.api.get_teams_as_dictionary().keys())
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

        consultants = augur.api.get_consultants()
        fulltime = augur.api.get_fulltime_staff()
        all_staff = consultants + fulltime

        team_json = {
            'teams': {},
            'consultant_count': 0,
            'fulltime_count': 0,
            'engineer_count': 0,
            'team_count': 0
        }

        team_objects = augur.api.get_teams()

        flat = {}
        for team_ob in team_objects:
            members_json = {}
            members = team_ob.member_ids
            for username in members:
                staff_ob = AugurModel.find_model_in_collection(all_staff, "jira_username", username)
                member = {
                    'funnel': team_ob.product_id
                }

                if not staff_ob:
                    raise LookupError("A staff member was listed as part of a team but that staff member was not found")

                member['email'] = staff_ob.email
                member['is_consultant'] = staff_ob.rate == 0.0
                member['vendor'] = staff_ob.company
                member['start_date'] = staff_ob.start_date
                member['fullname'] = staff_ob.first_name + " " + staff_ob.last_name

                if username not in flat:
                    member['team_id'] = team_ob.id
                    member['team_name'] = team_ob.name
                    flat[username] = member

                if member['is_consultant']:
                    team_json['consultant_count'] += 1
                else:
                    team_json['fulltime_count'] += 1

                team_json['engineer_count'] += 1

                members_json[username] = member

            team_json['team_count'] += 1

            sprint = augur.api.get_abridged_team_sprint(team_ob.id)
            board_id = team_ob.board_id
            board_link = "%s/secure/RapidBoard.jspa?rapidView=%d" % (settings.main.integrations.jira.instance, board_id)
            team_json['teams'][team_ob.name] = {
                'members': members_json,
                'board_id': board_id,
                'board_link': board_link,
                'sprint': sprint,
                'id': team_ob.id,
                'full': team_ob.name
            }

        team_json['devs'] = flat

        # Get a flat list of developers

        return self.cache_data(team_json)

