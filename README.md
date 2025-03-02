# Multi-Code-Reviewer

A specialized tool for reviewing GitHub pull requests from multiple perspectives, built using the `mcp-agent` framework. This tool conducts comprehensive code reviews with specialized agents that focus on different aspects of code quality.

## Features

The Multi-Code-Reviewer analyzes pull requests from four specialized perspectives:

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
python main.py https://github.com/username/repo/pull/123
```

The tool will:
1. Fetch the PR data from GitHub
2. Explore the local repository for additional context
3. Conduct specialized reviews in parallel
4. Generate a comprehensive review report

## Configuration

The tool can be configured using the `mcp_agent.config.yaml` file, which allows you to:

- Select different LLM providers and models
- Adjust the logging level
- Configure the various MCP servers

## Requirements

- Python 3.9+
- OpenAI API key
- GitHub access for PR details
