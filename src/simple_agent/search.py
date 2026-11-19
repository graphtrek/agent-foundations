from langchain.tools import tool
from langchain_community.tools import DuckDuckGoSearchResults

duckduckgo_client = DuckDuckGoSearchResults(output_format="string")


def search_web(query: str) -> str:
    """Search the web for information."""
    return duckduckgo_client.invoke(query)


web_search = tool("web_search")(search_web)
