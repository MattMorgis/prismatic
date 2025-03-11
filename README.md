# **PR**ismatic: A Code Review Agent

An AI Agent for reviewing GitHub pull requests from multiple perspectives, built using the `mcp-agent` framework.

## Features
**PR**ismatic analyzes pull requests from four specialized perspectives:

1. **Security Reviewer**: Identifies security vulnerabilities and best practices
2. **Performance Reviewer**: Focuses on performance optimizations and bottlenecks
3. **Clarity Reviewer**: Evaluates code readability, naming conventions, and maintainability
4. **QA Reviewer**: Assesses test coverage and testing best practices

Each reviewer provides specialized feedback, which is then aggregated into a comprehensive review report with prioritized recommendations.

## MCP Integration

Each reviewer utilizes the [GitHub](https://github.com/modelcontextprotocol/servers/tree/main/src/github) and [FileSystem](https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem) MCP Servers to access PR metadata, diff information, and other reviewers' comments. This integration allows for a comprehensive analysis by exploring the local repository to provide deeper context for the changes.

## Setup

1. Install [uv](https://github.com/astral-sh/uv) if you haven't already

2. Create a `mcp_agent.secrets.yaml` file (using the .example file as a template) with your API keys.

## Prerequisites

- Docker
- `mcp_agent.secrets.yaml` file in the project root directory

## Usage

### Build the Docker image

```bash
docker build -t prismatic .
```

Note: The build will fail if `mcp_agent.secrets.yaml` is missing.

### Run the code review

```bash
docker run prismatic <pr_url>
```

For example:
```bash
docker run prismatic https://github.com/owner/repo/pull/123
```

This will:
1. Process the specified PR
2. Generate a review report
3. Print the report to console & save within the container.

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
