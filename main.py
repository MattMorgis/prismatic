import argparse
import asyncio
import time
from urllib.parse import urlparse

from mcp_agent.agents.agent import Agent
from mcp_agent.app import MCPApp
from mcp_agent.workflows.llm.augmented_llm_anthropic import AnthropicAugmentedLLM
from mcp_agent.workflows.parallel.parallel_llm import ParallelLLM

# Import prompts from prompts.py
from prompts import (
    CLARITY_REVIEWER_INSTRUCTION,
    PERFORMANCE_REVIEWER_INSTRUCTION,
    PR_FETCHER_INSTRUCTION,
    REVIEW_AGGREGATOR_INSTRUCTION,
    SECURITY_REVIEWER_INSTRUCTION,
    TEST_REVIEWER_INSTRUCTION,
    get_pr_fetch_prompt,
)

# Initialize the MCPApp
app = MCPApp(name="multi_code_reviewer")


async def run_multi_code_review(pr_url):
    """Main function to orchestrate the multi-code review process"""
    async with app.run() as multi_code_reviewer:
        logger = multi_code_reviewer.logger
        logger.info(f"Starting multi-code review for PR: {pr_url}")

        try:
            # Create PR fetcher agent that uses the GitHub MCP server
            pr_fetcher = Agent(
                name="pr_fetcher",
                instruction=PR_FETCHER_INSTRUCTION,
                server_names=["github", "file", "git"],
            )

            # Parse the PR URL to extract owner, repo, and PR number
            parsed_url = urlparse(pr_url)
            path_parts = parsed_url.path.strip("/").split("/")

            if len(path_parts) < 4 or path_parts[2] != "pull":
                raise ValueError(f"Invalid GitHub PR URL: {pr_url}")

            owner = path_parts[0]
            repo_name = path_parts[1]
            pr_number = int(path_parts[3])

            async with pr_fetcher:
                # Attach LLM to the PR fetcher agent
                pr_llm = await pr_fetcher.attach_llm(AnthropicAugmentedLLM)

                # Use the GitHub MCP server via the LLM to fetch PR data
                pr_fetch_prompt = get_pr_fetch_prompt(
                    owner, repo_name, pr_number)

                pr_data = await pr_llm.generate_str(pr_fetch_prompt)
                logger.info("Successfully fetched PR data")

                # Create specialized reviewer agents
                security_reviewer = Agent(
                    name="security_reviewer",
                    instruction=SECURITY_REVIEWER_INSTRUCTION,
                    server_names=["github", "file-system"],
                )

                performance_reviewer = Agent(
                    name="performance_reviewer",
                    instruction=PERFORMANCE_REVIEWER_INSTRUCTION,
                    server_names=["github", "file-system"],
                )

                clarity_reviewer = Agent(
                    name="clarity_reviewer",
                    instruction=CLARITY_REVIEWER_INSTRUCTION,
                    server_names=["github", "file-system"],
                )

                test_reviewer = Agent(
                    name="test_reviewer",
                    instruction=TEST_REVIEWER_INSTRUCTION,
                    server_names=["github", "file-system"],
                )

                # Review aggregator agent
                review_aggregator = Agent(
                    name="review_aggregator",
                    instruction=REVIEW_AGGREGATOR_INSTRUCTION,
                    server_names=["github", "file-system"],
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
                    llm_factory=AnthropicAugmentedLLM,
                )

                # Execute parallel review
                review_result = await parallel.generate_str(
                    message=f"Review the following GitHub pull request data:\n\n{pr_data}",
                    # The PR data already contains the PR_CHECKOUT_PATH information that all agents can use
                )

                logger.info("Multi-code review completed successfully!")
                return review_result

        except Exception as e:
            logger.error(f"Error during multi-code review: {str(e)}")
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Multi-perspective code reviewer for GitHub PRs"
    )
    parser.add_argument("pr_url", help="GitHub Pull Request URL to review")
    args = parser.parse_args()

    start_time = time.time()
    review_result = asyncio.run(run_multi_code_review(args.pr_url))
    end_time = time.time()

    print("\n" + "=" * 80)
    print("MULTI-CODE REVIEWER REPORT")
    print("=" * 80 + "\n")
    print(review_result)
    print(f"\nReview completed in {end_time - start_time:.2f} seconds")
