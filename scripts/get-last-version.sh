#!/bin/bash
# Given a version tag, this script will return the previous version tag.
#
# Usage: get-last-version.sh v0.13.1

# Get the version tag from the command line
version=$1

# strip anything with a `-` prefix
version=$(echo $version | sed 's/-.*//')

# Get the previous version tag
git tag --sort=-version:refname | grep -A 1 $version | tail -n 1
