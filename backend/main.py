import os
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import pandas as pd
import io
import uuid
import asyncio
from scraper import search_product, async_playwright

app = FastAPI()

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "temp_files"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# In-memory job store
jobs = {}

async def process_excel_task(job_id: str, source: str, contents: bytes):
    try:
        df = pd.read_excel(io.BytesIO(contents))
        
        # Find relevant columns
        name_col = None
        brand_col = None
        
        # Priority for name: EntegraAdi, then others
        for col in df.columns:
            if "entegraadi" in str(col).lower().replace(" ", ""):
                name_col = col
                break
        
        if not name_col:
            potential_name_cols = ["UrunAdi", "Ürün Adı", "Name", "Product Name", "Adı", "Açıklama"]
            for col in df.columns:
                if any(p.lower() in str(col).lower() for p in potential_name_cols):
                    name_col = col
                    break
        
        potential_brand_cols = ["Marka", "Brand", "Manufacturer", "Uretici"]
        for col in df.columns:
            if any(p.lower() in str(col).lower() for p in potential_brand_cols):
                brand_col = col
                break
                
        if not name_col:
            name_col = df.columns[0]
            
        total_rows = len(df)
        jobs[job_id]["total"] = total_rows
        
        url_col_name = "AkakceUrl" if source.lower() == "akakce" else "CimriUrl"
        urls = []
        
        # Start Playwright once for the entire batch
        from scraper import USER_AGENTS
        import random
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            
            for index, row in df.iterrows():
                try:
                    name = str(row[name_col])
                    brand = str(row[brand_col]) if brand_col and pd.notna(row[brand_col]) else ""
                    
                    # Create a FRESH context for EVERY search to rotate User-Agent
                    ua = random.choice(USER_AGENTS)
                    context = await browser.new_context(user_agent=ua)
                    
                    # Call search_product - passing the fresh context
                    # The search_product function handles duplication check internally
                    url = await search_product(source, name, brand, context)
                    urls.append(url if url else "Bulunamadı")
                    
                    # Clean up context immediately
                    await context.close()
                except Exception as row_error:
                    print(f"Error processing row {index}: {row_error}")
                    urls.append("Hata")
                
                # Update progress
                jobs[job_id]["progress"] = index + 1
                
                # Delay to look more human and avoid rate limits
                # Slightly longer for bulk to be safer
                await asyncio.sleep(random.uniform(0.8, 2.0))
            
            await browser.close()

            
        df[url_col_name] = urls
        
        # Save to temp file
        file_path = os.path.join(UPLOAD_DIR, f"{job_id}.xlsx")
        df.to_excel(file_path, index=False)
        
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["fileId"] = f"{job_id}.xlsx"
        
    except Exception as e:
        print(f"Error processing job {job_id}: {e}")
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)

@app.post("/search")
async def single_search(source: str = Form(...), name: str = Form(...), brand: str = Form("")):
    from scraper import USER_AGENTS
    import random
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ua = random.choice(USER_AGENTS)
        context = await browser.new_context(user_agent=ua)
        
        try:
            url = await search_product(source, name, brand, context)
            await browser.close()
            if url:
                return {"success": True, "url": url}
            return {"success": False, "message": "Ürün bulunamadı."}
        except Exception as e:
            await browser.close()
            return {"success": False, "message": f"Arama hatası: {str(e)}"}


@app.post("/upload")
async def upload_file(background_tasks: BackgroundTasks, source: str = Form(...), file: UploadFile = File(...)):
    contents = await file.read()
    job_id = str(uuid.uuid4())
    
    jobs[job_id] = {
        "status": "processing",
        "progress": 0,
        "total": 0,
        "source": source
    }
    
    background_tasks.add_task(process_excel_task, job_id, source, contents)
    
    return {"success": True, "jobId": job_id}

@app.get("/status/{job_id}")
async def get_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]

@app.get("/download/{fileId}")
async def download_file(fileId: str):
    file_path = os.path.join(UPLOAD_DIR, fileId)
    if os.path.exists(file_path):
        return FileResponse(
            file_path, 
            filename=f"sonuc_{fileId}", 
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    raise HTTPException(status_code=404, detail="File not found")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

