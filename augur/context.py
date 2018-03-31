

class AugurContext(object):
    """
    This contains information that is used by the Augur library to identify constraints that should be
    used when requesting data.  The Context object is defined by a "Group".  Groups
    are associated with a workflow, teams and other information.  Many functions within
    augur will require a context object in order to know how to filter and interpret data.
    """

    def __init__(self, group_id):
        from augur import get_group
        self._group = get_group(group_id)
        self._workflow = self.group.workflow

    @property
    def workflow(self):
        return self._workflow

    @property
    def group(self):
        return self._group