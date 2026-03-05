import requests
import json
import zipfile
import io
import os

URL = "http://127.0.0.1:8000/api/anonymize"
FILE_PATH = "/Users/efeduzcay/Desktop/anonim/test_ogrenciler.csv"
OUTPUT_ZIP = "/Users/efeduzcay/Desktop/anonim/test_results.zip"
EXTRACT_DIR = "/Users/efeduzcay/Desktop/anonim/test_results"

print(f"Testing CSV Anonymizer with: {FILE_PATH}")

with open(FILE_PATH, "rb") as f:
    files = {"file": f}
    data = {
        "name_columns": json.dumps(["Ad", "Soyad"]),
        "drop_columns": json.dumps(["TC Kimlik No", "Öğrenci No"]),
        "generate_mapping": "true"
    }
    
    response = requests.post(URL, files=files, data=data)

if response.status_code == 200:
    print("Success! Downloaded ZIP file.")
    with open(OUTPUT_ZIP, "wb") as f:
        f.write(response.content)
        
    print(f"Extracting to {EXTRACT_DIR}...")
    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        zf.extractall(EXTRACT_DIR)
        
    print("Files extracted:")
    for name in os.listdir(EXTRACT_DIR):
        print(" -", name)
        
    print("\nSummary Content:")
    with open(os.path.join(EXTRACT_DIR, "summary.json"), "r") as f:
        print(f.read())
        
    print("\nMapping Preview (first 5 lines):")
    with open(os.path.join(EXTRACT_DIR, "mapping.csv"), "r") as f:
        lines = f.readlines()
        for line in lines[:5]:
            print(line.strip())
            
    print("\nAnonymized CSV Preview (first 5 lines):")
    with open(os.path.join(EXTRACT_DIR, "anonymized.csv"), "r") as f:
        lines = f.readlines()
        for line in lines[:5]:
            print(line.strip())
else:
    print("Error:", response.status_code, response.text)
