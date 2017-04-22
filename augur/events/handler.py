class WebhookHandler(object):
    def __init__(self):
        self.hooks = []
        self.action = None
        self.event = None

    def _process_event(self, event):
        raise NotImplemented()

    def add_listener(self, hook):
        self.hooks.append(hook)

    def handle(self, event):
        self.action = None
        self.event = None

        events = self._process_event(event)
        handled_count = 0
        for h in self.hooks:
            for e in events:
                if h.execute(self.action, e):
                    handled_count += 1

        print "%s action handled by %d listeners" % (self.action, handled_count)
        return handled_count
