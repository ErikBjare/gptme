#gh issue view $ISSUE_NUMBER > issue.md
#gh issue view $ISSUE_NUMBER -c > comments.md

# strip long <details>...</details> from issue.md and comments.md
perl -0777 -i -pe 's/\n<details>.*?<\/details>//sg' issue.md
perl -0777 -i -pe 's/\n<details>.*?<\/details>//sg' comments.md
