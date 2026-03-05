import io
import json
import zipfile
import os
from fastapi import FastAPI, File, UploadFile, Form, Request, Depends, HTTPException, status
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from anonymizer import parse_csv_bytes, find_default_columns, anonymize_dataframe

# --- Security Config ---
# 1. API Key Authentication
API_KEY = os.getenv("ANONYMIZER_API_KEY", "change_this_secret_key_in_production")

# 2. Rate Limiting Setup
limiter = Limiter(key_func=get_remote_address)

# 3. File Size Limit (2 GB max)
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024 

app = FastAPI(title="CSV Anonimleştirici")

# Register rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if not os.path.exists("static"):
    os.makedirs("static")

app.mount("/static", StaticFiles(directory="static"), name="static")

# --- Security Dependency ---
def verify_api_key(api_key: str = Form(None), request: Request = None):
    # In a real app you might use headers (X-API-Key), checking form data for ease of use in this simple web client
    if not api_key:
        api_key = request.headers.get("X-API-Key")
        
    if api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz veya eksik API Anahtarı.",
        )
    return api_key

# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/")
def read_root():
    return FileResponse("static/index.html")


@app.post("/api/columns")
@limiter.limit("10/minute")  # Max 10 column fetch requests per minute per IP
async def get_columns(
    request: Request, 
    file: UploadFile = File(...),
    api_key: str = Depends(verify_api_key)
):
    # Enforce file size stream limit for columns parse (read only first chunk anyway)
    file_bytes = await file.read(10 * 1024 * 1024) # Only read first 10MB to detect columns, protect RAM
    
    try:
        df = parse_csv_bytes(file_bytes)
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

    name_cols_sug, drop_cols_sug = find_default_columns(df)
    return {
        "columns": list(df.columns),
        "suggested_name_columns": name_cols_sug,
        "suggested_drop_columns": drop_cols_sug,
    }


@app.post("/api/anonymize")
@limiter.limit("5/minute")   # Max 5 heavy processing requests per minute per IP
async def anonymize(
    request: Request,
    file: UploadFile = File(...),
    name_columns: str = Form("[]"),
    drop_columns: str = Form("[]"),
    generate_mapping: bool = Form(True),
    api_key: str = Depends(verify_api_key)
):
    # Read file with size limit enforcement
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)
    
    if file_size > MAX_FILE_SIZE:
        return JSONResponse(status_code=413, content={"error": "Dosya boyutu çok büyük. Maksimum 2GB yüklenebilir."})

    file_bytes = await file.read()

    try:
        name_cols: list = json.loads(name_columns)
        drop_cols: list = json.loads(drop_columns)
    except json.JSONDecodeError:
        return JSONResponse(status_code=422, content={"error": "Geçersiz JSON formatı."})

    if not name_cols:
        return JSONResponse(status_code=422, content={"error": "En az bir anonimleştirilecek sütun seçin."})

    try:
        anon_csv_bytes, mapping_list, summary = anonymize_dataframe(file_bytes, name_cols, drop_cols)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("anonymized.csv", anon_csv_bytes)

        if generate_mapping:
            mapping_df = pd.DataFrame(mapping_list, columns=["original_value", "pseudonym", "occurrences"])
            mapping_bytes = b'\xef\xbb\xbf' + mapping_df.to_csv(index=False).encode('utf-8')
            zf.writestr("mapping.csv", mapping_bytes)

        zf.writestr("summary.json", json.dumps(summary, indent=4, ensure_ascii=False).encode("utf-8"))

    zip_buffer.seek(0)
    headers = {"Content-Disposition": 'attachment; filename="anonymizer_results.zip"'}
    return StreamingResponse(zip_buffer, media_type="application/zip", headers=headers)
