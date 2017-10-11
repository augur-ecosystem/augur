"""
The fabfile contains utilities necessary for publishing, building, incrementing versions,
database migrations, etc.  To use, install fabric:
> pip install fabric

Commands map to functions in this file.  Pass parameters using the :param=value:param=value...
format as in:
> fab bump_version:version_type=patch

That will bump the patch segment of the VERSIONS file by 1.
"""

import os
import collections
import json
import shutil
from fabric.api import local
from yoyo import read_migrations, get_backend
from augur import settings

def make_project_path(proj_rel_path):
    """
    Create an absolute path to the project using the given relative path.
    which
    Args:
        proj_rel_path(str): The relative path (from the project root)
    """
    return os.path.join(os.path.dirname(__file__),proj_rel_path)

def bump_version(version_type="patch"):
    """
    Bumps the version for the package - this can bump major, minor or patch
    Args:
        type (str): The version order to increment (can be major,minor,patch)
    """
    version_file_path = make_project_path('augur/VERSION')    
    with open(version_file_path, 'r+') as version_file:
        lines = list(version_file)
        if lines:
            version = lines[0]
            version_parts = collections.OrderedDict({'major':None,'minor':None,'patch':None})
            version_parts['major'], version_parts['minor'], version_parts['patch'] = version.split(".")

            zero_following_versions = False
            for part in ["major", "minor", "patch"]:
                if zero_following_versions:
                    # zero these out if a higher order version number was bumped
                    version_parts[part] = str(0)
                elif version_type == part:
                    # if the user wants to bump this version then increment by 1
                    temp = int(version_parts[part])
                    temp += 1
                    version_parts[part] = str(temp)
                    zero_following_versions = True

    with open(version_file_path, 'w+') as version_file:
        version_file.write(".".join(version_parts.values()))        

def publish(bump_version_type=None, upload=False, update_in_vcs=False):
    """
    Build, publish and/or bump the version

    Args:
        bump_version(str): None to NOT bump a version, otherwise it can be
                            one of "major","minor","patch"
        upload(bool): If True, this will be published to the configurated
                            repo
        update_in_vcs(bool): Changes made to the project will be committed
                                if set to True.
    """
    # Make sure the readmes are the same
    print "Copying README.md to README"
    
    source_readme = make_project_path('README.md')
    dest_readme = make_project_path('README')
    shutil.copyfile(source_readme,dest_readme)    

    # Check for version bump
    if bump_version_type:
        bump_version(bump_version_type)
    
    if update_in_vcs:
        # Update git
        print "Updating in git"
        augur_root = make_project_path("")
        local("git -C %s add ."%augur_root)
        local('git -C %s commit -m "version bump and prep for publish"'%augur_root)
        local('git -C %s push'%augur_root)

    # Build/Publish
    root_path = make_project_path("")
    path_to_setup = make_project_path("setup.py")

    print "Building package in %s"%root_path
    local("cd %s; python setup.py build"%(root_path))
    
    if upload:
        print "Uploading to artifact repository..."
        local("cd %s; python setup.py sdist upload -r local "%(root_path))

def run_migrations():
    load_local_settings()    
    db = settings.main.datastores.main.postgres
    migration_dir = make_project_path("augur/db/migrations")

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

def load_local_settings():
    local_settings_filepath = make_project_path('config/local.json')

    with open(local_settings_filepath,'r+') as local_settings_file:
        local_settings = json.load(local_settings_file)
        for key,val in local_settings.iteritems():
            os.environ[key] = val
    
    settings.load_settings()

if __name__ == "__main__":
    load_local_settings()

    for key,val in os.environ.iteritems():
        print "%s=%s"%(key,val)
