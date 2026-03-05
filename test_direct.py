"""
Direct unit test for the anonymizer logic without HTTP.
Tests parse_csv_bytes, find_default_columns and anonymize_dataframe directly.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from anonymizer import parse_csv_bytes, find_default_columns, anonymize_dataframe

CSV_PATH = "/Users/efeduzcay/Desktop/anonim/test_ogrenciler.csv"

with open(CSV_PATH, "rb") as f:
    file_bytes = f.read()

print("=== Step 1: Parsing CSV ===")
df = parse_csv_bytes(file_bytes)
print(f"Columns: {list(df.columns)}")
print(f"Rows: {len(df)}")
print()

print("=== Step 2: Auto-detecting columns ===")
name_cols, drop_cols = find_default_columns(df)
print(f"Name columns: {name_cols}")
print(f"Drop columns: {drop_cols}")
print()

print("=== Step 3: Anonymizing ===")
anon_bytes, mapping_list, summary = anonymize_dataframe(file_bytes, name_cols, drop_cols)
print("Summary:", summary)
print()

print("=== Anonymized CSV (first 5 rows) ===")
decoded_lines = anon_bytes.decode('utf-8-sig', errors='replace').splitlines()
for line in decoded_lines[:6]:
    print(line)
print()

print("=== Mapping ===")
for entry in mapping_list:
    print(f"  {entry['original_value']:30s} -> {entry['pseudonym']}  (appears {entry['occurrences']}x)")
