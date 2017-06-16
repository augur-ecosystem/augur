TEMPO_API_TOKEN="72c7fe70-eac9-4497-a3a1-e29ce4c47d41"

class UaTempo(object):

    def __init__(self, uajira):
        self.uajira = uajira

    def get_worklogs(self, start, end, team_id, username=None, project_key=None):
        """
        Retrieves the worklogs for a given team, user, and/or project between the given dates.
        :param start: {datetime} The start date
        :param end: {datetime} The end date
        :param team_id: The ID of the team
        :param username: The username to restrict the query to
        :param project_key: The project key to restrict the query to
        :return: Returns a JSON object with the results from the query.
        """
        query = {
            "dateFrom": start.format("YYYY-MM-DD"),
            "dateTo": end.format("YYYY-MM-DD"),
            "teamId": team_id
        }

        if username:
            query['username'] = username

        if project_key:
            query["projectKey"] = project_key

        query['tempoApiToken'] = TEMPO_API_TOKEN

        base = "{server}/rest/tempo-timesheets/3/{path}"
        return self.uajira.jira._get_json("worklogs/",params=query,base=base)

    def get_team_details(self, team_id):
        """
        Retrieves the team info for the given team
        :param team_id: The ID of the team
        :return: Returns a JSON object with the restuls from the query
        """
        if not team_id:
            raise LookupError("You must specify a non-zero team_id to retrieve details")

        base = "{server}/rest/tempo-teams/1/{path}"
        return self.uajira.jira._get_json("team/%d"%int(team_id),base=base)
