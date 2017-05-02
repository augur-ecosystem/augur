#!/usr/bin/env bash

if [[ $* == *--bump_patch* ]]
then
    echo "Bumping version..."
    ./bumpversion.sh
fi

echo "Publishing version to python index..."
python setup.py sdist upload -r local