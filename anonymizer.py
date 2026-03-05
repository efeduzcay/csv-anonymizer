import pandas as pd
import io
import re
from typing import Optional

DEFAULT_NAME_COLS = ["Ad Soyad", "AdSoyad", "Öğrenci Ad Soyad", "İsim", "Ad", "Soyad", "Name", "FullName"]
DEFAULT_DROP_COLS = [
    "TC", "TCKN", "TC Kimlik", "TC Kimlik No", "Kimlik No", "KimlikNo", "IdentityNo", "NationalId",
    "Öğrenci No", "Ogrenci No", "OgrenciNo", "StudentNo", "Student ID", "StudentId"
]

CHUNK_SIZE = 100_000


def normalize_text(text: str) -> str:
    if pd.isna(text):
        return ""
    text = str(text).strip().lstrip('\ufeff')
    text = (text
            .replace('I', 'ı').replace('İ', 'i').replace('Ğ', 'ğ')
            .replace('Ü', 'ü').replace('Ş', 'ş').replace('Ö', 'ö').replace('Ç', 'ç'))
    text = text.lower()
    return re.sub(r'\s+', ' ', text)


def _detect_encoding(file_bytes: bytes) -> str:
    for enc in ['utf-8-sig', 'utf-8', 'cp1254', 'iso-8859-9', 'latin1']:
        try:
            file_bytes.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue
    raise ValueError("CSV dosyası tanınan bir kodlamayla okunamadı (UTF-8, CP1254, Latin-1).")


def _clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [c.lstrip('\ufeff') for c in df.columns]
    return df


def parse_csv_bytes(file_bytes: bytes) -> pd.DataFrame:
    encoding = _detect_encoding(file_bytes)
    decoded = file_bytes.decode(encoding)
    df = pd.read_csv(io.StringIO(decoded), sep=None, engine='python', dtype=str)
    return _clean_columns(df)


def parse_csv_chunks(file_bytes: bytes):
    encoding = _detect_encoding(file_bytes)
    decoded = file_bytes.decode(encoding)
    return pd.read_csv(
        io.StringIO(decoded),
        sep=None,
        engine='python',
        dtype=str,
        chunksize=CHUNK_SIZE,
    )


def find_default_columns(df: pd.DataFrame):
    df_cols_lower = {c.lower(): c for c in df.columns}

    found_name_cols = []
    for dnc in DEFAULT_NAME_COLS:
        if dnc.lower() in df_cols_lower:
            found_name_cols.append(df_cols_lower[dnc.lower()])

    found_drop_cols = []
    for ddc in DEFAULT_DROP_COLS:
        tight_ddc = ddc.lower().replace(" ", "").replace("_", "")
        for actual_col in df.columns:
            clean_col = actual_col.lstrip('\ufeff')
            tight_actual = clean_col.lower().replace(" ", "").replace("_", "")
            if tight_ddc == tight_actual and actual_col not in found_drop_cols:
                found_drop_cols.append(actual_col)

    return found_name_cols, found_drop_cols


def _get_name_key(row: pd.Series, name_cols: list) -> tuple[str, str]:
    parts = [str(row[c]).strip() for c in name_cols if c in row.index and pd.notna(row.get(c))]
    display = " ".join(parts)
    return normalize_text(display), display


def anonymize_dataframe(file_bytes: bytes, name_cols: list, drop_cols: list):
    student_map: dict = {}
    pseudonym_counter = 1
    output_chunks = []
    total_rows = 0
    cols_dropped_identity: list = []
    first_chunk = True

    def get_or_create_pseudonym(norm_key: str, orig_display: str) -> str:
        nonlocal pseudonym_counter
        if norm_key not in student_map:
            student_map[norm_key] = {
                "original_value": orig_display,
                "pseudonym": f"X{pseudonym_counter}",
                "occurrences": 0,
            }
            pseudonym_counter += 1
        student_map[norm_key]["occurrences"] += 1
        return student_map[norm_key]["pseudonym"]

    for chunk in parse_csv_chunks(file_bytes):
        chunk = _clean_columns(chunk).reset_index(drop=True)

        if first_chunk:
            cols_dropped_identity = [c for c in drop_cols if c in chunk.columns]
            first_chunk = False

        chunk = chunk.drop(columns=[c for c in drop_cols if c in chunk.columns])

        anon_values = []
        for _, row in chunk.iterrows():
            norm_key, orig_display = _get_name_key(row, name_cols)
            anon_values.append(get_or_create_pseudonym(norm_key, orig_display) if norm_key else "")

        if len(name_cols) == 1:
            col = name_cols[0]
            if col in chunk.columns:
                chunk[col] = anon_values
        elif len(name_cols) > 1:
            chunk["AnonimAd"] = anon_values
            chunk = chunk.drop(columns=[c for c in name_cols if c in chunk.columns])

        total_rows += len(chunk)
        output_chunks.append(chunk)

    if not output_chunks:
        raise ValueError("CSV dosyası boş veya okunamadı.")

    result_df = pd.concat(output_chunks, ignore_index=True)
    csv_str = result_df.to_csv(index=False)
    anon_csv_bytes = b'\xef\xbb\xbf' + csv_str.encode('utf-8')

    dropped_all = cols_dropped_identity[:]
    if len(name_cols) > 1:
        dropped_all += [c for c in name_cols if c not in dropped_all]

    summary = {
        "total_rows": total_rows,
        "unique_students": len(student_map),
        "deleted_columns": dropped_all,
        "name_columns_used": name_cols,
    }

    return anon_csv_bytes, list(student_map.values()), summary
