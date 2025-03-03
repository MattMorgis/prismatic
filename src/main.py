from mcp_agent.app import MCPApp
from mcp_agent.config import get_settings

# Import prompts from prompts.py
from src.github import clean_up, clone_pr_repo, get_pr_target_branch

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
            github_token = get_github_token()
            print("Repo path:")
            repo_path = clone_pr_repo(pr_url, github_token)
            branch_name = get_pr_target_branch(pr_url, github_token)
            print(f"Cloned repository at {repo_path} on branch {branch_name}")
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
            logger.error(f"Error during code review: {str(e)}")
            raise
        finally:
            # Clean up the cloned repository if it exists
            if repo_path:
                logger.info(f"Cleaning up repository at {repo_path}")
                clean_up(repo_path)
