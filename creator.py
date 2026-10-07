def find_images(query):
    """
    Search Wikimedia Commons for images matching the query.
    Includes a compliant User-Agent header to prevent 403 Forbidden errors.
    """
    url = "https://commons.wikimedia.org/w/api.php"
    
    # Wikimedia requires a descriptive User-Agent header identifying the application and contact info
    headers = {
        "User-Agent": "TechMindStudioAutomation/1.0 (https://github.com/youtube-auto-publisher; contact@example.com)"
    }
    
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": 6,
        "gsrlimit": 30,
        "prop": "imageinfo",
        "iiprop": "url|size",
        "iiurlwidth": 2200
    }
    
    response = requests.get(url, params=params, headers=headers)
    response.raise_for_status()
    
    data = response.json()
    urls = []
    
    if "query" in data and "pages" in data["query"]:
        pages = data["query"]["pages"]
        for page_id, page_info in pages.items():
            if "imageinfo" in page_info:
                for info in page_info["imageinfo"]:
                    if "thumburl" in info:
                        urls.append(info["thumburl"])
                    elif "url" in info:
                        urls.append(info["url"])
                        
    return urls
