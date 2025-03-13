#!/bin/bash

# This script fetches the full info for a GitHub PR, including the PR review comments (not served by the `gh pr view` command).

set -e

# Input URL should look like: https://github.com/gptme/gptme/pull/466
URL=$1

OWNER=$(echo $URL | awk -F'/' '{print $(NF-3)}')
REPO=$(echo $URL | awk -F'/' '{print $(NF-2)}')
ISSUE_ID=$(echo $URL | awk -F'/' '{print $NF}')
API_PATH="/repos/$OWNER/$REPO/pulls/$ISSUE_ID/comments"

gh pr view --comments $URL

echo $API_PATH

# TODO: include code snippets + surrounding context referenced by the comments
# TODO: we may also want to read all the paths and include them in context when used by gptme
#       https://github.com/gptme/gptme/issues/468
echo
echo "PR Comments:"
gh api \
      -H "Accept: application/vnd.github+json" \
      -H "X-GitHub-Api-Version: 2022-11-28" \
      $API_PATH \
      --jq '.[] | "@" + .user.login + ": ", .body + "\n"'
