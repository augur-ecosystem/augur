import datetime

from augur.models import AugurModel
from augur.models.staff import Staff
from augur.models.team import Team


class StatusType(object):
    """
    A status type indicates the nature of the status (as in open,in progress or done)
    """
    Todo = "todo"
    InProgress = "inprogress"
    Done = "done"


class LinkSide(object):
    """
    Indicates which side of the link the entity is on (left or right). As in left -> right
    """
    Left = "left"
    Right = "right"


class TicketType(AugurModel):
    """
    The type of a ticket.  For example, a ticket can represent a bug, a story an epic or a task among other things.
    """
    Story = "story",
    Epic = "epic",
    Task = "task",
    SubTask = "subtask",
    Bug = "bug",

    def _add_properties(self):
        self.add_prop("id", unicode)
        self.add_prop("name", "", unicode)
        self.add_prop("type", "", unicode)
        self.add_prop("is_child", False, bool)


class TicketChange(AugurModel):
    """
    Represents an action that occured in a ticket.  This is the base class for other changes.  A change has a date
    of change but other details can be indicated in the derived classes.
    """
    def __init__(self):
        super(TicketChange, self).__init__()

    def __repr__(self):
        return str(self.name)

    def _add_properties(self):
        super(TicketChange, self)._add_properties()
        self.add_prop("time",None, datetime.datetime)


class StatusChange(TicketChange):
    """
    A type of ticket change, this is a change to the status of a ticket.
    """
    def __init__(self):
        super(StatusChange, self).__init__()

    def __repr__(self):
        return "Status Change - From {source} to {dest}".format(source=self.source.name,
                                                                dest=self.dest.name)

    def _add_properties(self):
        super(StatusChange, self)._add_properties()
        self.add_prop("source", None, Status)
        self.add_prop("dest", None, Status)


class Link(AugurModel):
    """
    Represents a link between two tickets.  A link has a left side and a right side.  Which side a ticket is on
    has no bearing on anything but the text that appears in the containing ticket.
    """
    def __init__(self):
        super(Link, self).__init__()

    def __repr__(self):
        return str(self.link_name)

    def _add_properties(self):
        self.add_prop("link_type","", unicode)
        self.add_prop("link_name","", unicode)
        self.add_prop("side", LinkSide.Left, unicode)


class Status(AugurModel):
    """
    The status of a ticket represents the state that the ticket is in.  A status is part of a workflow.  One status 
    leads to another status.  But certain statuses may not be connected to others. 
    """
    def __init__(self):
        super(Status,self).__init__()

    def _add_properties(self):
        self.add_prop("name", "", unicode)
        self.add_prop("type", StatusType.Todo, unicode)


class Ticket(AugurModel):
    """
    A ticket represents a unit of work that is assignable and has state.  Assignees move tickets from one state to
    another following a workflow.
    """
    def __init__(self):
        super(Ticket, self).__init__()

    def __repr__(self):
        return str(self.name)

    def _add_properties(self):
        self.add_prop("id", "", unicode)
        self.add_prop("summary", "", unicode)
        self.add_prop("description", "", unicode)
        self.add_prop("points", 0.0, float)
        self.add_prop("status", None, Status)
        self.add_prop("links", [], list)
        self.add_prop("team", None, Team)
        self.add_prop("assignee", None, Staff)
        self.add_prop("reporter", None, Staff)
        self.add_prop("created", None, datetime.datetime)
        self.add_prop("updated", None, datetime.datetime)
        self.add_prop("labels", [], list)
        self.add_prop("subtasks", [], list)
        self.add_prop("type", TicketType.Story, unicode)

        # keeps track of the changes that occured in the ticket over time
        self.add_prop("changes", [], list)

if __name__ == '__main__':
    pass