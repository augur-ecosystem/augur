#!/usr/bin/env bash

echo "Bumping version..."
./bumpversion.sh

echo "Publishing version to python index..."
python setup.py sdist upload -r local