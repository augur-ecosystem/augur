import datetime

import arrow

from augur.actions.action import Action
from augur.common import const
from augur.integrations.uajira import get_jira


class ReleaseReportAction(Action):
    def __init__(self, args=None):
        super(ReleaseReportAction, self).__init__(args)
        self.subject = "Released Tickets"

    def __str__(self):
        return self.subject

    def _get_template(self):
        return "release.html"

    def supported_formats(self):
        return [const.OUTPUT_FORMAT_HTML]

    def run(self):
        """
        Gets all the stale docs organized by team
        :return:
        """
        uaj = get_jira()
        issues = uaj.execute_jql(
            "project in (CM) AND (status=\"Production Deployed\" OR status = \"Production Validated\") AND (status changed to \"Production Deployed\" during (startOfDay(-1d),startOfDay()))")

        released_tickets = []

        release_date = arrow.get(datetime.datetime.now()).replace(days=-1).format('ddd, MMM D YYYY')
        for issue in issues:
            links = issue.fields.issuelinks

            if isinstance(links, list) and len(links) > 0:
                for link in links:
                    if int(link.type.id) == 10653:

                        # append the associated cm to the ticket.
                        linked_issue = None
                        if hasattr(link, 'outwardIssue'):
                            linked_issue = link.outwardIssue
                        elif hasattr(link, 'inwardIssue'):
                            linked_issue = link.inwardIssue

                        if linked_issue:
                            linked_issue.cm = issue
                            released_tickets.append(linked_issue)

        self.report_data_json = {
            'release_date': release_date,
            'issues': released_tickets
        }
        self.subject = "UA.com Changes Released to Production on %s" % release_date

def get_action():
    return ReleaseReportAction