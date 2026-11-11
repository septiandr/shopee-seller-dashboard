import os
import glob
import csv
import json
import sqlite3
import datetime
from pathlib import Path

from importer import get_db, load_config, DB_FILE

def init_ads_table():
    with get_db() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS shopee_ads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ad_name TEXT NOT NULL,
            ad_status TEXT,
            ad_type TEXT,
            product_id TEXT NOT NULL,
            bidding_mode TEXT,
            placement TEXT,
            period_raw TEXT NOT NULL,
            period_start TEXT,
            period_end TEXT,
            target_roas REAL,
            impressions INTEGER DEFAULT 0,
            clicks INTEGER DEFAULT 0,
            ctr_pct REAL DEFAULT 0,
            add_to_cart INTEGER DEFAULT 0,
            conversions INTEGER DEFAULT 0,
            direct_conversions INTEGER DEFAULT 0,
            units_sold INTEGER DEFAULT 0,
            direct_units_sold INTEGER DEFAULT 0,
            ad_gmv REAL DEFAULT 0,
            direct_gmv REAL DEFAULT 0,
            ad_spend REAL DEFAULT 0,
            actual_roas REAL DEFAULT 0,
            direct_roas REAL DEFAULT 0,
            acos_pct REAL DEFAULT 0,
            direct_acos_pct REAL DEFAULT 0,
            cpc REAL DEFAULT 0,
            cpa REAL DEFAULT 0,
            voucher_amount REAL DEFAULT 0,
            source_file TEXT,
            imported_at TEXT,
            UNIQUE(product_id, period_raw)
        )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ads_period ON shopee_ads(period_raw)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ads_product_id ON shopee_ads(product_id)")

        conn.execute("""
        CREATE TABLE IF NOT EXISTS ads_import_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT UNIQUE,
            file_path TEXT,
            file_size INTEGER,
            file_mtime REAL,
            imported_at TEXT,
            total_rows INTEGER,
            inserted_rows INTEGER,
            updated_rows INTEGER
        )
        """)

def parse_num_ads(v):
    if v is None:
        return 0.0
    s = str(v).strip().replace("Rp", "").replace("rp", "").replace("%", "").replace(" ", "").replace(",", "")
    if not s or s.lower() == "nan" or s == "-":
        return 0.0
    try:
        return float(s)
    except:
        return 0.0

def import_ads_csv_file(file_path):
    init_ads_table()
    config = load_config()
    p = Path(file_path)
    if not p.exists():
        return {"status": "error", "message": f"File {file_path} tidak ditemukan"}

    with open(str(p), "r", encoding="utf-8", errors="ignore") as fp:
        rows = list(csv.reader(fp))

    if len(rows) < 8:
        return {"status": "error", "message": "Format file iklan tidak valid (baris kurang dari 8)"}

    period_raw = ""
    for r in rows[:7]:
        if r and len(r) >= 2 and r[0].strip().lower() == "periode":
            period_raw = r[1].strip()

    # Parse period start & end dates
    period_start = ""
    period_end = ""
    if period_raw and "-" in period_raw:
        parts = period_raw.split("-")
        try:
            d1, m1, y1 = parts[0].strip().split("/")
            period_start = f"{y1}-{m1}-{d1}"
            d2, m2, y2 = parts[1].strip().split("/")
            period_end = f"{y2}-{m2}-{d2}"
        except:
            pass

    headers = [h.strip() for h in rows[7]]
    hmap = {h: i for i, h in enumerate(headers) if h}

    required_keys = ["Nama Iklan", "Kode Produk", "Omzet Penjualan", "Biaya"]
    for k in required_keys:
        if k not in hmap:
            return {"status": "error", "message": f"Kolom wajib '{k}' tidak ditemukan pada CSV iklan"}

    inserted = 0
    updated = 0
    total = 0

    with get_db() as conn:
        for r in rows[8:]:
            if len(r) <= max(hmap.values()):
                continue

            def g(name):
                idx = hmap.get(name)
                return r[idx].strip() if idx is not None and idx < len(r) else ""

            product_id = g("Kode Produk")
            ad_name = g("Nama Iklan")
            if not product_id or not ad_name:
                continue

            total += 1
            ad_status = g("Status")
            ad_type = g("Jenis Iklan")
            bidding_mode = g("Mode Bidding")
            placement = g("Penempatan Iklan")

            impressions = int(parse_num_ads(g("Dilihat")))
            clicks = int(parse_num_ads(g("Jumlah Klik")))
            ctr_pct = parse_num_ads(g("Persentase Klik"))
            add_to_cart = int(parse_num_ads(g("Tambah ke Keranjang")))
            conversions = int(parse_num_ads(g("Konversi")))
            direct_conversions = int(parse_num_ads(g("Konversi Langsung")))
            units_sold = int(parse_num_ads(g("Produk Terjual")))
            direct_units_sold = int(parse_num_ads(g("Terjual Langsung")))
            ad_gmv = parse_num_ads(g("Omzet Penjualan"))
            direct_gmv = parse_num_ads(g("Penjualan Langsung (GMV Langsung)"))
            ad_spend = parse_num_ads(g("Biaya"))
            actual_roas = parse_num_ads(g("Efektifitas Iklan"))
            direct_roas = parse_num_ads(g("Efektivitas Langsung"))
            acos_pct = parse_num_ads(g("Persentase Biaya Iklan terhadap Penjualan dari Iklan (ACOS)"))
            direct_acos_pct = parse_num_ads(g("Persentase Biaya Iklan terhadap Penjualan dari Iklan Langsung (ACOS Langsung)"))
            voucher_amount = parse_num_ads(g("Voucher Amount"))

            cpc = (ad_spend / clicks) if clicks > 0 else 0.0
            cpa = (ad_spend / conversions) if conversions > 0 else 0.0

            cur = conn.execute(
                "SELECT id, target_roas FROM shopee_ads WHERE product_id = ? AND period_raw = ?",
                (product_id, period_raw)
            )
            existing = cur.fetchone()

            imported_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            product_target_roas_map = config.get("product_target_roas", {})
            default_target = product_target_roas_map.get(str(product_id))

            if existing:
                # Update existing record while PRESERVING user-set target_roas if already set
                target_roas = existing["target_roas"] if existing["target_roas"] is not None else default_target
                conn.execute("""
                UPDATE shopee_ads SET
                    ad_name = ?,
                    ad_status = ?,
                    ad_type = ?,
                    bidding_mode = ?,
                    placement = ?,
                    period_start = ?,
                    period_end = ?,
                    target_roas = ?,
                    impressions = ?,
                    clicks = ?,
                    ctr_pct = ?,
                    add_to_cart = ?,
                    conversions = ?,
                    direct_conversions = ?,
                    units_sold = ?,
                    direct_units_sold = ?,
                    ad_gmv = ?,
                    direct_gmv = ?,
                    ad_spend = ?,
                    actual_roas = ?,
                    direct_roas = ?,
                    acos_pct = ?,
                    direct_acos_pct = ?,
                    cpc = ?,
                    cpa = ?,
                    voucher_amount = ?,
                    source_file = ?,
                    imported_at = ?
                WHERE id = ?
                """, (
                    ad_name, ad_status, ad_type, bidding_mode, placement,
                    period_start, period_end, target_roas, impressions, clicks, ctr_pct,
                    add_to_cart, conversions, direct_conversions, units_sold,
                    direct_units_sold, ad_gmv, direct_gmv, ad_spend,
                    actual_roas, direct_roas, acos_pct, direct_acos_pct,
                    cpc, cpa, voucher_amount, p.name, imported_at, existing["id"]
                ))
                updated += 1
            else:
                # Insert new record with config default target_roas
                target_roas = default_target
                conn.execute("""
                INSERT INTO shopee_ads (
                    ad_name, ad_status, ad_type, product_id, bidding_mode, placement,
                    period_raw, period_start, period_end, target_roas, impressions,
                    clicks, ctr_pct, add_to_cart, conversions, direct_conversions,
                    units_sold, direct_units_sold, ad_gmv, direct_gmv, ad_spend,
                    actual_roas, direct_roas, acos_pct, direct_acos_pct, cpc, cpa,
                    voucher_amount, source_file, imported_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """, (
                    ad_name, ad_status, ad_type, product_id, bidding_mode, placement,
                    period_raw, period_start, period_end, target_roas, impressions,
                    clicks, ctr_pct, add_to_cart, conversions, direct_conversions,
                    units_sold, direct_units_sold, ad_gmv, direct_gmv, ad_spend,
                    actual_roas, direct_roas, acos_pct, direct_acos_pct, cpc, cpa,
                    voucher_amount, p.name, imported_at
                ))
                inserted += 1

        file_stat = p.stat()
        conn.execute("""
        INSERT OR REPLACE INTO ads_import_logs (
            file_name, file_path, file_size, file_mtime, imported_at, total_rows, inserted_rows, updated_rows
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            p.name, str(p.resolve()), file_stat.st_size, file_stat.st_mtime,
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            total, inserted, updated
        ))
        conn.commit()

    return {
        "status": "success",
        "file": p.name,
        "period": period_raw,
        "total_rows": total,
        "inserted": inserted,
        "updated": updated
    }

def sync_ads_watch_folder(force=False):
    config = load_config()
    base_dir = Path(__file__).parent
    configured_folder = config.get("watch_folder_iklan", str(Path.home() / "Downloads" / "iklan"))

    candidate_dirs = [
        base_dir / "iklan",
        base_dir,
        Path(configured_folder),
        Path.home() / "Downloads"
    ]

    csv_files = []
    for d in candidate_dirs:
        if d.exists() and d.is_dir():
            csv_files.extend(list(d.glob("Data+Keseluruhan+Iklan*.csv")))
            csv_files.extend(list(d.glob("*.csv")))

    # Deduplicate by resolved path and sort chronologically
    unique_files = {str(f.resolve()): f for f in csv_files}.values()
    sorted_files = sorted(unique_files, key=os.path.getmtime)

    if not sorted_files:
        return {"status": "info", "message": "Tidak ada file CSV iklan di folder iklan"}

    results = []
    for f in sorted_files:
        if not force:
            with get_db() as conn:
                cur = conn.execute("SELECT file_mtime, file_size FROM ads_import_logs WHERE file_name = ?", (f.name,))
                log = cur.fetchone()
                stat = f.stat()
                if log and log["file_mtime"] == stat.st_mtime and log["file_size"] == stat.st_size:
                    continue
        res = import_ads_csv_file(f)
        results.append(res)

    return {"status": "success", "processed": results, "total_files": len(sorted_files)}

def update_ad_target_roas(ad_id: int, target_roas: float):
    with get_db() as conn:
        conn.execute("UPDATE shopee_ads SET target_roas = ? WHERE id = ?", (target_roas, ad_id))
        conn.commit()
    return {"status": "success", "id": ad_id, "target_roas": target_roas}

if __name__ == "__main__":
    init_ads_table()
    res = sync_ads_watch_folder(force=True)
    print("Ads Sync Result:", res)
