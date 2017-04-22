import listener
from augur.events.listeners import transitions

EVENTS = (
    "issue:updated",
    "issue:transitioned",
    "issue:commented",
    "issue:worklog",
    "issue:created",
    "project:updated",
    "project:created"
)

