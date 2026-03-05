import io
import json
import zipfile
import os
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd

from anonymizer import parse_csv_bytes, find_default_columns, anonymize_dataframe

app = FastAPI(title="CSV Anonimleştirici")

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


@app.get("/")
def read_root():
    return FileResponse("static/index.html")


@app.post("/api/columns")
async def get_columns(file: UploadFile = File(...)):
    file_bytes = await file.read()
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
async def anonymize(
    file: UploadFile = File(...),
    name_columns: str = Form("[]"),
    drop_columns: str = Form("[]"),
    generate_mapping: bool = Form(True),
):
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
