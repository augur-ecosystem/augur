class WebhookListener(object):
    def __init__(self, hook_filter):
        self.filter = hook_filter

    def execute(self, action, event):
        raise NotImplemented
