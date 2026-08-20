from langchain.tools import tool
from langchain_community.tools import DuckDuckGoSearchResults

duckduckgoClient = DuckDuckGoSearchResults(output_format="string")

@tool
def web_search(query: str):
  """Search the web for information"""
  return duckduckgoClient.invoke(query)

#print(web_search.invoke("latest AI news"))