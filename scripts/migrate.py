import os
from yoyo import read_migrations, get_backend
from augur import settings

if __name__ == '__main__':
    settings.load_settings()
    db = settings.main.datastores.main.postgres
    migration_dir = os.path.dirname(os.path.abspath(__file__))

    print "Augur Migration"
    print "---------------"
    print "Host: %s"%db.host
    print "DB Name: %s"%db.dbname
    print "Migration Dir: %s"%migration_dir

    cont = raw_input("Type 'continue' to proceed with the migration: ")
    if cont == "continue":
        print "\nBeginning migration..."
        backend = get_backend('postgres://%s:%s@%s/%s'%(db.username,db.password,db.host,db.dbname))
        migrations = read_migrations(migration_dir)
        backend.apply_migrations(backend.to_apply(migrations))
        print "\nMigrations completed."
    else:
        print "\nMigration cancelled."
