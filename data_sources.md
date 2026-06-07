# Data Sources — Local Scout Agent

**Pilot City:** Ho Chi Minh City, Vietnam
**Last Updated:** 2026-06-07

---

## Facebook Groups (Food Discussion)

| # | Group Name | URL | Access | Notes | Status |
|---|-----------|-----|--------|-------|--------|
| 1 | Ăn Gì Ở Sài Gòn | facebook.com/groups/angiisaigon | Public | Active daily, 200K+ members | Mapped |
| 2 | Review Quán Ăn Sài Gòn | facebook.com/groups/reviewquanansg | Public | Restaurant reviews with photos | Mapped |
| 3 | Hội Mê Ăn Uống SG | facebook.com/groups/hoimeanansg | Closed | Requires join, highly authentic | Mapped |
| 4 | Ẩm Thực Sài Gòn | facebook.com/groups/amthucsaigon | Public | Broader food culture discussion | Mapped |
| 5 | Food Hub Saigon | facebook.com/groups/foodhubsaigon | Public | Expats + locals, bilingual | Mapped |

**Scraping Strategy:** Apify Facebook Scraper actor for initial data pull; Playwright-based custom scraper for ongoing monitoring. Target: posts with >10 reactions and >5 comments. Extract: post text, comments, author profile indicators, photo metadata.

---

## Reddit Subreddits

| # | Subreddit | URL | Relevance | Notes |
|---|----------|-----|-----------|-------|
| 1 | r/VietNam | reddit.com/r/VietNam | High | General Vietnam discussion, frequent food threads |
| 2 | r/saigon | reddit.com/r/saigon | High | HCMC-specific, expat/local mix |
| 3 | r/SoutheastAsia | reddit.com/r/SoutheastAsia | Medium | Regional food travel questions |
| 4 | r/travel | reddit.com/r/travel | Low | Occasional Vietnam food threads |
| 5 | r/solotravel | reddit.com/r/solotravel | Low | Hidden gem requests from solo travelers |

**Scraping Strategy:** Reddit JSON API via old.reddit.com or pushshift.io for historical data. Rate limited naturally by Reddit's API (60 req/min). Extract: threads with "restaurant", "food", "eat", "recommend" keywords.

---

## Local Food Forums

| # | Source | URL | Language | Notes |
|---|--------|-----|----------|-------|
| 1 | Foody.vn | foody.vn/ho-chi-minh | VI | Largest VN restaurant platform, structured data |
| 2 | Eat.vn | eat.vn | VI | Restaurant listings with reviews |
| 3 | Diadiemanuong.com | diadiemanuong.com | VI | Food blog aggregator |
| 4 | Lozi.vn | lozi.vn/ho-chi-minh | VI | Food discovery + reviews |
| 5 | PasGo.vn | pasgo.vn/ho-chi-minh | VI | Vietnamese dining platform |

**Scraping Strategy:** crawl4ai with Playwright for JavaScript-rendered content. Foody.vn has structured HTML — parse review blocks directly. Respect robots.txt and implement 1 req/sec rate limit.

---

## Local Food Blogs

| # | Blog | URL | Language | Notes |
|---|------|-----|----------|-------|
| 1 | Sài Gòn Ăn Gì | saigonanchi.blogspot.com | VI | Veteran food blogger, 10+ years of archives |
| 2 | Ăn Chơi Sài Gòn | anchorisaigon.com | VI | Street food focused |
| 3 | Phượt Sài Gòn | phuotsaigon.net | VI | Backpacker food guides |
| 4 | Món Ngon Sài Gòn | monngonsaigon.vn | VI | Dish-specific recommendations |
| 5 | SaigonEats | saigoneseats.com | EN | Expat food blogger |
| 6 | Vietnam Coracle | vietnamcoracle.com | EN | Independent travel guides with food sections |
| 7 | Rusty Compass | rustycompass.com/vietnam | EN | Curated food listings, no paid placements |
| 8 | Migrationology | migrationology.com/category/vietnam | EN | Mark Wiens' Vietnam food content |
| 9 | Legal Nomads | legalnomads.com/vietnam | EN | Detailed HCMC food guides |
| 10 | The Ranting Panda | therantingpanda.com | EN | Detailed reviews |

**Scraping Strategy:** newspaper3k for article extraction + crawl4ai for rich content. Focus on posts from 2018 onward. Parse recipe names, locations mentioned, and author sentiment indicators.

---

## Foursquare / Swarm Check-in Data

- **Foursquare Places API:** Venue details, tips, ratings
- **Key signal:** Check-in count over time, ratio of local vs. visitor check-ins
- **Access:** Foursquare Places API (free tier: 50,000 requests/month)
- **Strategy:** Query venues within pilot area grid cells, store check-in statistics

---

## Instagram Hyper-local Tags

- **Relevant tags:** #saigonfood #saigoneats #quanngonsaigon #anchisaigon #hcmcfood #saigonstreetfood
- **Strategy:** Instagram Graph API (limited for non-business accounts). Alternative: public post scraping via crawl4ai on Instagram web with geotagged posts near pilot area
- **Note:** Respect Instagram robots.txt. Primary value: geocoded photo data with dish names in captions

---

## Access Checklist

| Service | API Key Required | Registered | Key Configured |
|---------|-----------------|------------|----------------|
| Reddit JSON API | No | N/A | N/A |
| Foody.vn | No | N/A | N/A |
| Facebook Graph API | Yes | No | No |
| Foursquare Places API | Yes | No | No |
| Google Places API | Yes | No | No |
| Mapbox | Yes | No | No |

---

## Robots.txt Compliance Notes

- **reddit.com:** Allows crawling of public API endpoints, disallows aggressive scraping
- **foody.vn:** Standard robots.txt, allows Googlebot, restricts generic crawlers
- **facebook.com:** Restricts most automated access; use Apify actors which comply with Facebook ToS
- **blogs (Blogspot, WordPress):** Generally permissive with standard delay directives
- **Rate limit policy:** All scrapers default to 1 req/sec per domain with exponential backoff on HTTP 429

---

*This file is a living document. Update source status and add new sources as discovered during Phase 1 development.*
