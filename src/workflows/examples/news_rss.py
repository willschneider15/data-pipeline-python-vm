from typing import Dict, Any, List
import structlog
from datetime import datetime
import asyncio
import aiohttp
import feedparser
from bs4 import BeautifulSoup
import re

from src.core.workflow import BaseWorkflow, WorkflowResult, WorkflowConfig

logger = structlog.get_logger()

class NewsRSSConfig(WorkflowConfig):
    """Configuration for news RSS workflow."""
    name: str = "news_rss"
    enabled: bool = True
    interval: int = 1800  # 30 minutes
    options: Dict[str, Any] = {
        "feeds": [
            "https://feeds.content.dowjones.io/public/rss/mw_topstories"
        ],
        "keywords": [
            "stock", "market", "trading", "invest", "earnings",
            "revenue", "profit", "loss", "acquisition", "merger",
            "S&P 500", "Dow Jones", "Nasdaq", "IPO", "cryptocurrency",
            "interest rate", "Federal Reserve", "inflation", "economy"
        ]
    }

class NewsRSSWorkflow(BaseWorkflow):
    """Workflow for processing news RSS feeds."""
    
    def __init__(self, config: NewsRSSConfig):
        super().__init__(config)
        self._logger = logger.bind(workflow="news_rss")
        self.feeds = config.options.get("feeds", [])
        self.keywords = config.options.get("keywords", [])
        self.processed_entries = set()

    def _clean_text(self, text: str) -> str:
        """Clean HTML and normalize text."""
        if not text:
            return ""
        # Remove HTML tags
        soup = BeautifulSoup(text, "html.parser")
        text = soup.get_text()
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract relevant keywords from text."""
        found_keywords = []
        text_lower = text.lower()
        for keyword in self.keywords:
            if keyword.lower() in text_lower:
                found_keywords.append(keyword)
        return found_keywords

    async def _fetch_feed(self, feed_url: str) -> List[Dict[str, Any]]:
        """Fetch and parse RSS feed."""
        async with aiohttp.ClientSession() as session:
            async with session.get(feed_url) as response:
                if response.status != 200:
                    self._logger.error(
                        "feed_fetch_error",
                        url=feed_url,
                        status=response.status
                    )
                    return []
                
                content = await response.text()
                feed = feedparser.parse(content)
                
                entries = []
                for entry in feed.entries:
                    # Skip if already processed
                    if entry.id in self.processed_entries:
                        continue
                    
                    # Clean and process entry
                    title = self._clean_text(entry.title)
                    description = self._clean_text(entry.description if hasattr(entry, 'description') else "")
                    content = self._clean_text(entry.content[0].value if hasattr(entry, 'content') else "")
                    
                    # Extract keywords
                    all_text = f"{title} {description} {content}"
                    keywords = self._extract_keywords(all_text)
                    
                    if keywords:  # Only include entries with relevant keywords
                        entries.append({
                            "id": entry.id,
                            "title": title,
                            "description": description,
                            "link": entry.link,
                            "published": entry.published if hasattr(entry, 'published') else datetime.utcnow().isoformat(),
                            "keywords": keywords,
                            "source": "MarketWatch"
                        })
                        self.processed_entries.add(entry.id)
                
                return entries

    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process RSS feed data."""
        try:
            all_entries = []
            for feed_url in self.feeds:
                entries = await self._fetch_feed(feed_url)
                all_entries.extend(entries)
            
            # Sort by published date (newest first)
            all_entries.sort(key=lambda x: x.get("published", ""), reverse=True)
            
            return {
                "articles": all_entries,
                "total_articles": len(all_entries),
                "sources": list(set(entry["source"] for entry in all_entries)),
                "keywords_found": list(set(kw for entry in all_entries for kw in entry["keywords"]))
            }
        except Exception as e:
            self._logger.error(f"Error processing news data: {str(e)}")
            return {
                "error": str(e),
                "articles": []
            }

    async def execute(self, data: Dict[str, Any]) -> WorkflowResult:
        """Execute the workflow with the given data."""
        try:
            processed_data = await self.process(data)
            return WorkflowResult(success=True, data=processed_data)
        except Exception as e:
            self._logger.error("workflow_error", error=str(e))
            return WorkflowResult(success=False, error=str(e))

async def run_news_workflow():
    """Run the news RSS workflow with live data."""
    config = NewsRSSConfig()
    workflow = NewsRSSWorkflow(config)
    
    print("\nFetching news from MarketWatch RSS feed...")
    print("Press Ctrl+C to stop...")
    
    while True:
        try:
            result = await workflow.execute({})
            if result.success:
                print("\nNews Articles:")
                for article in result.data["articles"][:5]:  # Show top 5 articles
                    print(f"\nTitle: {article['title']}")
                    print(f"Source: {article['source']}")
                    print(f"Published: {article['published']}")
                    print(f"Keywords: {', '.join(article['keywords'])}")
                    print("---")
                print(f"\nTotal Articles: {result.data['total_articles']}")
                print(f"Sources: {', '.join(result.data['sources'])}")
                print(f"Keywords Found: {', '.join(result.data['keywords_found'])}")
            else:
                print(f"Error: {result.error}")
            
            # Wait for the configured interval
            await asyncio.sleep(config.interval)
            
        except KeyboardInterrupt:
            print("\nStopping news workflow...")
            break
        except Exception as e:
            print(f"Error: {str(e)}")
            await asyncio.sleep(60)  # Wait a minute before retrying

if __name__ == "__main__":
    asyncio.run(run_news_workflow()) 