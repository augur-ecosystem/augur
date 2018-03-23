import augur
from augur.integrations.objects import JiraObject


class JiraPerson(JiraObject):

    def __init__(self, source, **kwargs):
        super(JiraPerson, self).__init__(source, **kwargs)
        self._jira_person = None
        self._db_person = None

    def _load(self):

        if not self.option('jira_username'):
            self.logger("Cannot initialize JiraPerson without Jira username")

        username = self.option('jira_username')
        self._db_person = augur.api.get_staff_member_by_field(username=username) or None

        if self._db_person:
            if self.option('load_jira_user_data'):
                self.log_access('load-user')

                user = self.source.jira.user(username)
                self._jira_person = user.raw()
