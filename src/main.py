from mcp_agent.app import MCPApp
from mcp_agent.config import get_settings

# Import GitHubClient from github.py
from src.github import GitHubClient

# Initialize the MCPApp
app = MCPApp(name="multi_code_reviewer")


def get_github_token():
    return get_settings().mcp.servers["github"].env["GITHUB_PERSONAL_ACCESS_TOKEN"]


async def run_multi_code_review(pr_url):
    """Main function to orchestrate the multi-code review process"""
    async with app.run() as multi_code_reviewer:
        logger = multi_code_reviewer.logger
        logger.info(f"Starting multi-code review for PR: {pr_url}")

        repo_path = None
        try:
            github_client = GitHubClient(
                github_token=get_github_token(), custom_logger=logger)

            repo_path = github_client.clone_pr_repo(pr_url)
            target_branch = github_client.get_pr_target_branch(pr_url)

            # Check if repository validation should be performed
            patch_file = github_client.get_and_apply_pr_patch(
                pr_url, repo_path)
            logger.info("Review details:")
            logger.info(f"Repository path: {repo_path}")
            logger.info(f"Patch file: {patch_file}")
            logger.info(f"Target branch: {target_branch}")

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

            # # Create parallel workflow
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
            logger.error(f"Error during code review: {str(e)}")
            raise
        finally:
            # Clean up the cloned repository if it exists
            if repo_path and github_client:
                logger.info(f"Cleaning up repository at {repo_path}")
                github_client.clean_up(repo_path)
