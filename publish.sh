#!/usr/bin/env bash

if [[ $* == *--bump_patch* ]]
then
    echo "Bumping version..."
    ./bumpversion.sh
fi

# Make sure the readmes are the same
echo "Copying README.md to README"
cp README.md README

# Update git
echo "Updating in git"
git add .
git commit -m "version bump and prep for publish"
git push

echo "Publishing version to python index..."
python setup.py sdist upload -r local