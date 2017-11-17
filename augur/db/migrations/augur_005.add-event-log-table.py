"""
add notifications
"""

from yoyo import step

__depends__ = {'__init__', 'augur_004.add-build_type_notifications.py'}

steps = [

    step("""
    CREATE TABLE eventlog
    (
        id SERIAL NOT NULL 
            CONSTRAINT eventlog_pkey
                primary key,
        event_time TIMESTAMP NOT NULL,
        event_type TEXT NOT NULL,
        event_data JSONB
    ) 
"""),
]
