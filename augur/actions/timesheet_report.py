import StringIO
import csv

from augur import common
from augur.common import const
from augur.actions.action import Action
from augur.integrations.uajira import get_jira


class TimesheetReportAction(Action):
    def __init__(self, args=None):
        super(TimesheetReportAction, self).__init__(args)
        self.subject = "UA Timesheet"
        self.end = None
        self.start = None

    def __str__(self):
        return self.subject

    def _get_template(self):
        return "timesheet.html"

    def supported_formats(self):
        return [const.OUTPUT_FORMAT_CSV, const.OUTPUT_FORMAT_HTML]

    def render(self, output_format):
        if output_format == const.OUTPUT_FORMAT_CSV:
            output = StringIO.StringIO()
            fieldnames = ['fullname', 'total_hours', 'total_cost', 'rate']
            csvwriter = csv.DictWriter(output, fieldnames=fieldnames)
            output.write(",".join(fieldnames) + "\n")
            for username, info in self.report_data_json.iteritems():
                val = {
                    'fullname': "%s,%s" % (info['info']['last_name'], info['info']['first_name']),
                    'total_hours': info['total_hours_for_dev'],
                    'total_cost': info['total_cost_for_dev'],
                    'rate': info['consultant_rate'],
                }
                csvwriter.writerow(val)

            return output.getvalue()

        else:
            return super(TimesheetReportAction, self).render(output_format)

    def run(self):
        """
        Gets all the stale docs organized by team
        :return:
        """
        team_id = self.args.tempoteam
        self.start, self.end = common.get_date_range_from_strings(self.args.start, self.args.end)

        worklogs = get_jira().get_user_worklog(self.start, self.end, int(team_id))
        timesheet = {}

        for log in worklogs['logs']:
            total_hours_for_log = log['timeSpentSeconds'] / 3600.0
            consultant_rate = log['author']['consultant_info']['rate'] \
                if ('consultant_info' in log['author'] and log['author']['consultant_info']) else 0.0

            total_cost_for_log = float(consultant_rate) * total_hours_for_log

            username = log['author']['name']
            if username not in timesheet:
                timesheet[username] = {
                    "info": worklogs['consultants'][username],
                    "total_cost_for_dev": 0,
                    "total_hours_for_dev": 0,
                    "consultant_rate": consultant_rate,
                }
            timesheet[username]['total_cost_for_dev'] += total_cost_for_log
            timesheet[username]['total_hours_for_dev'] += total_hours_for_log

        self.report_data_json = {
            "consultants": timesheet,
            "team": team_id,
            "start": self.start,
            "end": self.end
        }
        self.subject = "UA Timesheet - %s to %s" % (self.start.strftime("%m-%d-%Y"), self.end.strftime("%m-%d-%Y"))

def get_action():
    return TimesheetReportAction