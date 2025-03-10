from typing import List

from mcp_agent.agents.agent import Agent
from mcp_agent.app import MCPApp
from mcp_agent.config import get_settings
from mcp_agent.workflows.llm.augmented_llm_anthropic import RequestParams
from mcp_agent.workflows.parallel.parallel_llm import ParallelLLM

from src.custom.llm import CustomAnthropicAugmentedLLM
from src.github import GitHubClient
from src.prompts import (
    CLARITY_REVIEWER_INSTRUCTION,
    PERFORMANCE_REVIEWER_INSTRUCTION,
    PR_SUMMARIZER_INSTRUCTION,
    REVIEW_AGGREGATOR_INSTRUCTION,
    SECURITY_REVIEWER_INSTRUCTION,
    TEST_REVIEWER_INSTRUCTION,
    get_pr_summarizer_prompt,
)

# Initialize the MCPApp
app = MCPApp(name="prismatic")


def get_github_token():
    return get_settings().mcp.servers["github"].env["GITHUB_PERSONAL_ACCESS_TOKEN"]


def fetch_repo(pr_url, github_client):
    repo_path = github_client.clone_pr_repo(pr_url)

    # Check if repository validation should be performed
    patch_file = github_client.get_and_apply_pr_patch(pr_url, repo_path)

    return repo_path, patch_file


async def run_code_review(pr_url):
    """Main function to orchestrate the multi-code review process"""
    async with app.run() as prismatic:
        logger = prismatic.logger
        logger.info(f"Starting multi-code review for PR: {pr_url}")

        # Initialize variables that might be used in finally block
        repo_path = None
        github_client = None

        try:
            github_client = GitHubClient(github_token=get_github_token(), logger=logger)

            pr_is_open = github_client.is_pr_open(pr_url=pr_url)
            if not pr_is_open:
                logger.info(f"PR {pr_url} is not open, skipping review")
                return ""

            repo_path, patch_file = fetch_repo(pr_url, github_client)
            logger.info(f"Repository path: {repo_path}")
            logger.info(f"Patch file: {patch_file}")

            # Create PR summarizer agent that uses the GitHub MCP server
            pr_summarizer = Agent(
                name="pr_summarizer",
                instruction=PR_SUMMARIZER_INSTRUCTION,
                server_names=["github", "file"],
            )

            async with pr_summarizer:
                # Attach LLM to the PR fetcher agent
                pr_llm = await pr_summarizer.attach_llm(CustomAnthropicAugmentedLLM)

                pr_summarizer_prompt = get_pr_summarizer_prompt(
                    pr_url=pr_url,
                    repo_path=repo_path,
                    diff_file=patch_file,
                )

                responses = await pr_llm.generate(
                    pr_summarizer_prompt,
                    request_params=RequestParams(max_tokens=4000, max_iterations=40),
                )

                # Extract the text content from the responses
                full_response = parse_llm_full_response(responses)
                pr_data = parse_llm_final_response(responses)
                logger.info(f"Successfully summarized PR: {full_response}")
                summary_cost = calculate_token_usage(responses, logger)

                # Create specialized reviewer agents
                security_reviewer = Agent(
                    name="security_reviewer",
                    instruction=SECURITY_REVIEWER_INSTRUCTION,
                    server_names=["github", "file"],
                )

                performance_reviewer = Agent(
                    name="performance_reviewer",
                    instruction=PERFORMANCE_REVIEWER_INSTRUCTION,
                    server_names=["github", "file"],
                )

                clarity_reviewer = Agent(
                    name="clarity_reviewer",
                    instruction=CLARITY_REVIEWER_INSTRUCTION,
                    server_names=["github", "file"],
                )

                test_reviewer = Agent(
                    name="test_reviewer",
                    instruction=TEST_REVIEWER_INSTRUCTION,
                    server_names=["github", "file"],
                )

                # Review aggregator agent
                review_aggregator = Agent(
                    name="review_aggregator",
                    instruction=REVIEW_AGGREGATOR_INSTRUCTION,
                    server_names=["github", "file"],
                )

                # Create parallel workflow
                parallel = ParallelLLM(
                    fan_in_agent=review_aggregator,
                    fan_out_agents=[
                        security_reviewer,
                        performance_reviewer,
                        clarity_reviewer,
                        test_reviewer,
                    ],
                    llm_factory=CustomAnthropicAugmentedLLM,
                )

                # Execute parallel review
                review_result = await parallel.generate_str(
                    message=f"Review the following GitHub pull request:\n\nPR URL: {pr_url}\nRepository Path: {repo_path}\nPatch File: {patch_file}\n\nPR Summary: {pr_data}",
                    request_params=RequestParams(max_tokens=4000, max_iterations=40),
                )

                logger.info("PRismatic review completed successfully!")
                return review_result

        except Exception as e:
            logger.error(f"Error during code review: {str(e)}")
            raise
        finally:
            # Clean up the cloned repository if it exists
            if repo_path and github_client:
                logger.info(f"Cleaning up repository at {repo_path}")
                github_client.clean_up(repo_path)


def parse_llm_full_response(responses):
    final_text: List[str] = []

    for response in responses:
        for content in response.content:
            if content.type == "text":
                final_text.append(content.text)
            elif content.type == "tool_use":
                final_text.append(
                    f"[Calling tool {content.name} with args {content.input}]"
                )

    return "\n".join(final_text)


def parse_llm_final_response(responses):
    final_text = ""

    if responses:
        # Only process the last response
        last_response = responses[-1]
        for content in last_response.content:
            if content.type == "text":
                final_text = content.text

    return final_text


def calculate_token_usage(responses, logger):
    total_input_tokens = 0
    total_output_tokens = 0
    total_cache_creation_tokens = 0
    total_cache_read_tokens = 0

    for response in responses:
        # Extract token usage information if available
        if hasattr(response, "usage"):
            usage = response.usage
            input_tokens = usage.input_tokens if hasattr(usage, "input_tokens") else 0
            output_tokens = (
                usage.output_tokens if hasattr(usage, "output_tokens") else 0
            )

            # Extract cache-related token information
            cache_creation_tokens = (
                usage.cache_creation_input_tokens
                if hasattr(usage, "cache_creation_input_tokens")
                else 0
            )
            cache_read_tokens = (
                usage.cache_read_input_tokens
                if hasattr(usage, "cache_read_input_tokens")
                else 0
            )

            total_input_tokens += input_tokens
            total_output_tokens += output_tokens
            total_cache_creation_tokens += cache_creation_tokens
            total_cache_read_tokens += cache_read_tokens

            # Log token usage including cache metrics
            logger.info(
                f"Token usage - Input: {input_tokens}, Output: {output_tokens}, "
                f"Cache Creation: {cache_creation_tokens}, Cache Read: {cache_read_tokens}"
            )

    # Log total token usage including cache metrics
    logger.info(
        f"Total token usage - Input: {total_input_tokens}, Output: {total_output_tokens}, "
        f"Cache Creation: {total_cache_creation_tokens}, Cache Read: {total_cache_read_tokens}"
    )

    # Calculate approximate cost with updated pricing and cache metrics
    # Prices: $3 per million input tokens, $15 per million output tokens
    # Cache pricing: $3.75 per million cache write tokens, $0.30 per million cache read tokens
    input_cost = (total_input_tokens / 1_000_000) * 3.0
    output_cost = (total_output_tokens / 1_000_000) * 15.0
    cache_creation_cost = (total_cache_creation_tokens / 1_000_000) * 3.75
    cache_read_cost = (total_cache_read_tokens / 1_000_000) * 0.30

    total_cost = input_cost + output_cost + cache_creation_cost + cache_read_cost

    logger.info(
        f"Estimated cost: ${total_cost:.6f} ("
        f"Input: ${input_cost:.6f}, "
        f"Output: ${output_cost:.6f}, "
        f"Cache Creation: ${cache_creation_cost:.6f}, "
        f"Cache Read: ${cache_read_cost:.6f})"
    )

    return total_cost
