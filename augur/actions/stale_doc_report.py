from pyfluence import Confluence

from augur import settings
from augur.actions.action import Action
from augur.common import const, comm
from augur.integrations.uajira import get_jira

INVALID_USERS = {
    'progers': "pbrown2@underarmour.com",
    'groffman': "chris.tate@twintechs.com",
    'tcrider': "kchung3@underarmour.com",
    'ashirk': "dducharme@underarmour.com",
    'klindenboom': "lwilson1@underarmour.com",
    'bmotlagh': "kshehadeh@underarmour.com",
    'jsmulison': "kshehadeh@underarmour.com",
    "jammond": "hnuss@underarmour.com",
    "msiddeeq": "lwilson1@underarmour.com",
    "hgilmore": "schaki@underarmour.com",
    "ksankuru": "dducharme@underarmour.com",
    "bmendenhall": "rwilson1@underarmour.com",
    "jmessenger": "kvalencik@underarmour.com"
}


class StaleDocReportAction(Action):
    """
    Retrieves a list of all confluence articles that have not been updated in over <stale_duration_weeks> weeks.

    Parameters:
        * stale_duration_weeks - (optional) The number of weeks back in time that an article has been updated before which
                                it will be considered "stale". (default = 24)
        * email_authors - (optional) A boolean indicating whether or not authors should be emailed separately when
                            they have an article that hasn't been updated in over x weeks. (default = True)
    """

    def __init__(self, args):
        super(StaleDocReportAction, self).__init__(args)

        if not hasattr(self.args, "stale_duration_weeks"):
            self.args.stale_duration_weeks = 24

        # by default we email the most recent updaters of the pages that haven't been updated in over X weeks.
        if not hasattr(self.args,"email_authors"):
            self.args.email_authors = True

    def __str__(self):
        return "Stale Confluence Document Report"

    def _get_template(self):
        return "docs_by_user.html"

    def supported_formats(self):
        return [const.OUTPUT_FORMAT_HTML]

    def run(self):
        """
        Gets all the stale docs organized by team
        :return:
        """
        uaj = get_jira()
        con = Confluence(settings.main.integrations.jira.username,
                         settings.main.integrations.jira.password, settings.main.integrations.confluence.url)
        space = self.args.space
        data = con.search(
            "type=page and space=%s and label not in (\"ecomm-archived\") and lastModified < now('-%dw')" %
                    (space,int(self.args.stale_duration_weeks)),
            expand=["history", "version"])

        pages_by_user = {}
        for page_data in data['results']:
            page_id = page_data['content']['id']
            page = con.get_content(page_id, expand=["version"])
            user = page['version']['by']['username']
            if user not in pages_by_user:
                pages_by_user[user] = []
            pages_by_user[user].append(page)

        # now send emails (unless parameters says not to)
        if self.args.email_authors:
            for user, pages in pages_by_user.iteritems():
                user_ob = uaj.jira.user(user)
                email = user_ob.emailAddress
                body = self._render_template("stale_page_email.html", {'user': user, 'pages': pages})

                if user in INVALID_USERS:
                    email = INVALID_USERS[user]
                else:
                    if not email:
                        email = "kshehadeh@underarmour.com"

                # only send
                comm.send_email_aws(to_addresses=[email],
                                    subject="%d stale confluence pages found for %s" % (len(pages), user), body_html=body)

        self.report_data_json = {
            "pages_by_user": pages_by_user
        }
