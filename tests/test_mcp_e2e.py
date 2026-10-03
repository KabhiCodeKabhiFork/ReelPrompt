"""Spawns the real MCP server over stdio and calls its tools through an MCP client."""
import sys

import anyio
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def _params(tmp_path, provider="mock", **extra):
    import os
    env = {"REELPROMPT_HOME": str(tmp_path), "REELPROMPT_PROVIDER": provider, "PATH": os.environ["PATH"], "REELPROMPT_NO_DOTENV": "1", **extra}
    return StdioServerParameters(command=sys.executable, args=["-m", "reelprompt.mcp_server"], env=env)


def _run(coro):
    return anyio.run(coro)


def test_lists_tools(tmp_path):
    async def go():
        async with stdio_client(_params(tmp_path)) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                return {t.name for t in (await s.list_tools()).tools}
    assert _run(go) == {"get_video_context", "analyze_video"}


def test_get_video_context_returns_text_and_images(sample_video, tmp_path):
    async def go():
        async with stdio_client(_params(tmp_path)) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                return await s.call_tool("get_video_context", {"source": str(sample_video), "frames": 4})
    res = _run(go)
    assert not res.is_error
    kinds = [c.type for c in res.content]
    assert kinds[0] == "text" and "image" in kinds
    assert "pack_folder" in res.content[0].text


def test_analyze_video_returns_prompt(sample_video, tmp_path):
    async def go():
        async with stdio_client(_params(tmp_path)) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                return await s.call_tool("analyze_video", {"source": str(sample_video), "frames": 3})
    res = _run(go)
    assert not res.is_error
    assert res.content[0].text.startswith("# Mock analysis")
    assert any(c.type == "image" for c in res.content)


def test_bad_source_is_a_tool_error(tmp_path):
    async def go():
        async with stdio_client(_params(tmp_path)) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                return await s.call_tool("get_video_context", {"source": "/nonexistent/video.mp4"})
    res = _run(go)
    assert res.is_error


def test_without_api_key_only_context_tool_is_offered(tmp_path):
    async def go():
        async with stdio_client(_params(tmp_path, provider="openai")) as (r, w):  # no OPENAI_API_KEY in env
            async with ClientSession(r, w) as s:
                await s.initialize()
                return {t.name for t in (await s.list_tools()).tools}
    assert _run(go) == {"get_video_context"}


def test_with_api_key_both_tools_are_offered(tmp_path):
    async def go():
        async with stdio_client(_params(tmp_path, provider="openai", OPENAI_API_KEY="sk-test")) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                return {t.name for t in (await s.list_tools()).tools}
    assert _run(go) == {"get_video_context", "analyze_video"}
