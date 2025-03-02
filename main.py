import asyncio
import argparse
import time
from urllib.parse import urlparse, parse_qs

from mcp_agent.app import MCPApp
from mcp_agent.agents.agent import Agent
from mcp_agent.workflows.llm.augmented_llm_openai import OpenAIAugmentedLLM
from mcp_agent.workflows.parallel.parallel_llm import ParallelLLM

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
                instruction="""
                You are a PR data fetcher that extracts relevant information from GitHub pull requests and explores the local codebase.
                Given a GitHub PR URL, you will:
                1. Extract all files changed in the PR
                2. Get the diff for each file 
                3. Gather PR metadata (title, description, comments)
                4. Use the file-system tool to explore related files in the codebase that would provide important context
                5. Format this information in a structured way for code review
                
                Your output should be comprehensive and include all necessary code context for a thorough review.
                Use the file-system tool to navigate directories, read files, and understand the broader context of the changes.
                When you see changes to a file, you should use the file-system tool to:
                - Explore other files in the same directory
                - Look for related files that might be impacted by the changes
                - Understand the project structure and dependencies
                - Identify potential issues that might arise from these changes
                """,
                server_names=["github", "file-system"],
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
                pr_llm = await pr_fetcher.attach_llm(OpenAIAugmentedLLM)

                # Use the GitHub MCP server via the LLM to fetch PR data
                pr_fetch_prompt = f"""
                Use the GitHub MCP server to fetch comprehensive data about this pull request:
                
                Owner: {owner}
                Repository: {repo_name}
                PR Number: {pr_number}
                
                Please collect:
                1. PR metadata (title, description, author)
                2. List of files changed
                3. The diff/patch for each file
                4. Any comments on the PR
                
                Then, use the file-system tool to explore the local repository and gather more context:
                1. For each changed file, examine the local copy of the file
                2. Look for related files in the same directories
                3. Check for configuration files, tests, or documentation related to the changes
                4. Explore the project structure to understand dependencies and potentially affected areas
                
                Format the data in a structured way that is suitable for code review.
                Include the complete code context needed for a thorough review, including:
                - The diff from the PR
                - Important related files not included in the PR
                - Project structure context that helps understand the changes
                - Any potential issues or dependencies identified during exploration
                """

                pr_data = await pr_llm.generate_str(pr_fetch_prompt)
                logger.info("Successfully fetched PR data")

                # Create specialized reviewer agents
                security_reviewer = Agent(
                    name="security_reviewer",
                    instruction="""
                    You are a security expert focused on code security. Analyze the provided code changes for:
                    1. Security vulnerabilities (e.g., SQL injection, XSS, CSRF)
                    2. Authentication/authorization issues
                    3. Data validation problems
                    4. Secure coding practices
                    5. Potential secret/credential exposure
                    
                    Use the file-system tool to explore the codebase more thoroughly if needed:
                    - Examine security-related files and configurations
                    - Look at authentication and authorization mechanisms
                    - Check for patterns across the codebase that might reveal systemic issues
                    
                    For each issue found, provide:
                    - Issue description
                    - Location in the code (file, line number)
                    - Severity (Critical, High, Medium, Low)
                    - Recommendation for fixing
                    
                    If no security issues are found, mention the positive security aspects of the code.
                    """,
                    server_names=["github", "file-system"],
                )

                performance_reviewer = Agent(
                    name="performance_reviewer",
                    instruction="""
                    You are a performance optimization expert. Analyze the provided code changes for:
                    1. Performance bottlenecks or inefficient algorithms
                    2. Memory leaks or excessive memory usage
                    3. Unnecessary computations or loops
                    4. Database query optimization opportunities
                    5. Caching opportunities
                    
                    Use the file-system tool to explore the codebase more thoroughly if needed:
                    - Look at similar performance-critical parts of the codebase
                    - Examine configuration files that might affect performance
                    - Check for existing benchmarks or performance tests
                    - Understand how the changed code interacts with other components
                    
                    For each issue found, provide:
                    - Issue description
                    - Location in the code (file, line number)
                    - Performance impact (High, Medium, Low)
                    - Recommendation for optimization
                    
                    If no performance issues are found, mention the positive performance aspects of the code.
                    """,
                    server_names=["github", "file-system"],
                )

                clarity_reviewer = Agent(
                    name="clarity_reviewer",
                    instruction="""
                    You are a code clarity and maintainability expert. Analyze the provided code changes for:
                    1. Code readability and naming conventions
                    2. Documentation quality (comments, docstrings)
                    3. Function/method length and complexity
                    4. Code duplication
                    5. Adherence to project style guidelines
                    
                    Use the file-system tool to explore the codebase more thoroughly if needed:
                    - Check existing style guide files or linter configurations
                    - Look at similar files to understand project conventions
                    - Examine documentation standards across the project
                    - Identify patterns and practices established in the codebase
                    
                    For each issue found, provide:
                    - Issue description
                    - Location in the code (file, line number)
                    - Recommendation for improvement
                    
                    If code is well-written, mention the positive aspects of code clarity and style.
                    """,
                    server_names=["github", "file-system"],
                )

                test_reviewer = Agent(
                    name="test_reviewer",
                    instruction="""
                    You are a testing and quality assurance expert. Analyze the provided code changes for:
                    1. Test coverage of new/modified code
                    2. Edge cases that might not be tested
                    3. Testing best practices and patterns
                    4. Potential for test flakiness
                    5. Mocking strategies and their effectiveness
                    
                    Use the file-system tool to explore the codebase more thoroughly if needed:
                    - Look for test files related to the changed code
                    - Examine test frameworks and utilities used in the project
                    - Check for CI/CD configurations and test requirements
                    - Understand the overall test strategy and patterns
                    
                    For each issue found, provide:
                    - Issue description
                    - Location in the code (file, line number)
                    - Recommendation for testing improvement
                    
                    If test coverage is good, mention the positive aspects of the testing approach.
                    """,
                    server_names=["github", "file-system"],
                )

                # Review aggregator agent
                review_aggregator = Agent(
                    name="review_aggregator",
                    instruction="""
                    You are a senior code reviewer who compiles feedback from multiple specialized reviewers.
                    
                    You will receive reviews from:
                    - Security Reviewer: Focused on security vulnerabilities and best practices
                    - Performance Reviewer: Focused on performance optimizations
                    - Clarity Reviewer: Focused on code readability and maintainability
                    - Test Reviewer: Focused on test coverage and quality
                    
                    Use the file-system tool to explore the codebase if needed to verify or further investigate claims made by other reviewers.
                    You can access the local repository to check code context, examine related files, or verify patterns mentioned in the individual reviews.
                    
                    Your job is to:
                    1. Compile all feedback into a single comprehensive review
                    2. Resolve any conflicts or contradictions between reviews
                    3. Prioritize issues (Critical, High, Medium, Low)
                    4. Provide an executive summary of the most important findings
                    5. Give an overall recommendation (Approve, Request Changes, Comment)
                    
                    Format your review in markdown with clear sections for each aspect.
                    """,
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
                    llm_factory=OpenAIAugmentedLLM,
                )

                # Execute parallel review
                review_result = await parallel.generate_str(
                    message=f"Review the following GitHub pull request data:\n\n{pr_data}",
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
