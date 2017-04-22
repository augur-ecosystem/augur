from augur.events.filter import WebhookFilter


class JiraWebhookFilter(WebhookFilter):

    def __init__(self,actions=None, projects=None,fields=None,reporters=None,assignees=None):
        super(JiraWebhookFilter, self).__init__(projects=projects,fields=fields,reporters=reporters,assignees=assignees)

    def allow(self, action, event):

        self.reset_filter()

        self.filter_audit['actions'] = self.filter['actions'] and action not in self.filter['actions']
        self.filter_audit['projects'] = self.filter['projects'] and event.issue.fields.project.key not in self.filter['projects']

        self.filter_audit['fields'] = self.filter['fields'] and event.changelog.current.field not in self.filter['fields']

        if event.issue.fields.reporter:
            self.filter_audit['reporters'] = self.filter['reporters'] and event.issue.fields.reporter.name not in self.filter['reporters']
        else:
            self.filter_audit['reporters'] = self.filter['reporters'] is None

        if event.issue.fields.assignee:
            self.filter_audit['assignees'] = self.filter['assignees'] and event.issue.fields.assignee.name not in self.filter['assignees']
        else:
            self.filter_audit['assignees'] = self.filter['assignees'] is None

        return reduce(lambda prev,current: current != False if prev else False,self.filter_audit)