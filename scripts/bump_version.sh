#!/bin/bash

set -e

git diff --cached --exit-code || (echo "There are staged files, please commit or unstage them" && exit 1)
git diff --exit-code pyproject.toml || (echo "pyproject.toml is dirty, please commit or stash changes" && exit 1)

git pull

VERSION_TAG=$(git describe --tags --abbrev=0 | cut -b 2-)
VERSION_PYPROJECT=$(poetry version --short)

IS_COMMIT_TAGGED=$(git tag --points-at HEAD | grep -q "^v[0-9]\+\.[0-9]\+\.[0-9]\+$" && echo "true" || echo "false")

# if we're already on a tagged commit, and the versions match, exit with 0
if [ "${VERSION_TAG}" == "${VERSION_PYPROJECT}" ] && [ "${IS_COMMIT_TAGGED}" == "true" ]; then
  echo "Version ${VERSION_TAG} is already tagged, assuming up-to-date"
  exit 0
# if the version in pyproject.toml is not the same as the latest tag, we need to bump the version
elif [ "${VERSION_TAG}" != "${VERSION_PYPROJECT}" ]; then
  echo "The latest tag is ${VERSION_TAG} but the version in pyproject.toml is ${VERSION_PYPROJECT}"
  echo "Updating the version in pyproject.toml to match the latest tag"
  poetry version ${VERSION}
  git add pyproject.toml
  git commit -m "chore: bump version to ${VERSION}" || echo "No version bump needed"
else
  # if the versions match, ask for version number to bump to
  read -p "Enter new version number: " VERSION_NEW
  # strip leading 'v' if present
  VERSION_NEW=$(echo ${VERSION_NEW} | sed 's/^v//')
  # if version is existing version, exit with 0
  if [ "${VERSION_NEW}" == "${VERSION_TAG}" ]; then
    echo "Version ${VERSION_NEW} already exists, assuming up-to-date"
    exit 0
  fi
  echo "Bumping version to ${VERSION_NEW}"
  poetry version ${VERSION_NEW}
  git add pyproject.toml
  git commit -m "chore: bump version to ${VERSION_NEW}"
  git tag -s v${VERSION_NEW} -m "v${VERSION_NEW}"
fi
