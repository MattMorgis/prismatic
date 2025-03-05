# **PR**ismatic: A Code Review Agent

An AI Agent for reviewing GitHub pull requests from multiple perspectives, built using the `mcp-agent` framework.

## Features
**PR**ismatic analyzes pull requests from four specialized perspectives:

1. **Security Reviewer**: Identifies security vulnerabilities and best practices
2. **Performance Reviewer**: Focuses on performance optimizations and bottlenecks
3. **Clarity Reviewer**: Evaluates code readability, naming conventions, and maintainability
4. **QA Reviewer**: Assesses test coverage and testing best practices

Each reviewer provides specialized feedback, which is then aggregated into a comprehensive review report with prioritized recommendations.

## Enhanced Capabilities

- **GitHub PR Integration**: Fetches PR metadata, diff information, and comments
- **File System Access**: Explores the local repository to provide deeper context for the changes
- **Parallel Review**: Reviews happen in parallel to speed up the process
- **Report Aggregation**: Combines specialized reviews into a cohesive, actionable report
- **Contextual Understanding**: Examines related files and project structure to provide more relevant feedback

## Setup

1. Install the required dependencies:

```bash
pip install -r requirements.txt
```

2. Create a `mcp_agent.secrets.yaml` file (using the .example file as a template) with your API keys.

## Usage

To review a GitHub pull request:

```bash
python prismatic.py https://github.com/username/repo/pull/123
```

## Configuration

### GitHub Access Token
You need a [GitHub Personal Access Token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)
* Go to [Personal access tokens](https://github.com/settings/personal-access-tokens) (in GitHub Settings > Developer settings)
* Select which repositories you'd like this token to have access to (Public, All, or Select)
* Copy the generated token

### Anthropic API Key
You need an Anthropic API Key
* Go to [Anthropic API Console](https://console.anthropic.com/settings/keys)
* Copy your API key

## Requirements

- Python 3.11+
- Anthropic API key
- GitHub access for PR details
