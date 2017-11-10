"""
add notifications
"""

from yoyo import step

__depends__ = {'__init__', 'augur_002.add_vendor_table'}

steps = [
    step("""﻿    
        CREATE TABLE public.notifications (
          id SERIAL NOT NULL,
          build text COLLATE pg_catalog."default" NOT NULL,
          deploy text COLLATE pg_catalog."default" NOT NULL,
          staff integer,
          team integer,
          CONSTRAINT notifications_pkey PRIMARY KEY (id))
    """),

    step("""
    ALTER TABLE staff ADD COLUMN IF NOT EXISTS notification INTEGER 
    """),

    step("""
    ALTER TABLE staff ADD COLUMN IF NOT EXISTS slack_id TEXT 
    """),

    step("""
    ALTER TABLE team ADD COLUMN notification INTEGER 
    """),

    step("""
    ALTER TABLE staff ADD CONSTRAINT fk_staff__notification FOREIGN KEY (notification)
        REFERENCES public.notifications (id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE CASCADE
    """),

    step("""
    ALTER TABLE team ADD CONSTRAINT fk_team__notifications FOREIGN KEY (notification)
        REFERENCES public.notifications (id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE CASCADE 
    """)
]
