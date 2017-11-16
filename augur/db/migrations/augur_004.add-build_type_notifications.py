"""
add notifications
"""

from yoyo import step

__depends__ = {'__init__', 'augur_003.add-notifications.py'}

steps = [

    step("""
    ALTER TABLE notifications ADD COLUMN IF NOT EXISTS build_types VARCHAR(255) DEFAULT 'all' 
    """),
]
