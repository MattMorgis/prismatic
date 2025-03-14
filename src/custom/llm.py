# This is file is based on augmented_llm_anthropic.py from mcp-agent
# https://github.com/lastmile-ai/mcp-agent
#
# Licensed under the Apache License, Version 2.0
#
# (c) 2025 lastmile ai
#
# NOTICE: This file has been modified from the original version.
#
# For the full license information, please view the LICENSE
# file that was distributed with the original source code.

import asyncio
import functools
import logging
from typing import List

from anthropic import Anthropic
from anthropic._exceptions import (
    OverloadedError,
    RateLimitError,
    ServiceUnavailableError,
)
from anthropic.types import Message, MessageParam, ToolParam, ToolResultBlockParam
from mcp_agent.workflows.llm.augmented_llm_anthropic import (
    AnthropicAugmentedLLM as BaseAnthropicAugmentedLLM,
)
from mcp_agent.workflows.llm.augmented_llm_anthropic import RequestParams
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from mcp.types import CallToolRequest, CallToolRequestParams


def wrap_anthropic_api_with_retry_and_backoff(func):
    """Decorator to add retry and backoff for Anthropic API rate limit errors.
    This decorator wraps API calls to Anthropic's services with an exponential
    backoff retry mechanism specifically for rate limit errors (HTTP 429).

    Features:
    - Retries up to 5 times with exponential backoff
    - Only retries for rate limit errors (HTTP 429)
    - Logs each retry attempt with details
    Args:
        func: The function to wrap (can be sync or async)
    Returns:
        A wrapped function that will retry on rate limit errors
    """
    # Get or create a logger
    logger = logging.getLogger(__name__)

    # Configure the retry behavior specifically for rate limit errors
    # - retry up to 5 times
    # - wait exponentially: ~30s, ~60s, ~120s, ~180s, ~180s (plus jitter)
    # - only retry for rate limit errors
    retry_config = dict(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=15, min=30, max=180),
        retry=retry_if_exception_type(
            exception_types=tuple(
                [RateLimitError, ServiceUnavailableError, OverloadedError]
            )
        ),
        before_sleep=lambda retry_state: logger.warning(
            f"Rate limit hit: {retry_state.outcome.exception()}. "
            f"Retrying in {retry_state.next_action.sleep:.2f} seconds "
            f"(attempt {retry_state.attempt_number}/5)"
        ),
    )

    # Check if the function is a coroutine function (async)
    if asyncio.iscoroutinefunction(func):
        # For async functions, we need to use the async retry decorator
        from tenacity import AsyncRetrying

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            async for attempt in AsyncRetrying(**retry_config):
                with attempt:
                    return await func(*args, **kwargs)

        return async_wrapper
    else:
        # For regular functions, use the standard retry decorator
        return retry(**retry_config)(func)


class CustomAnthropicAugmentedLLM(BaseAnthropicAugmentedLLM):
    """
    Custom implementation of AnthropicAugmentedLLM that incorporates changes
    from pending pull requests.

    This class will be removed once the PRs are merged into the main framework.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Any initialization changes from your PRs go here

    async def generate(self, message, request_params: RequestParams | None = None):
        """
        Process a query using an LLM and available tools.
        The default implementation uses Claude as the LLM.
        Override this method to use a different LLM.
        """
        config = self.context.config
        anthropic = Anthropic(api_key=config.anthropic.api_key)
        messages: List[MessageParam] = []
        params = self.get_request_params(request_params)

        if params.use_history:
            messages.extend(self.history.get())

        if isinstance(message, str):
            messages.append({"role": "user", "content": message})
        elif isinstance(message, list):
            messages.extend(message)
        else:
            messages.append(message)

        response = await self.aggregator.list_tools()
        available_tools: List[ToolParam] = [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema,
            }
            for tool in response.tools
        ]

        responses: List[Message] = []
        model = await self.select_model(params)

        for i in range(params.max_iterations):
            # Add cache_control to tools
            tools_with_cache = self._apply_cache_to_tools(available_tools)

            # Add cache_control to system prompt
            system_content = self.instruction or params.systemPrompt
            system_with_cache = self._apply_cache_to_system_prompt(system_content)

            # Add cache_control to final message
            messages_with_cache = self._apply_cache_to_messages(messages)

            arguments = {
                "model": model,
                "max_tokens": params.maxTokens,
                "messages": messages_with_cache,
                "system": system_with_cache if system_with_cache else system_content,
                "stop_sequences": params.stopSequences,
                "tools": tools_with_cache,
            }

            if params.metadata:
                arguments = {**arguments, **params.metadata}

            self.logger.debug(f"{arguments}")
            self._log_chat_progress(chat_turn=(len(messages) + 1) // 2, model=model)

            api_call_with_retry = wrap_anthropic_api_with_retry_and_backoff(
                anthropic.messages.create
            )

            executor_result = await self.executor.execute(
                api_call_with_retry, **arguments
            )

            response = executor_result[0]

            if isinstance(response, BaseException):
                self.logger.error(f"Error: {executor_result}")
                break

            self.logger.debug(
                f"{model} response:",
                data=response,
            )

            response_as_message = self.convert_message_to_message_param(response)
            messages.append(response_as_message)
            responses.append(response)

            if response.stop_reason == "end_turn":
                self.logger.debug(
                    f"Iteration {i}: Stopping because finish_reason is 'end_turn'"
                )
                break
            elif response.stop_reason == "stop_sequence":
                # We have reached a stop sequence
                self.logger.debug(
                    f"Iteration {i}: Stopping because finish_reason is 'stop_sequence'"
                )
                break
            elif response.stop_reason == "max_tokens":
                # We have reached the max tokens limit
                self.logger.debug(
                    f"Iteration {i}: Stopping because finish_reason is 'max_tokens'"
                )
                # TODO: saqadri - would be useful to return the reason for stopping to the caller
                break
            else:  # response.stop_reason == "tool_use":
                for content in response.content:
                    if content.type == "tool_use":
                        tool_name = content.name
                        tool_args = content.input
                        tool_use_id = content.id

                        # TODO -- productionize this
                        # if tool_name == HUMAN_INPUT_TOOL_NAME:
                        #     # Get the message from the content list
                        #     message_text = ""
                        #     for block in response_as_message["content"]:
                        #         if (
                        #             isinstance(block, dict)
                        #             and block.get("type") == "text"
                        #         ):
                        #             message_text += block.get("text", "")
                        #         elif hasattr(block, "type") and block.type == "text":
                        #             message_text += block.text

                        # panel = Panel(
                        #     message_text,
                        #     title="MESSAGE",
                        #     style="green",
                        #     border_style="bold white",
                        #     padding=(1, 2),
                        # )
                        # console.console.print(panel)

                        tool_call_request = CallToolRequest(
                            method="tools/call",
                            params=CallToolRequestParams(
                                name=tool_name, arguments=tool_args
                            ),
                        )

                        result = await self.call_tool(
                            request=tool_call_request, tool_call_id=tool_use_id
                        )

                        messages.append(
                            MessageParam(
                                role="user",
                                content=[
                                    ToolResultBlockParam(
                                        type="tool_result",
                                        tool_use_id=tool_use_id,
                                        content=result.content,
                                        is_error=result.isError,
                                    )
                                ],
                            )
                        )

        if params.use_history:
            self.history.set(messages)

        self._log_chat_finished(model=model)

        return responses

    def _apply_cache_to_tools(self, tools):
        """
        Apply cache control to tools.
        Marks the last tool with ephemeral cache control.
        Args:
            tools: List of tools to apply cache control to
        Returns:
            List of tools with cache control applied
        """
        if tools and len(tools) > 0:
            # Apply cache control directly to the last tool
            tools[-1]["cache_control"] = {"type": "ephemeral"}

        return tools

    def _apply_cache_to_system_prompt(self, system_content):
        """
        Apply cache control to system prompt.
        Marks the last block with ephemeral cache control.
        Args:
            system_content: System prompt content (string or list)
        Returns:
            System prompt with cache control applied
        """
        if not system_content:
            return None

        system_with_cache = None
        if isinstance(system_content, str):
            system_with_cache = [
                {
                    "type": "text",
                    "text": system_content,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        elif isinstance(system_content, list):
            system_with_cache = []
            for idx, block in enumerate(system_content):
                block_copy = (
                    block.copy()
                    if isinstance(block, dict)
                    else {"type": "text", "text": block}
                )
                # Add cache control to the last block
                if idx == len(system_content) - 1:
                    block_copy["cache_control"] = {"type": "ephemeral"}
                system_with_cache.append(block_copy)

        return system_with_cache

    def _apply_cache_to_messages(self, messages):
        """
        Apply cache control to messages.
        Marks the last message with ephemeral cache control.
        Args:
            messages: List of messages to apply cache control to
        Returns:
            List of messages with cache control applied
        """
        if not messages:
            return []

        messages_with_cache = []

        for idx, msg in enumerate(messages):
            # Only copy the message if it's the last one that needs modification
            if idx == len(messages) - 1:
                msg_copy = msg.copy()

                self.logger.debug(
                    f"Adding cache breakpoint at message {idx + 1} of {len(messages)}"
                )

                if isinstance(msg_copy.get("content"), str):
                    msg_copy["content"] = [
                        {
                            "type": "text",
                            "text": msg_copy["content"],
                            "cache_control": {"type": "ephemeral"},
                        }
                    ]
                elif isinstance(msg_copy.get("content"), list):
                    content_list = []
                    for c_idx, content in enumerate(msg_copy["content"]):
                        if isinstance(content, dict):
                            if c_idx == len(msg_copy["content"]) - 1:
                                content_copy = content.copy()
                                content_copy["cache_control"] = {"type": "ephemeral"}
                                content_list.append(content_copy)
                            else:
                                content_list.append(content)
                        else:
                            content_list.append(content)
                    msg_copy["content"] = content_list

                messages_with_cache.append(msg_copy)
            else:
                # For non-last messages, use them directly without copying
                messages_with_cache.append(msg)

        return messages_with_cache
