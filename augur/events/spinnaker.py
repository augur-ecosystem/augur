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
        self._stage_context = None
        self._gh_context = None

    @property
    def type(self):
        try:
            return self.data.payload.details.type
        except AttributeError:
            return None

    @property
    def stage_name(self):
        try:
            return self.data.payload.content.context.stageDetails.type
        except AttributeError:
            return None


    @property
    def pipeline_name(self):
        try:
            return self.data.payload.content.execution.name
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
        try:
            return "%s/%s"%(self.org, self.repo)
        except (AttributeError,ValueError,IndexError):
            return ""

    @property
    def stage_context(self):
        if not self._stage_context:
            sn = self.stage_name
            stage = filter(lambda s: s.type == sn, self.data.payload.content.execution.stages)
            if len(stage) > 0:
                self._stage_context = stage[0]

        return self._stage_context

    @property
    def ghcheck_stage_context(self):
        if not self._gh_context:
            stage = filter(lambda s: s.name.lower() == 'gh-check', self.data.payload.content.execution.stages)
            if len(stage) > 0:
                self._gh_context = stage[0]

        return self._gh_context

    @property
    def repo(self):
        try:
            return self.ghcheck_stage_context.context.pipelineParameters.APPLICATION
        except AttributeError:
            return ""

    @property
    def org(self):
        try:
            parts = self.ghcheck_stage_context.context.pipelineParameters.ARTIFACT.split("-")
            if len(parts):
                return parts[0]

        except (ValueError, AttributeError):
            return ""

    @property
    def artifact(self):
        try:
            return self.ghcheck_stage_context.context.pipelineParameters.ARTIFACT
        except(ValueError,AttributeError):
            return ""

    @property
    def commit_hash(self):
        try:
            parts = self.ghcheck_stage_context.context.pipelineParameters.ARTIFACT.split("-")
            if len(parts):
                return parts[-2]
        except (ValueError, AttributeError):
            return ""

    @property
    def environment(self):
        try:
            # we use the pipeline name as a way to determine where this is being deployed.  If it
            #   ends in -staging then it's staging, if it ends in anything else its production
            full_env = self.pipeline_name
            parts = full_env.split("-")
            if len(parts) and parts[-1] == "staging":
                return "staging"
            else:
                return "production"
        except (AttributeError, ValueError):
            return ""
