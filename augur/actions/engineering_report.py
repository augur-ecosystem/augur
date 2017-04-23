from augur.actions.action import Action
from augur.common import const
from augur.integrations.uajira import get_jira


class EngineeringReportAction(Action):
    def __init__(self, args):
        super(EngineeringReportAction, self).__init__(args)
        self.subject = "Engineering Report"

    def __str__(self):
        return self.subject

    def _get_template(self):
        return "engineering_report.html"

    def supported_formats(self):
        return [const.OUTPUT_FORMAT_HTML]

    def run(self):
        """
        Gets all the stale docs organized by team
        :return:
        """
        self.report_data_json = get_jira().get_engineering_report(self.args.week_number)
        self.subject = "%d Engineering Report - Week %d" % (self.report_data_json['start'].year,
                                                            int(self.report_data_json['week_number']))
