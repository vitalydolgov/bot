# The harness drops images from MCP tool results before they reach the model:
# mcp_http._tool_call_result keeps only text, and the OpenAI provider's
# text_only_tool_result_content replaces image parts with an "[Image]" placeholder.
# The configured endpoint accepts image parts in tool messages, so forward them
# instead; without this, screenshots taken via MCP tools never reach the model.
import mistralai.vibe.harness.runtime.completion.providers.utils as provider_utils
import mistralai.vibe.harness.runtime.hosts.mcp_http as mcp_http
from mcp.types import ImageContent

from mistralai.vibe.harness.core import protocol as core_protocol
from mistralai.vibe.harness.runtime.capabilities.models import McpToolCallFailed, McpToolCallSucceeded


def _tool_call_result_with_images(result):
    payload = result.model_dump(mode="json", by_alias=True, exclude_none=True)
    if payload.get("isError"):
        return McpToolCallFailed(message=mcp_http._error_message(result))
    text = mcp_http._result_text(result, payload.get("structuredContent"))
    content = [core_protocol.TextContentBlock(text=text)]
    for block in result.content:
        if isinstance(block, ImageContent):
            content.append(core_protocol.ImageContentBlock(data=block.data, mime_type=block.mime_type))
    return McpToolCallSucceeded(content=content, structured_content=mcp_http._structured_content_from_text(text))


def _tool_result_content_with_images(content):
    if not isinstance(content, list):
        return content
    return provider_utils.resource_link_text_fallback(content)


def apply_sdk_patches() -> None:
    mcp_http._tool_call_result = _tool_call_result_with_images
    provider_utils.text_only_tool_result_content = _tool_result_content_with_images
