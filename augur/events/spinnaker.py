import copy

from munch import munchify
from augur.events import EventData

# Deployment?
#   event.payload.type = ["orca:task:starting","orca:task:complete"]
#   event.payload.content.
#   event.payload.content.context.application = "ua"
#   event.payload.content.context.deployment (exists)

class SpinnakerEventData(EventData):
    """
    Wraps a jira webhook event to make data access easier.
    """
    def __init__(self, event_data):
        self.data = munchify(event_data)

        # save this the first time the property is called below
        #   so we don't have to build it every time.
        self._image_desc = None


    @property
    def type(self):
        try:
            return self.data.payload.details.type
        except AttributeError:
            return None

    @property
    def application(self):
        try:
            return self.data.payload.details.application
        except AttributeError:
            return None

    @property
    def account(self):
        try:
            return self.data.payload.content.execution.account
        except AttributeError:
            return None

    @property
    def task_name(self):
        try:
            return self.data.payload.content.taskName
        except AttributeError:
            return None

    @property
    def org_and_repo(self):
        return "%s/%s"%(self.image_desc.repo, self.image_desc.org)

    @property
    def image_desc(self):
        """
        """
        try:
            if not self._image_desc:
                desc = self.data.payload.content.context.containers[0].imageDescription
                tag = desc.tag
                org,branch,commit,docker = tag.split("-")
                self._image_desc = munchify({
                    "org": org,
                    "repo": desc.repository,
                    "artifact": desc.imageId,
                    "branch": branch,
                    "commit": commit,
                    "docker": docker
                })

            return self._image_desc

        except AttributeError:
            return None

    @property
    def commit_hash(self):
        desc = self.image_desc
        return desc.commit if desc else None

    @property
    def org(self):
        desc = self.image_desc()
        return desc.org if desc else None

    @property
    def is_deployment(self):
        try:
            return 'deployment' in self.data.payload.content.context
        except AttributeError:
            return False

    @property
    def environment(self):
        try:
            return self.data.payload.content.context.account
        except AttributeError:
            return None
