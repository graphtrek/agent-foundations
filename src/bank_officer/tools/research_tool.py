"""The coordinator's research tools for the ``research`` architecture mode:
``web_search`` and ``research_links``, which fans the chosen links out to
page-researcher subagents in parallel and waits for all of them."""

import contextvars
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from langchain.tools import tool

from agents.agent_spec import AgentFactory
from tools.specialist_runner import run_specialist
from tools.tool_groups import TOOL_GROUPS
from tools.web_tools import check_public_url, web_search

RESEARCH_TOOL = "research_links"


def create_research_tools(researcher: AgentFactory, max_links: int) -> list[Any]:
    """``web_search`` plus ``research_links``. The fan-out is done in code, so the
    parallelism and the wait for every subagent do not depend on the model
    issuing several calls in one step."""

    @tool(RESEARCH_TOOL)
    def research_links(question: str, urls: list[str]) -> str:
        """Read the given links in parallel with one subagent per link and return each
        subagent's summary. Pass the user's question and the most relevant URLs
        (at most the allowed number) taken from the web_search results."""
        unique = list(dict.fromkeys(u.strip() for u in urls if u.strip()))
        chosen, dropped = unique[:max_links], unique[max_links:]
        if not chosen:
            return "No links given. Call web_search first and pass the best URLs."

        def research(url: str) -> str:
            if (refusal := check_public_url(url)) is not None:
                return f"Not read: {refusal}."
            agent = researcher.build(TOOL_GROUPS["web"](""))
            return run_specialist(
                agent, f"User question: {question}\n\nPage to read: {url}"
            )

        # A context copy per task so the reply-language ContextVar reaches the
        # worker threads; the with-block returns only when every subagent is done.
        with ThreadPoolExecutor(max_workers=len(chosen)) as pool:
            futures = [
                pool.submit(contextvars.copy_context().run, research, url) for url in chosen
            ]
            summaries = [f.result() for f in futures]
        report = "\n\n".join(
            f"### Source {i}: {url}\n{summary}"
            for i, (url, summary) in enumerate(zip(chosen, summaries), start=1)
        )
        if dropped:
            report += f"\n\n(Only {max_links} links are read; skipped: {', '.join(dropped)})"
        return report

    return [web_search, research_links]
