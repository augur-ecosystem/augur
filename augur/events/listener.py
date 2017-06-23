import logging


class WebhookListener(object):
    def __init__(self, hook_filter):
        self.filter = hook_filter
        self.logger = logging.getLogger('webhooks')

    def execute(self, action, event):
        raise NotImplemented
