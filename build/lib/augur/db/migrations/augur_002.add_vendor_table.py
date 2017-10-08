
__depends__ = ['augur_001.init']

from yoyo import step

steps = [

    # create the vendor table.
    step("""
        CREATE TABLE vendor
        (
          id SERIAL NOT NULL
            CONSTRAINT vendor_pkey
            PRIMARY KEY,
          name TEXT NOT NULL,
          engagement_contact_first_name TEXT NOT NULL,
          engagement_contact_last_name TEXT NOT NULL,
          engagement_contact_email TEXT NOT NULL,
          billing_contact_first_name TEXT,
          billing_contact_last_name TEXT,
          billing_contact_email TEXT,
          tempo_id INTEGER
        );"""),

    # add foreign key constraints
    step("ALTER TABLE staff ADD COLUMN vendor INT, add constraint fk_vendor_key "
         "foreign key (vendor) references vendor(id); "),
    step("ALTER TABLE staff ADD CONSTRAINT fk_staff__vendor FOREIGN KEY (vendor) REFERENCES vendor(id)"),

    # Add index
    step("CREATE INDEX idx_staff__vendor ON staff (vendor)"),

    # Make company optional
    step("ALTER TABLE staff ALTER COLUMN company DROP NOT NULL;")
]

