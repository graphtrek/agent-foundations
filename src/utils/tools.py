from langchain.tools import tool
from langchain_community.tools import DuckDuckGoSearchResults

duckduckgo_client = DuckDuckGoSearchResults(output_format="string")


@tool
def web_search(query: str) -> str:
    """Search the web for information."""
    return duckduckgo_client.invoke(query)
