from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv
import httpx
from bs4 import BeautifulSoup
import asyncio


# Initialize FastMCP and load environment variables
mcp = FastMCP("search", host="localhost")
load_dotenv()

USER_AGENT = "search-app/1.0"
DUCKDUCKGO_URL = "https://html.duckduckgo.com/html/"

async def search_duckduckgo(query: str, limit: int) -> list:
    """Fetch search results from DuckDuckGo"""
    try:
        # Format query for URL
        formatted_query = query.replace(" ", "+")
        url = f"{DUCKDUCKGO_URL}?q={formatted_query}"
        
        # Set headers to avoid blocking
        headers = {
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            
            # Parse HTML response
            soup = BeautifulSoup(response.text, "html.parser")
            result_elements = soup.select('.result__body')
            
            # Extract results up to limit
            results = []
            for result in result_elements[:limit]:
                title_elem = result.select_one('.result__a')
                url_elem = result.select_one('.result__url')
                snippet_elem = result.select_one('.result__snippet')
                
                if title_elem and url_elem:
                    result_dict = {
                        "title": title_elem.get_text().strip(),
                        "url": url_elem.get_text().strip(),
                        "snippet": snippet_elem.get_text().strip() if snippet_elem else ""
                    }
                    results.append(result_dict)
            
            return results
            
    except httpx.TimeoutException:
        return [{"error": "Request timed out"}]
    except Exception as e:
        return [{"error": f"Search failed: {str(e)}"}]
    

async def fetch_url(url: str):
    """Fetch and extract clean text content from a webpage"""
    timeout = 15.0
    
    # Add https:// prefix if missing
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    # Headers to mimic a real browser
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    
    async with httpx.AsyncClient(follow_redirects=True) as client:
        try:
            print(f"Fetching content from: {url}")
            response = await client.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            
            # Parse HTML and extract clean text
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "header", "footer", "aside"]):
                script.decompose()
            
            # Try to find main content areas first
            main_content = soup.find('main') or soup.find('article') or soup.find('div', class_=['content', 'main', 'post', 'article'])
            
            if main_content:
                text = main_content.get_text()
            else:
                text = soup.get_text()
            
            # Clean up the text
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            # Limit text length to avoid extremely long responses
            if len(text) > 10000:
                text = text[:10000] + "... [content truncated]"
            
            return text
            
        except httpx.TimeoutException:
            return "Error: Request timed out while fetching the webpage"
        except httpx.HTTPStatusError as e:
            return f"Error: HTTP {e.response.status_code} - {e.response.reason_phrase}"
        except Exception as e:
            return f"Error: Failed to fetch webpage - {str(e)}"

@mcp.tool()
async def search_and_fetch(query: str, limit: int = 3):
    """
    Search the web using DuckDuckGo and return results.

    Args:
        query: The search query string
        limit: Maximum number of results to return (default: 3, maximum 10)

    Returns:
        List of dictionaries containing 
        - title
        - url
        - snippet 
        - summary markdown (empty if not available)
    """
    if not isinstance(query, str) or not query.strip():
        raise ValueError("Query must be a non-empty string")
    
    if not isinstance(limit, int) or limit < 1:
        raise ValueError("Limit must be a positive integer")
    
    # Cap limit at reasonable maximum
    limit = min(limit, 10)
    
    results = await search_duckduckgo(query, limit)
    
    if not results:
        return [{"message": f"No results found for '{query}'"}]
    
    # Create a list of fetch_url coroutines
    fetch_tasks = [fetch_url(item["url"]) for item in results]
    
    # Execute all fetch requests in parallel and wait for results
    summaries = await asyncio.gather(*fetch_tasks)
    
    # Assign summaries to their respective result items
    for item, summary in zip(results, summaries):
        item["summary"] = summary
    
    return results

# @mcp.tool()
async def search(query: str, limit: int = 3):
    """
    Search the web using DuckDuckGo and return results without scraping.

    Args:
        query: The search query string
        limit: Maximum number of results to return (default: 3, maximum 10)

    Returns:
        List of dictionaries containing 
        - title
        - url
        - snippet 
    """
    if not isinstance(query, str) or not query.strip():
        raise ValueError("Query must be a non-empty string")
    
    if not isinstance(limit, int) or limit < 1:
        raise ValueError("Limit must be a positive integer")
    
    # Cap limit at reasonable maximum
    limit = min(limit, 10)
    
    results = await search_duckduckgo(query, limit)
    
    if not results:
        return [{"message": f"No results found for '{query}'"}]
    
    return results

@mcp.tool()
async def fetch(url: str):
    """
    Scrape the HTML content and return clean text content from a webpage.

    Args:
        url: The URL to fetch and extract content from

    Returns:
        text: Clean text content extracted from the webpage
    """
    if not isinstance(url, str):
        raise ValueError("Query must be a non-empty string")
    
    text = await fetch_url(url)
    
    return text

def test_fetch_url():
    import asyncio
    async def run_test():
        # Mocking. In a real test, you would mock this, but for this example, we will call a real url.
        result = await fetch_url("https://github.com/BigWhaleLabs/web-search-duckduckgo/tree/master")
        # In a real test you would assert the returned result with a known good result.
        # For this example, we will just test that a result is returned.
        assert isinstance(result, str)
        # Add more specific assertions here.
        print("result recieved")
        print(result)

    try:
        asyncio.run(run_test())
    except Exception as e:
        print(f"Test failed: {e}")
        assert False

if __name__ == "__main__":
    # Required packages: pip install mcp httpx beautifulsoup4 python-dotenv
    mcp.run(transport="streamable-http")
    # test_fetch_url()
