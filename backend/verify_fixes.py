import asyncio
from scraper import agentic_search_cimri, async_playwright

async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        
        # Test Case 1: Wrench Set (Should not match dryer)
        q1 = "Bosch Açık Uçlu Kombine Anahtar Seti 12 Parça"
        print(f"Testing: {q1}...")
        res1 = await agentic_search_cimri(q1, "Bosch", context)
        print(f"Result (Wrench): {res1}")
        
        # Test Case 2: Stihl MS 170 (Should not match karter/piston)
        q2 = "Stihl MS 170"
        print(f"Testing: {q2}...")
        res2 = await agentic_search_cimri(q2, "Stihl", context)
        print(f"Result (Chainsaw): {res2}")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test())
