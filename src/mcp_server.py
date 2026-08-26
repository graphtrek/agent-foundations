import requests
from mcp.server.fastmcp import FastMCP

from utils.tools import search_web

mcp = FastMCP(name="LangChain Agent Server", host="0.0.0.0", port=8000)

mcp.tool()(search_web)


@mcp.prompt()
def search_prompt() -> str:
    """Return the system prompt for the search assistant."""
    return """
    You are a helpful assistant that answers user questions about LangChain,
    LangGraph and LangSmith.

    You can use the following tools/resources to answer user questions:
    - search_web: Search the web for information
    - github_file: Access the langchain-ai repo files

    If the user asks a question that is not related to LangChain, LangGraph or
    LangSmith, you should say "I'm sorry, I can only answer questions about
    LangChain, LangGraph and LangSmith."

    You may try multiple tool and resource calls to answer the user's question.

    You may also ask clarifying questions to better understand the user's
    question.
    """


@mcp.resource("github://langchain-ai/langchain-mcp-adapters/main/README.md")
def resource() -> str:
    """Fetch the README from the langchain-mcp-adapters GitHub repository."""

    url = (
        "https://raw.githubusercontent.com/langchain-ai/"
        "langchain-mcp-adapters/main/README.md"
    )
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.exceptions.RequestException as error:
        return f"Error fetching resource: {error}"
    return response.text


if __name__ == "__main__":
    print(f"MCP Server is running at http://{mcp.settings.host}:{mcp.settings.port}")
    mcp.run(transport="stdio")
