from munch import munchify
from augur.events import EventData


class JenkinsEventData(EventData):
    """
    Wraps a jira webhook event to make data access easier.
    """
    def __init__(self, event_data):
        self.data = munchify(event_data)

    @property
    def org_url(self):
        try:
            return self.data.orgUrl
        except AttributeError:
            return None


    @property
    def pr(self):
        try:
            parts = self.branch.split("-")
            if len(parts) > 1 and parts[0].lower() == "pr":
                return int(parts[1])
            else:
                return 0
        except AttributeError:
            return 0

    @property
    def branch(self):
        try:
            return self.data.branchName
        except AttributeError:
            return None

    @property
    def org_and_repo_name(self):
        return "%s/%s"%(self.org_name,self.repo_name)

    @property
    def team_name(self):
        """
        Determines the team name based on an organization name that has this format: "Team<Name>"
        :return: Returns the team name or None if no recognizable team name.
        """
        if 'team' in self.org_name.lower():
            parts = self.org_name.split("Team")
            if len(parts) >= 2:
                return parts[1]

        return None

    @property
    def org_name(self):
        try:
            return self.data.orgName
        except AttributeError:
            return None

    @property
    def repo_url(self):
        try:
            return self.data.repoUrl
        except AttributeError:
            return None

    @property
    def repo_name(self):
        try:
            return self.data.repoName
        except AttributeError:
            return None

    @property
    def build_url(self):
        try:
            return self.data.buildUrl
        except AttributeError:
            return None

    @property
    def build_number(self):
        try:
            return self.data.buildNum
        except AttributeError:
            return None

    @property
    def commit_hash(self):
        try:
            return self.data.commitHash
        except AttributeError:
            return None

    @property
    def commit_url(self):
        try:
            return self.data.commitUrl
        except AttributeError:
            return None

    @property
    def tickets(self):
        """
        Returns a list of the issue keys associated with the build. Should usually be only one in the list.
        :return: Returns a list.
        """
        try:
            return self.data.jiraTickets
        except AttributeError:
            return None

    @property
    def docker_image(self):
        try:
            return self.data.dockerImage
        except AttributeError:
            return None

