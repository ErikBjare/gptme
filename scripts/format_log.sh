#!/usr/bin/env bash
# Usage: ./format_log.sh <~/.local/share/gptme/logs/*/conversation.jsonl>
while IFS= read -r line; do
    role="
$(echo "$line" | jq -r '.role'):"
    # Pad the role to a length of 12 with spaces
    role=$(printf "%-12s" "$role")
    content=$(echo "$line" | jq -r '.content')
    echo "$content" | while IFS= read -r line_content; do
        if [[ -z "$line_content" ]]; then
            echo "     "
        else
            echo "$role $line_content"
            role="            "
        fi
    done
done < $1
