GitHub Bot
==========

One way to run gptme is as a GitHub bot.

The `gptme-bot` composite action is a GitHub Action that automates the process of running the `gptme`  in response to comments on GitHub issues or pull requests. It is designed to be used for tasks that gptme can perform with a one-shot prompt, such as running commands and committing their results, creating files or making simple changes/additions (like write tests), and (potentially) automating code reviews.

## Inputs

The action has the following inputs:

- `openai_api_key`: The OpenAI API key. Required.
- `github_token`: The GitHub token. Required.
- `issue_number`: The number of the issue or pull request the comment is associated with. Required.
- `comment_body`: The body of the comment. Required.
- `comment_id`: The ID of the comment. Required.
- `repo_name`: The name of the repository. Required.
- `user_name`: The username of the comment author. Required.
- `branch_base`: The base branch for the pull request. Required.
- `python_version`: The version of Python to use. Required.
- `is_pr`: A boolean indicating whether the issue is a pull request. Required.
- `branch_name`: The name of the branch associated with the pull request. Required.

## Usage

To use the `gptme-bot` composite action in your repo, you need to create a GitHub Actions workflow file that triggers the action in response to comments on issues or pull requests. 

Here is an example workflow file that triggers the action in response to comments on issues:

```yaml
name: gptme-bot

on:
  issue_comment:
    types: [created]

permissions: write-all

jobs:
  run-bot:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v3

      - name: run gptme-bot action
        uses: ./.github/actions/bot
        with:
          openai_api_key: ${{ secrets.OPENAI_API_KEY }}
          github_token: ${{ secrets.GITHUB_TOKEN }}
          issue_number: ${{ github.event.issue.number }}
          comment_body: ${{ github.event.comment.body }}
          comment_id: ${{ github.event.comment.id }}
          repo_name: ${{ github.event.repository.name }}
          user_name: ${{ github.event.repository.owner.login }}
          branch_base: ${{ github.event.repository.default_branch }}
          is_pr: ${{ github.event.issue.pull_request != null }}
          branch_name: ${{ github.event.pull_request.head.ref || format('gptme/bot-changes-{0}', github.run_id) }}
          allowlist: "erikbjare"
```

The `gptme-bot` action will then run the `gptme` command-line tool with the command specified in the comment, and perform actions based on the output of the tool. 

If a question was asked, it will simply reply.

If a request was made it will check out the appropriate branch, install dependencies, run `gptme`, then commit and push any changes made. If the issue is a pull request, the bot will push changes directly to the pull request branch. If the issue is not a pull request, the bot will create a new pull request with the changes. 
