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

To use the `gptme-bot` composite action in your workflow, include it as a step:

```yaml
on:
  issue_comment:
    types: [created]

steps:
  - name: Run gptme-bot composite action
    uses: ./.github/actions/bot-composite
    with:
      openai_api_key: ${{ secrets.OPENAI_API_KEY }}
      github_token: ${{ github.token }}
      issue_number: ${{ github.event.issue.number }}
      comment_body: ${{ github.event.comment.body }}
      comment_id: ${{ github.event.comment.id }}
      repo_name: ${{ github.event.repository.name }}
      user_name: ${{ github.event.repository.owner.login }}
      branch_base: "master"
      python_version: '3.11'
      is_pr: ${{ github.event.issue.pull_request != null }}
      branch_name: ${{ github.event.pull_request.head.ref }}
```

Please note that you need to replace the `uses` path with the correct path to your `bot-composite.yml` file. Also, make sure to replace the `branch_base`, `python_version`, `is_pr`, and `branch_name` inputs with the correct values for your use case.

The `gptme-bot` composite action will then run the `gptme` command-line tool with the command specified in the comment, and perform actions based on the output of the tool. This includes checking out the appropriate branch, installing dependencies, running the `gptme` command, and committing and pushing any changes made by the tool. If the issue is a pull request, the action will push changes directly to the pull request branch. If the issue is not a pull request, the action will create a new pull request with the changes. 

