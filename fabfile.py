from fabric.api import run, local
import os

def make_project_path(proj_rel_path):
    """
    Create an absolute path to the project using the given relative path.
    which
    Args:
        proj_rel_path(str): The relative path (from the project root)
    """
    return os.path.join(dir(__file__),proj_rel_path)

def bump_version(version_type="patch"):
    """
    Bumps the version for the package - this can bump major, minor or patch
    Args:
        type (str): The version order to increment (can be major,minor,patch)
    """
    version_file = make_project_path('augur/VERSION')    
    with open(version_file, 'r+') as version_file:
        lines = list(version_file)
        if lines:
            version = lines[0]
            major_val, minor_val, patch_val = version.split(".")
            zero_following_versions = False
            for part in ["major", "minor", "patch"]:
                if zero_following_versions:
                    # zero these out if a higher order version number was bumped
                    locals()[part+"_val"] = str(0)
                elif version_type == part:
                    # if the user wants to bump this version then increment by 1
                    temp = int(locals()[part+"_val"])
                    temp += 1
                    locals()[part+"_val"] = str(temp)
                    zero_following_versions = True

    with open(version_file, 'w+') as version_file:
        version_file.write(".".join([major_val, minor_val,patch_val]))

def publish(bump_version_type=None, upload=False):
    """
    Build, publish and/or bump the version

    Args:
        bump_version(str): None to NOT bump a version, otherwise it can be
                            one of "major","minor","patch"
    """
    # Make sure the readmes are the same
    print "Copying README.md to README"
    local("cp README.md README")

    # Check for version bump
    if bump_version_type:
        bump_version(bump_version_type)

    # Update git
    print "Updating in git"
    local("git add .")
    local('git commit -m "version bump and prep for publish"')
    local('git push')

    # Build/Publish
    if upload:
        print "Build and publish version to python index..."
        local("python setup.py sdist upload -r local")
    else:
        print "Building package"
        local("python setup.py sdist build")