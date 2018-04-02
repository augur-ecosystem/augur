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
import shutil
from fabric.api import local


def make_project_path(proj_rel_path):
    """
    Create an absolute path to the project using the given relative path.
    which
    Args:
        proj_rel_path(str): The relative path (from the project root)
    """
    return os.path.join(os.path.dirname(__file__), proj_rel_path)


def bump_version(version_type="patch"):
    """
    Bumps the version for the package - this can bump major, minor or patch
    Args:
        version_type (str): The version order to increment (can be major,minor,patch)
    """
    version_file_path = make_project_path('augur/VERSION')
    with open(version_file_path, 'r+') as version_file:
        lines = list(version_file)
        if lines:
            version = lines[0]
            version_parts = collections.OrderedDict({'major': None, 'minor': None, 'patch': None})
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
        bump_version_type(str): None to NOT bump a version, otherwise it can be
                            one of "major","minor","patch"
        upload(bool): If True, this will be published to the configurated
                            repo
        update_in_vcs(bool): Changes made to the project will be committed
                                if set to True.
    """
    # Check for version bump
    if bump_version_type:
        bump_version(bump_version_type)

    if update_in_vcs:
        # Update git
        print "Updating in git"
        augur_root = make_project_path("")
        local("git -C %s add ." % augur_root)
        local('git -C %s commit -m "version bump and prep for publish"' % augur_root)
        local('git -C %s push' % augur_root)

    # Build/Publish
    root_path = make_project_path("")

    print "Building package in %s" % root_path
    local("cd %s; python setup.py build" % (root_path))

    if upload:
        print "Uploading to artifact repository..."
        local("cd %s; python setup.py sdist upload " % (root_path))
