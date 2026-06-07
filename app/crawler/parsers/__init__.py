from app.crawler.parsers.forum_parser import parse_foody_page, parse_generic_forum
from app.crawler.parsers.reddit_parser import parse_reddit_search_results, parse_reddit_thread
from app.crawler.parsers.blog_parser import parse_blog_article

__all__ = [
    "parse_foody_page",
    "parse_generic_forum",
    "parse_reddit_search_results",
    "parse_reddit_thread",
    "parse_blog_article",
]
