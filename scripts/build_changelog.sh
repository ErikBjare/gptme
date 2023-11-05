#!/bin/bash
set -e

if [[ -z "$1" ]]; then
    echo "Usage: $0 <range>"
    echo "Example: $0 v0.1.0..v0.2.0"
    exit 1
fi

SCRIPTDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# fetch the script if not available locally (symlinked on my system atm)
if [[ ! -f "$SCRIPTDIR/build_changelog.py" ]]; then
    curl -o "$SCRIPTDIR/build_changelog.py" https://raw.githubusercontent.com/ActivityWatch/activitywatch/master/scripts/build_changelog.py
fi

# run
$SCRIPTDIR/build_changelog.py --range $1 --org ErikBjare --repo gptme --project-title GPTMe
