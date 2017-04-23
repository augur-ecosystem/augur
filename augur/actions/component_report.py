from augur.actions.action import Action
from augur.common import const
from augur.integrations import uagithub


class ComponentReportAction(Action):
    def __init__(self, args):
        super(ComponentReportAction, self).__init__(args)

    def __str__(self):
        return "Components"

    def _get_template(self):
        return "components.html"

    def supported_formats(self):
        return [const.OUTPUT_FORMAT_JSON, const.OUTPUT_FORMAT_HTML]

    def run(self):
        """
        Gets all the team members organized by team
        :return:
        """
        self.report_data_json = uagithub.UaGithub().get_org_component_data(self.args.org)
