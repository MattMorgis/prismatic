from urllib.parse import urlparse

from mcp_agent.app import MCPApp
from mcp_agent.config import get_settings

# Import prompts from prompts.py

# Initialize the MCPApp
app = MCPApp(name="multi_code_reviewer")


async def get_github_token():
    return get_settings().mcp.servers["github"].env["GITHUB_PERSONAL_ACCESS_TOKEN"]


async def clone_repo_and_apply_patch(pr_url):
    # Get GitHub token and validate it exists
    github_token = await get_github_token()
    if not github_token:
        raise ValueError(
            "GitHub token not found. Please ensure GITHUB_PERSONAL_ACCESS_TOKEN is set in configuration.")
    # Parse the PR URL to extract owner, repo, and PR number
    parsed_url = urlparse(pr_url)
    path_parts = parsed_url.path.strip("/").split("/")

    if len(path_parts) < 4 or path_parts[2] != "pull":
        raise ValueError(f"Invalid GitHub PR URL: {pr_url}")

    owner = path_parts[0]
    repo_name = path_parts[1]
    pr_number = int(path_parts[3])

    return owner, repo_name, pr_number


async def run_multi_code_review(pr_url):
    """Main function to orchestrate the multi-code review process"""
    async with app.run() as multi_code_reviewer:
        logger = multi_code_reviewer.logger
        logger.info(f"Starting multi-code review for PR: {pr_url}")

        try:
            clone_repo_and_apply_patch(pr_url)
            # # Create specialized reviewer agents
            # security_reviewer = Agent(
            #     name="security_reviewer",
            #     instruction=SECURITY_REVIEWER_INSTRUCTION,
            #     server_names=["github", "file"],
            # )

            # performance_reviewer = Agent(
            #     name="performance_reviewer",
            #     instruction=PERFORMANCE_REVIEWER_INSTRUCTION,
            #     server_names=["github", "file"],
            # )

            # clarity_reviewer = Agent(
            #     name="clarity_reviewer",
            #     instruction=CLARITY_REVIEWER_INSTRUCTION,
            #     server_names=["github", "file"],
            # )

            # test_reviewer = Agent(
            #     name="test_reviewer",
            #     instruction=TEST_REVIEWER_INSTRUCTION,
            #     server_names=["github", "file"],
            # )

            # # Review aggregator agent
            # review_aggregator = Agent(
            #     name="review_aggregator",
            #     instruction=REVIEW_AGGREGATOR_INSTRUCTION,
            #     server_names=["github", "file"],
            # )

            # Create parallel workflow
            # parallel = ParallelLLM(
            #     fan_in_agent=review_aggregator,
            #     fan_out_agents=[
            #         security_reviewer,
            #         performance_reviewer,
            #         clarity_reviewer,
            #         test_reviewer,
            #     ],
            #     llm_factory=AnthropicAugmentedLLM,
            # )

            # # Execute parallel review
            # review_result = await parallel.generate_str(
            #     message=f"Review the following GitHub pull request data:\n\n{pr_data}",
            #     # The PR data already contains the PR_CHECKOUT_PATH information that all agents can use
            # )

            # logger.info("Multi-code review completed successfully!")
            # return review_result

        except Exception as e:
            logger.error(f"Error during multi-code review: {str(e)}")
            raise
