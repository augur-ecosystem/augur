import StringIO
import csv

from augur.actions.action import Action
from augur.common import const
from augur.integrations.uajira import get_jira


class TeamReportAction(Action):
    def __init__(self, args):
        super(TeamReportAction, self).__init__(args)

    def __str__(self):
        return "Teams"

    def _get_template(self):
        return "teams.html"

    def _is_team_lead(self, username):
        if 'Team Leads' in self.report_data_json['teams']:
            return username in self.report_data_json['teams']['Team Leads']
        else:
            return False

    def supported_formats(self):
        return [const.OUTPUT_FORMAT_JSON, const.OUTPUT_FORMAT_HTML]

    def render(self, output_format):
        if output_format == const.OUTPUT_FORMAT_CSV:
            output = StringIO.StringIO()
            fieldnames = ['fullname', 'email', 'username', 'active', 'team', 'is_team_lead']
            csvwriter = csv.DictWriter(output, fieldnames=fieldnames)
            output.write(",".join(fieldnames) + "\n")
            for teamname, team in self.report_data_json['teams'].iteritems():
                for username, user in team.iteritems():
                    val = user
                    val['team'] = teamname
                    val['username'] = username
                    csvwriter.writerow(val)

            return output.getvalue()

        else:
            return super(TeamReportAction, self).render(output_format)

    def run(self):
        """
        Gets all the team members organized by team
        :return:
        """

        json_output = {
            "teams": {},
            "report": str(self),
        }

        groups = get_jira().get_jira().groups("Team ")
        for group in groups:
            if group.startswith('Team'):
                members = get_jira().get_jira().group_members(group)
                json_output['teams'][group] = members

        self.report_data_json = json_output

        # add additional data that is only available after the team info has all been collected.
        for teamname, team in self.report_data_json['teams'].iteritems():
            for username, user in team.iteritems():
                user['is_team_lead'] = self._is_team_lead(username)

