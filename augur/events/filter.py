
class WebhookFilter(object):
    def __init__(self,actions=None, projects=None,fields=None,reporters=None,assignees=None):

        self.filter = {
            "actions": actions,
            "projects": projects,
            "fields": fields,
            "reporters": reporters,
            "assignees": assignees
        }
        self.filter_audit = None
        self.reset_filter()

    def reset_filter(self):
        self.filter_audit = {f:None for f in self.filter.keys()}

    def allow(self,action, event):
        raise NotImplemented

