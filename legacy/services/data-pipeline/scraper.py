"""
NutriCrawler - A robust web scraper for nutrition data.
"""

import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from typing import Optional


class NutriCrawler:
    """
    A web crawler designed to fetch and parse nutrition data from web pages.
    
    Attributes:
        user_agent (UserAgent): Instance for generating random user agents.
        session (requests.Session): Persistent session for making HTTP requests.
    """

    def __init__(self, timeout: int = 10):
        """
        Initialize the NutriCrawler.
        
        Args:
            timeout: Request timeout in seconds.
        """
        self.user_agent = UserAgent()
        self.session = requests.Session()
        self.timeout = timeout

    def _get_headers(self) -> dict:
        """Generate request headers with a random user agent."""
        return {
            "User-Agent": self.user_agent.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }

    def fetch_data(self, url: str) -> dict:
        """
        Fetch and parse nutrition data from the given URL.
        
        Args:
            url: The URL to scrape.
            
        Returns:
            A dictionary containing:
                - success (bool): Whether the request was successful.
                - status (str): "Success" or "Failed".
                - status_code (int): HTTP status code or None if request failed.
                - url (str): The requested URL.
                - title (str): Page title if found.
                - content (str): Cleaned text content.
                - links (list): List of links found on the page.
                - error (str): Error message if request failed.
        """
        result = {
            "success": False,
            "status": "Failed",
            "status_code": None,
            "url": url,
            "title": None,
            "content": None,
            "links": [],
            "error": None,
        }

        try:
            response = self.session.get(
                url,
                headers=self._get_headers(),
                timeout=self.timeout,
            )
            
            # Fix encoding issues by using apparent_encoding
            response.encoding = response.apparent_encoding
            
            result["status_code"] = response.status_code
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Extract title
            title_tag = soup.find("title")
            result["title"] = title_tag.get_text(strip=True) if title_tag else "No title found"

            # Remove script and style elements
            for element in soup(["script", "style", "nav", "footer", "header"]):
                element.decompose()

            # Extract main content
            main_content = soup.find("main") or soup.find("article") or soup.find("body")
            if main_content:
                result["content"] = main_content.get_text(separator="\n", strip=True)
            else:
                result["content"] = soup.get_text(separator="\n", strip=True)

            # Extract links
            result["links"] = [
                {"text": a.get_text(strip=True), "href": a.get("href")}
                for a in soup.find_all("a", href=True)
                if a.get("href") and not a.get("href").startswith("#")
            ]

            result["success"] = True
            result["status"] = "Success"

        except requests.exceptions.Timeout:
            result["error"] = f"Request timed out after {self.timeout} seconds."
        except requests.exceptions.TooManyRedirects:
            result["error"] = "Too many redirects encountered."
        except requests.exceptions.HTTPError as e:
            result["status_code"] = e.response.status_code
            result["error"] = f"HTTP error: {e.response.status_code} - {e.response.reason}"
        except requests.exceptions.ConnectionError:
            result["error"] = "Failed to establish a connection."
        except requests.exceptions.RequestException as e:
            result["error"] = f"Request failed: {str(e)}"
        except Exception as e:
            result["error"] = f"Unexpected error: {str(e)}"

        return result


if __name__ == "__main__":
    # Quick test
    crawler = NutriCrawler()
    
    test_url = "https://www.example.com"
    print(f"Testing NutriCrawler with: {test_url}\n")
    
    data = crawler.fetch_data(test_url)
    
    print(f"Status: {data['status']}")
    print(f"HTTP Code: {data['status_code']}")
    
    if data["success"]:
        print(f"✅ Success!")
        print(f"Title: {data['title']}")
        print(f"Content preview: {data['content'][:200]}...")
        print(f"Found {len(data['links'])} links.")
    else:
        print(f"❌ Failed: {data['error']}")
