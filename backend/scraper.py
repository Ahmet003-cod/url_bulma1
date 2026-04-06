import asyncio
from playwright.async_api import async_playwright
import urllib.parse
from thefuzz import fuzz
import re
import random

# Negative keywords to prevent machine vs accessory/spare part mismatch
NEGATIVES = [
    "torba", "filtre", "hortum", "aksesuar", "yedek parça", "batarya", 
    "şarj cihazı", "kablo", "uç set", "mandren", "adaptör", "kağıt", 
    "bezi", "başlığı", "fırçası", "aparatı", "akü", "akülü", "seti", "set",
    "piston", "karter", "silindir", "bilya", "buji", "kapak", "zincir",
    "şanzıman", "dişli", "segman", "yağ", "yakıt", "karbüratör", "motoru değil"
]

# User-Agent pool for bot evasion
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edge/120.0.0.0"
]

def clean_name(name):
    """Removes common technical suffixes to find the base model."""
    suffixes = [
        r"taşıma çantalı", r"çantalı", r"solo", r"akülü", r"vidalama", 
        r"kırıcı-delici", r"zımba çakma", r"çivi ve", r"şarjlı", r"li-ion",
        r"li-i", r"li", r"-\d+v", r"\d+v", r"18v", r"12v", r"36v", r"54v"
    ]
    cleaned = name.lower()
    for s in suffixes:
        cleaned = re.sub(s, "", cleaned)
    return cleaned.strip()

async def human_delay(min_ms=500, max_ms=1500):
    """Adds a random delay to mimic human behavior."""
    delay = random.randint(min_ms, max_ms) / 1000.0
    await asyncio.sleep(delay)

def find_best_match(query, brand, candidates, threshold=50, force_tech_match=False):
    """
    Finds the best matching candidate's URL.
    """
    if not candidates:
        return None
    
    best_candidate = None
    highest_score = -1
    
    clean_query = query.lower().strip()
    
    # If brand is not provided, try to extract it from the query
    # We'll check for common brands in the query to enforce matching
    common_brands = ["bosch", "ryobi", "einhell", "makita", "dewalt", "stanley", "black+decker", "milwaukee", "stihl", "husqvarna"]
    clean_brand = brand.lower().strip() if brand else ""
    if not clean_brand:
        for b in common_brands:
            if b in clean_query:
                clean_brand = b
                break
    
    # Model patterns - improved to handle variations and case sensitivity
    model_pattern = r"([A-Z]{1,}\s?\d+-\d+|[A-Z]{1,}-\d+|[A-Z]{1,}\d+-\d+|[A-Z]{1,}\d+[A-Z]{1,}-\d+|[A-Z]{1,}\s?\d+/\d+|\d+\.\d+\s?Ah|\d+\s?Ah|\d+\s?V|\d+V|\d+X\d+\.\d+AH|\d+X\d+AH)"
    query_models = re.findall(model_pattern, clean_query.upper())
    
    # Check if user is specifically searching for an accessory
    is_query_accessory = any(n in clean_query for n in NEGATIVES)
    
    for cand in candidates:
        title = cand['title'].lower().strip()
        url = cand['url'].lower()
        
        # 3. Smart Word-by-Word Analysis (Deep Match)
        # Ensure most non-brand words from query are in title
        query_words = [w for w in clean_query.split() if len(w) > 2 and w != clean_brand]
        title_words = [w for w in title.split()]
        
        match_count = 0
        for qw in query_words:
            if any(qw in tw for tw in title_words):
                match_count += 1
                
        # If less than 50% of specific words match, penalize or skip
        # This prevents "Anahtar" query matching "Kurutma" title
        if query_words and (match_count / len(query_words)) < 0.5:
            continue 
        
        # 1. Brand Enforcement: If brand is detected/provided, it MUST be in the title
        if clean_brand and clean_brand not in title:
            alt_brand = clean_brand.replace("+", " ").replace("-", " ")
            if alt_brand not in title:
                continue
            
        # 2. Tech Match Enforcement (Specifically for Cimri's technical errors)
        if force_tech_match:
            try:
                def get_important_floats(text):
                    nums = re.findall(r"\d+\.\d+|\d+", text.lower())
                    return {float(n) for n in nums if float(n) > 2.0}
                
                query_floats = get_important_floats(clean_query)
                title_floats = get_important_floats(title)
                
                if not query_floats.issubset(title_floats):
                    continue
            except:
                pass

        # 3. Accessory/Part Check
        is_title_accessory = any(n in title for n in NEGATIVES)
        accessory_penalty = 0
        if is_title_accessory and not is_query_accessory:
            accessory_penalty = 60 # Increased penalty
        elif not is_title_accessory and is_query_accessory:
            accessory_penalty = 20 
            
        # 4. Similarity Score
        score = fuzz.token_set_ratio(clean_query, title)
        score -= accessory_penalty
        
        # 5. Model Number Check (Important boost)
        model_match = any(m in title.upper() for m in query_models) if query_models else True
        
        if model_match:
            score += 40 
        else:
            score -= 10
            
        if score > highest_score:
            highest_score = score
            best_candidate = cand['url']
            
    if highest_score >= threshold:
        return best_candidate
    return None

async def extract_candidates(page):
    """Universal extractor for search results."""
    candidates = []
    
    # Method 1: Look for product titles in the main results container
    # For Cimri, we want to avoid 'Son Gezdiklerin' or 'Popüler Ürünler' sections.
    # We select elements that are NOT inside recommendation sections.
    elements = await page.query_selector_all("h2, h3, .product-name, .title")
    for el in elements:
        try:
            # Improved 'is_ignored' check to avoid skipping the entire page
            is_ignored = await page.evaluate("""(el) => {
                const ignoredKeywords = ['son gezdiklerin', 'popüler ürünler', 'sizin için seçtiklerimiz', 'benzer ürünler'];
                let parent = el.parentElement;
                while (parent && parent.tagName !== 'BODY') {
                    // Check if this specific parent is a recommendation section by looking for its header
                    const h = parent.querySelector('h1, h2, h3');
                    if (h && h !== el) {
                        const hText = h.innerText.toLowerCase();
                        if (ignoredKeywords.some(k => hText.includes(k))) return true;
                    }
                    if (parent.classList.contains('recommendation') || parent.id.includes('recommendation')) return true;
                    parent = parent.parentElement;
                }
                return false;
            }""", el)
            
            title = await el.inner_text()
            title = title.strip()
            
            if is_ignored:
                # print(f"DEBUG: Ignoring element {title} because it's in a recommendations section.")
                continue

            if not title or len(title) < 5: continue
            
            # Find the href. Try parent, then siblings, then children of the card container
            href = None
            parent_a = await el.query_selector("xpath=./ancestor::a")
            if parent_a:
                href = await parent_a.get_attribute("href")
            
            if not href:
                # Look for any link in the same parent container that looks like a product page
                parent_card = await el.evaluate_handle("el => el.closest('div, li, article')")
                if parent_card:
                    # Cimri specific product link patterns
                    link_el = await parent_card.query_selector("a[href*='/en-ucuz-'], a[href*='/category/'], a[href*='/product/']")
                    if link_el:
                        href = await link_el.get_attribute("href")
            
            if not href:
                # Last resort: check immediate siblings
                parent_div = await el.query_selector("xpath=./..")
                if parent_div:
                    link_el = await parent_div.query_selector("a")
                    if link_el:
                        href = await link_el.get_attribute("href")
            
            if href:
                # Filter out direct external store links
                if "cimri.com" not in href and "http" in href: 
                    continue
                
                # Cimri ID Pattern Check: Real products have a unique numeric ID after a comma 
                # (e.g. ,2205175232). Categories like 'çamaşır-kurutma-makineleri' DO NOT.
                if "cimri.com" in href or href.startswith("/"):
                    # Check if URL ends with comma and at least 5 digits
                    if not re.search(r",\d{5,}", href):
                        # print(f"DEBUG: Skipping category page: {href}")
                        continue
                        
                candidates.append({"title": title, "url": href})
                # print(f"DEBUG: Found candidate: {title} -> {href}")
        except Exception as e:
            # print(f"DEBUG Error in extract_candidates: {e}")
            continue
            
    # Method 2: Specific fallback for Cimri-like card structures
    if not candidates:
        # Only look for product links that look like Cimri internal product pages
        all_links = await page.query_selector_all("a[href*='/en-ucuz-']")
        for link in all_links:
            try:
                title = await link.inner_text()
                href = await link.get_attribute("href")
                if title and len(title.strip()) > 10 and href:
                    candidates.append({"title": title.strip(), "url": href})
            except:
                continue
                
    return candidates

async def follow_akakce_suggestions(page):
    """Follows suggestions if no results."""
    suggestion_selectors = [
        "a:has-text('için de sonuçlar gösteriliyor')",
        "a:has-text('İlgili kategoriye git')",
        ".no-result a"
    ]
    for sel in suggestion_selectors:
        try:
            link = await page.query_selector(sel)
            if link:
                await link.click()
                await page.wait_for_load_state("networkidle")
                return True
        except:
            continue
    return False

async def agentic_search_akakce(name, brand, page_or_context):
    if not page_or_context:
        # If no context is provided, we can't continue without breaking the flow
        # But we previously fixed main.py to always provide it.
        # Still, adding a fallback for safety.
        print("Error: No browser page or context provided to agentic_search_akakce")
        return None

    if hasattr(page_or_context, 'new_page'):
        page = await page_or_context.new_page()
    else:
        page = page_or_context

    # Smart search stages to avoid "Bosch Bosch" duplication
    base_name = clean_name(name)
    brand_lower = brand.lower().strip() if brand else ""
    
    search_stages = [name]
    
    if brand_lower and brand_lower not in base_name.lower():
        search_stages.append(f"{brand} {base_name}")
    else:
        search_stages.append(base_name)

    # Remove duplicates
    search_stages = list(dict.fromkeys(search_stages))

    for stage_query in search_stages:
        search_url = f"https://www.akakce.com/arama/?q={urllib.parse.quote(stage_query)}"
        try:
            # Random delay before navigation
            await human_delay(300, 800)
            await page.goto(search_url, timeout=45000, wait_until="domcontentloaded")
            
            # Additional scroll to look human
            await page.mouse.wheel(0, 500)
            await human_delay(200, 500)
        except Exception as e:
            print(f"Akakce error for {stage_query}: {e}")
        
        candidates = await extract_candidates(page)
        if not candidates:
            if await follow_akakce_suggestions(page):
                candidates = await extract_candidates(page)
        
        for c in candidates:
            if not c['url'].startswith("http"):
                c['url'] = f"https://www.akakce.com{c['url']}"
        
        result = find_best_match(name, brand, candidates)
        if result: 
            if hasattr(page_or_context, 'new_page'): await page.close()
            return result
    
    # Broad fallback
    words = name.split()
    if len(words) > 3:
        broad_query = " ".join(words[:4])
        search_url = f"https://www.akakce.com/arama/?q={urllib.parse.quote(broad_query)}"
        try:
            await page.goto(search_url, timeout=30000, wait_until="domcontentloaded")
            candidates = await extract_candidates(page)
            for c in candidates:
                if not c['url'].startswith("http"): c['url'] = f"https://www.akakce.com{c['url']}"
            result = find_best_match(name, brand, candidates, threshold=40)
            if result:
                if hasattr(page_or_context, 'new_page'): await page.close()
                return result
        except:
            pass

    if hasattr(page_or_context, 'new_page'): await page.close()
    return None

async def agentic_search_cimri(name, brand, page_or_context):
    if not page_or_context:
        print("Error: No browser page or context provided to agentic_search_cimri")
        return None

    if hasattr(page_or_context, 'new_page'):
        page = await page_or_context.new_page()
    else:
        page = page_or_context
    
    # 1. First Attempt: Use direct input if possible (more reliable for special chars)
    try:
        await page.goto("https://www.cimri.com", timeout=30000, wait_until="domcontentloaded")
        search_box = await page.query_selector("input[placeholder*='ara'], input#search-input, .search-input")
        if search_box:
            await search_box.fill(name)
            await search_box.press("Enter")
            await page.wait_for_load_state("networkidle", timeout=30000)
            await page.mouse.wheel(0, 500)
            await human_delay(500, 1000)
            
            candidates = await extract_candidates(page)
            if candidates:
                for c in candidates:
                    if not c['url'].startswith("http"): c['url'] = f"https://www.cimri.com{c['url']}"
                result = find_best_match(name, brand, candidates, threshold=35, force_tech_match=True)
                if result:
                    if hasattr(page_or_context, 'new_page'): await page.close()
                    return result
    except Exception as e:
        print(f"Cimri direct search failed, falling back to URL search: {e}")

    # 2. Fallback: Search Stages via URL
    base_name = clean_name(name)
    brand_lower = brand.lower().strip() if brand else ""
    
    search_stages = [name]
    if brand_lower and brand_lower not in base_name.lower():
        search_stages.append(f"{brand} {base_name}")
    else:
        search_stages.append(base_name)
    
    # Stage 3: Remove special characters like '+' and '/' that might confuse search
    clean_plus = re.sub(r'[\+\/]', ' ', name)
    if clean_plus != name:
        search_stages.append(clean_plus)
        
    search_stages = list(dict.fromkeys(search_stages))

    for stage_query in search_stages:
        try:
            search_url = f"https://www.cimri.com/arama?q={urllib.parse.quote(stage_query)}"
            await human_delay(400, 1000)
            # Use networkidle for Cimri as it loads results dynamically
            await page.goto(search_url, timeout=45000, wait_until="networkidle")
            await page.mouse.wheel(0, 500)
            await human_delay(500, 1000)
            
            candidates = await extract_candidates(page)
            # Fallback for Cimri specific card links
            if not candidates:
                # Find all links that look like product pages
                links = await page.query_selector_all("a[href*='/en-ucuz-']")
                for link in links:
                    title = await link.inner_text()
                    href = await link.get_attribute("href")
                    if title and href:
                        candidates.append({"title": title.strip(), "url": href})

            for c in candidates:
                if not c['url'].startswith("http"): c['url'] = f"https://www.cimri.com{c['url']}"
            
            result = find_best_match(name, brand, candidates, threshold=35)
            if result: 
                if hasattr(page_or_context, 'new_page'): await page.close()
                return result
        except Exception as e:
            print(f"Cimri error for {stage_query}: {e}")
            continue

    if hasattr(page_or_context, 'new_page'): await page.close()
    return None

async def search_product(source: str, query: str, brand: str = "", page_or_context=None):
    if source.lower() == "akakce":
        return await agentic_search_akakce(query, brand, page_or_context)
    elif source.lower() == "cimri":
        return await agentic_search_cimri(query, brand, page_or_context)
    return None
    return None


