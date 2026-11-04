import os
import glob
import json
import sqlite3
import datetime
from pathlib import Path
import openpyxl

CONFIG_FILE = Path(__file__).parent / "config.json"
DB_FILE = Path(__file__).parent / "shopee_ledger.db"

def load_config():
    default_cfg = {
        "hpp_cover": 6000,
        "hpp_bolt": 2000,
        "extra_bubble_cost": 0,
        "shopee_admin_fee_pct": 8.25,
        "shopee_process_fee_flat": 1250,
        "shopee_gratis_ongkir_xtra_pct": 5.5,
        "shopee_promo_auto_topup_pct": 3.33,
        "shopee_pph22_pct": 0.5,
        "watch_folder": "/Users/risanggalih/Downloads/penjualan",
        "port": 8000
    }
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                default_cfg.update(cfg)
                return default_cfg
        except Exception:
            pass
    return default_cfg

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

def get_db():
    conn = sqlite3.connect(str(DB_FILE))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_no TEXT NOT NULL,
            order_status TEXT,
            tracking_no TEXT,
            shipping_option TEXT,
            payment_method TEXT,
            order_created_at TEXT,
            order_paid_at TEXT,
            order_completed_at TEXT,
            product_name TEXT,
            variation_name TEXT,
            model_type TEXT,
            has_bolt INTEGER DEFAULT 0,
            pack_type TEXT,
            qty INTEGER DEFAULT 1,
            price_unit REAL DEFAULT 0,
            subtotal REAL DEFAULT 0,
            seller_discount REAL DEFAULT 0,
            seller_voucher REAL DEFAULT 0,
            shopee_voucher REAL DEFAULT 0,
            total_payment REAL DEFAULT 0,
            net_revenue REAL DEFAULT 0,
            shopee_admin_fee REAL DEFAULT 0,
            shopee_process_fee REAL DEFAULT 0,
            shopee_gratis_ongkir_xtra REAL DEFAULT 0,
            shopee_promo_fee REAL DEFAULT 0,
            shopee_pph22 REAL DEFAULT 0,
            total_shopee_deductions REAL DEFAULT 0,
            net_payout REAL DEFAULT 0,
            hpp_cover_unit REAL DEFAULT 6000,
            hpp_bolt_unit REAL DEFAULT 0,
            total_hpp_cover REAL DEFAULT 0,
            total_hpp_bolt REAL DEFAULT 0,
            total_hpp REAL DEFAULT 0,
            profit REAL DEFAULT 0,
            margin_pct REAL DEFAULT 0,
            buyer_username TEXT,
            recipient_name TEXT,
            city TEXT,
            province TEXT,
            raw_address TEXT,
            source_file TEXT,
            imported_at TEXT,
            UNIQUE(order_no, product_name, variation_name)
        )
        """)
        
        # Verify / Add new columns
        cols = [c[1] for c in conn.execute("PRAGMA table_info(orders)").fetchall()]
        new_cols = [
            ("shopee_admin_fee", "REAL DEFAULT 0"),
            ("shopee_process_fee", "REAL DEFAULT 0"),
            ("shopee_gratis_ongkir_xtra", "REAL DEFAULT 0"),
            ("shopee_promo_fee", "REAL DEFAULT 0"),
            ("shopee_pph22", "REAL DEFAULT 0"),
            ("total_shopee_deductions", "REAL DEFAULT 0"),
            ("net_payout", "REAL DEFAULT 0")
        ]
        for col_name, col_type in new_cols:
            if col_name not in cols:
                conn.execute(f"ALTER TABLE orders ADD COLUMN {col_name} {col_type}")

        conn.execute("CREATE INDEX IF NOT EXISTS idx_order_no ON orders(order_no)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_order_created_at ON orders(order_created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_order_status ON orders(order_status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_has_bolt ON orders(has_bolt)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_model_type ON orders(model_type)")

        conn.execute("""
        CREATE TABLE IF NOT EXISTS import_logs (
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

def parse_num(val):
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    val_str = str(val).strip().replace("Rp", "").replace("rp", "").replace(" ", "")
    if not val_str or val_str.lower() == "nan":
        return 0.0
    if "," in val_str and "." in val_str:
        val_str = val_str.replace(".", "").replace(",", ".")
    elif "." in val_str:
        val_str = val_str.replace(".", "")
    elif "," in val_str:
        val_str = val_str.replace(",", ".")
    try:
        return float(val_str)
    except:
        return 0.0

def calculate_shopee_deductions(subtotal, config):
    admin_pct = float(config.get("shopee_admin_fee_pct", 8.25)) / 100.0
    process_flat = float(config.get("shopee_process_fee_flat", 1250.0))
    gratis_ongkir_pct = float(config.get("shopee_gratis_ongkir_xtra_pct", 5.5)) / 100.0
    promo_pct = float(config.get("shopee_promo_auto_topup_pct", 3.33)) / 100.0
    pph22_pct = float(config.get("shopee_pph22_pct", 0.5)) / 100.0

    shopee_admin_fee = round(subtotal * admin_pct)
    shopee_process_fee = process_flat if subtotal > 0 else 0.0
    shopee_gratis_ongkir_xtra = round(subtotal * gratis_ongkir_pct)
    shopee_promo_fee = round(subtotal * promo_pct)
    shopee_pph22 = round(subtotal * pph22_pct)

    total_deductions = shopee_admin_fee + shopee_process_fee + shopee_gratis_ongkir_xtra + shopee_promo_fee + shopee_pph22
    net_payout = max(0.0, subtotal - total_deductions)

    return {
        "shopee_admin_fee": shopee_admin_fee,
        "shopee_process_fee": shopee_process_fee,
        "shopee_gratis_ongkir_xtra": shopee_gratis_ongkir_xtra,
        "shopee_promo_fee": shopee_promo_fee,
        "shopee_pph22": shopee_pph22,
        "total_shopee_deductions": total_deductions,
        "net_payout": net_payout
    }

def parse_order_row(ws, r, header_map, config, source_file=""):
    def g(col_name):
        idx = header_map.get(col_name)
        if idx:
            val = ws.cell(r, idx).value
            return str(val).strip() if val is not None else ""
        return ""

    order_no = g("No. Pesanan")
    if not order_no or order_no.lower() == "nan":
        return None

    status = g("Status Pesanan")
    tracking_no = g("No. Resi")
    shipping_option = g("Opsi Pengiriman")
    payment_method = g("Metode Pembayaran")
    order_created_at = g("Waktu Pesanan Dibuat")
    order_paid_at = g("Waktu Pembayaran Dilakukan")
    order_completed_at = g("Waktu Pesanan Selesai")
    
    product_name = g("Nama Produk")
    variation_name = g("Nama Variasi")
    var_lower = variation_name.lower()

    # Determine Bolt Variant
    has_bolt = 0
    if "tanpa baut" in var_lower or "no baut" in var_lower or "non baut" in var_lower:
        has_bolt = 0
    elif "+ baut" in var_lower or "+baut" in var_lower or "plus baut" in var_lower or "dengan baut" in var_lower or "baut" in var_lower:
        has_bolt = 1

    # Determine Model
    model_type = "Lainnya"
    if "old" in var_lower:
        model_type = "Model Old"
    elif "new" in var_lower:
        model_type = "Model New"

    # Determine Packaging
    pack_type = "Biasa"
    if "bubble" in var_lower:
        pack_type = "Extra Bubble"

    qty = int(parse_num(g("Jumlah")))
    if qty <= 0:
        qty = 1
        
    price_unit = parse_num(g("Harga Setelah Diskon"))
    if price_unit <= 0:
        price_unit = parse_num(g("Harga Awal"))

    subtotal = parse_num(g("Subtotal Pesanan"))
    if subtotal <= 0:
        subtotal = price_unit * qty

    seller_discount = parse_num(g("Diskon Dari Penjual"))
    seller_voucher = parse_num(g("Voucher Ditanggung Penjual"))
    shopee_voucher = parse_num(g("Voucher Ditanggung Shopee"))
    total_payment = parse_num(g("Total Pembayaran"))

    net_revenue = subtotal - seller_discount - seller_voucher
    if net_revenue <= 0:
        net_revenue = subtotal

    hpp_cover_unit = float(config.get("hpp_cover", 6000))
    hpp_bolt_unit = float(config.get("hpp_bolt", 2000)) if has_bolt else 0.0
    extra_bubble_cost = float(config.get("extra_bubble_cost", 0)) if pack_type == "Extra Bubble" else 0.0

    total_hpp_cover = hpp_cover_unit * qty
    total_hpp_bolt = hpp_bolt_unit * qty
    total_hpp = total_hpp_cover + total_hpp_bolt + (extra_bubble_cost * qty)

    deductions = calculate_shopee_deductions(subtotal, config)
    total_shopee_deductions = deductions["total_shopee_deductions"]
    net_payout = deductions["net_payout"]

    profit = net_payout - total_hpp
    margin_pct = (profit / subtotal * 100.0) if subtotal > 0 else 0.0

    buyer_username = g("Username (Pembeli)")
    recipient_name = g("Nama Penerima")
    city = g("Kota/Kabupaten")
    province = g("Provinsi")
    raw_address = g("Alamat Pengiriman")

    imported_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return {
        "order_no": order_no,
        "order_status": status,
        "tracking_no": tracking_no,
        "shipping_option": shipping_option,
        "payment_method": payment_method,
        "order_created_at": order_created_at,
        "order_paid_at": order_paid_at,
        "order_completed_at": order_completed_at,
        "product_name": product_name,
        "variation_name": variation_name,
        "model_type": model_type,
        "has_bolt": has_bolt,
        "pack_type": pack_type,
        "qty": qty,
        "price_unit": price_unit,
        "subtotal": subtotal,
        "seller_discount": seller_discount,
        "seller_voucher": seller_voucher,
        "shopee_voucher": shopee_voucher,
        "total_payment": total_payment,
        "net_revenue": net_revenue,
        "shopee_admin_fee": deductions["shopee_admin_fee"],
        "shopee_process_fee": deductions["shopee_process_fee"],
        "shopee_gratis_ongkir_xtra": deductions["shopee_gratis_ongkir_xtra"],
        "shopee_promo_fee": deductions["shopee_promo_fee"],
        "shopee_pph22": deductions["shopee_pph22"],
        "total_shopee_deductions": total_shopee_deductions,
        "net_payout": net_payout,
        "hpp_cover_unit": hpp_cover_unit,
        "hpp_bolt_unit": hpp_bolt_unit,
        "total_hpp_cover": total_hpp_cover,
        "total_hpp_bolt": total_hpp_bolt,
        "total_hpp": total_hpp,
        "profit": profit,
        "margin_pct": margin_pct,
        "buyer_username": buyer_username,
        "recipient_name": recipient_name,
        "city": city,
        "province": province,
        "raw_address": raw_address,
        "source_file": source_file,
        "imported_at": imported_at
    }

def import_excel_file(file_path):
    """
    Import file Excel Shopee dengan aturan:
    1. MENAMBAH: Pesanan baru yang belum ada di database akan ditambahkan (INSERT).
    2. MEMPERBARUI DENGAN DATA BARU: Jika nomor pesanan & variasi (atau tanggal) sudah ada di database,
       seluruh informasi (status, resi, waktu bayar/selesai, potongan, dll) akan DIPERBARUI (UPDATE)
       menggunakan data terbaru dari file baru ini.
    3. DATA LAMA TIDAK PERNAH DIHAPUS: Pesanan dari tanggal-tanggal sebelumnya tetap tersimpan aman.
    """
    init_db()
    config = load_config()
    p = Path(file_path)
    if not p.exists():
        return {"status": "error", "message": f"File {file_path} tidak ditemukan"}

    wb = openpyxl.load_workbook(str(p), data_only=True)
    ws = wb.active

    headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
    header_map = {str(h).strip(): i+1 for i, h in enumerate(headers) if h}

    if "No. Pesanan" not in header_map:
        return {"status": "error", "message": "Kolom 'No. Pesanan' tidak ditemukan di template Excel"}

    inserted = 0
    updated = 0
    total = 0

    with get_db() as conn:
        for r in range(2, ws.max_row + 1):
            row_data = parse_order_row(ws, r, header_map, config, source_file=p.name)
            if not row_data:
                continue
            total += 1

            # Cari apakah pesanan ini sudah ada sebelumnya
            cur = conn.execute(
                "SELECT id FROM orders WHERE order_no = ? AND product_name = ? AND variation_name = ?",
                (row_data["order_no"], row_data["product_name"], row_data["variation_name"])
            )
            existing = cur.fetchone()

            if existing:
                # DATA YANG SAMA: Gunakan data baru dari file ini untuk meng-update
                conn.execute("""
                UPDATE orders SET
                    order_status = ?,
                    tracking_no = ?,
                    shipping_option = ?,
                    payment_method = ?,
                    order_created_at = ?,
                    order_paid_at = ?,
                    order_completed_at = ?,
                    qty = ?,
                    price_unit = ?,
                    subtotal = ?,
                    seller_discount = ?,
                    seller_voucher = ?,
                    shopee_voucher = ?,
                    total_payment = ?,
                    net_revenue = ?,
                    shopee_admin_fee = ?,
                    shopee_process_fee = ?,
                    shopee_gratis_ongkir_xtra = ?,
                    shopee_promo_fee = ?,
                    shopee_pph22 = ?,
                    total_shopee_deductions = ?,
                    net_payout = ?,
                    hpp_cover_unit = ?,
                    hpp_bolt_unit = ?,
                    total_hpp_cover = ?,
                    total_hpp_bolt = ?,
                    total_hpp = ?,
                    profit = ?,
                    margin_pct = ?,
                    city = ?,
                    province = ?,
                    raw_address = ?,
                    source_file = ?,
                    imported_at = ?
                WHERE id = ?
                """, (
                    row_data["order_status"],
                    row_data["tracking_no"],
                    row_data["shipping_option"],
                    row_data["payment_method"],
                    row_data["order_created_at"],
                    row_data["order_paid_at"],
                    row_data["order_completed_at"],
                    row_data["qty"],
                    row_data["price_unit"],
                    row_data["subtotal"],
                    row_data["seller_discount"],
                    row_data["seller_voucher"],
                    row_data["shopee_voucher"],
                    row_data["total_payment"],
                    row_data["net_revenue"],
                    row_data["shopee_admin_fee"],
                    row_data["shopee_process_fee"],
                    row_data["shopee_gratis_ongkir_xtra"],
                    row_data["shopee_promo_fee"],
                    row_data["shopee_pph22"],
                    row_data["total_shopee_deductions"],
                    row_data["net_payout"],
                    row_data["hpp_cover_unit"],
                    row_data["hpp_bolt_unit"],
                    row_data["total_hpp_cover"],
                    row_data["total_hpp_bolt"],
                    row_data["total_hpp"],
                    row_data["profit"],
                    row_data["margin_pct"],
                    row_data["city"],
                    row_data["province"],
                    row_data["raw_address"],
                    row_data["source_file"],
                    row_data["imported_at"],
                    existing["id"]
                ))
                updated += 1
            else:
                # DATA BARU: Tambahkan ke database (menambah akumulasi data)
                conn.execute("""
                INSERT INTO orders (
                    order_no, order_status, tracking_no, shipping_option, payment_method,
                    order_created_at, order_paid_at, order_completed_at, product_name,
                    variation_name, model_type, has_bolt, pack_type, qty, price_unit,
                    subtotal, seller_discount, seller_voucher, shopee_voucher, total_payment,
                    net_revenue, shopee_admin_fee, shopee_process_fee, shopee_gratis_ongkir_xtra,
                    shopee_promo_fee, shopee_pph22, total_shopee_deductions, net_payout,
                    hpp_cover_unit, hpp_bolt_unit, total_hpp_cover, total_hpp_bolt,
                    total_hpp, profit, margin_pct, buyer_username, recipient_name, city,
                    province, raw_address, source_file, imported_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """, (
                    row_data["order_no"], row_data["order_status"], row_data["tracking_no"],
                    row_data["shipping_option"], row_data["payment_method"], row_data["order_created_at"],
                    row_data["order_paid_at"], row_data["order_completed_at"], row_data["product_name"],
                    row_data["variation_name"], row_data["model_type"], row_data["has_bolt"],
                    row_data["pack_type"], row_data["qty"], row_data["price_unit"], row_data["subtotal"],
                    row_data["seller_discount"], row_data["seller_voucher"], row_data["shopee_voucher"],
                    row_data["total_payment"], row_data["net_revenue"],
                    row_data["shopee_admin_fee"], row_data["shopee_process_fee"],
                    row_data["shopee_gratis_ongkir_xtra"], row_data["shopee_promo_fee"],
                    row_data["shopee_pph22"], row_data["total_shopee_deductions"], row_data["net_payout"],
                    row_data["hpp_cover_unit"], row_data["hpp_bolt_unit"], row_data["total_hpp_cover"],
                    row_data["total_hpp_bolt"], row_data["total_hpp"], row_data["profit"], row_data["margin_pct"],
                    row_data["buyer_username"], row_data["recipient_name"], row_data["city"],
                    row_data["province"], row_data["raw_address"], row_data["source_file"],
                    row_data["imported_at"]
                ))
                inserted += 1

        file_stat = p.stat()
        conn.execute("""
        INSERT OR REPLACE INTO import_logs (
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
        "total_rows": total,
        "inserted": inserted,
        "updated": updated
    }

def sync_watch_folder(force=False):
    """
    Sinkronisasi seluruh file Excel di folder penjualan.
    - File diproses berurutan dari yang terlama ke yang terbaru.
    - Jika ada file baru: menambah data baru ke database.
    - Jika ada pesanan dengan nomor/tanggal yang sama di file yang lebih baru: otomatis memakai data terbaru.
    - Data dari file-file sebelumnya tetap dipertahankan.
    """
    config = load_config()
    watch_folder = config.get("watch_folder", "/Users/risanggalih/Downloads/penjualan")
    p = Path(watch_folder)
    if not p.exists() or not p.is_dir():
        return {"status": "error", "message": f"Folder {watch_folder} tidak ditemukan"}

    # Sort files chronologically so latest file takes precedence
    excel_files = sorted(list(p.glob("*.xlsx")) + list(p.glob("*.xls")), key=os.path.getmtime)
    if not excel_files:
        return {"status": "info", "message": "Tidak ada file Excel di folder penjualan"}

    results = []
    for f in excel_files:
        if not force:
            with get_db() as conn:
                cur = conn.execute("SELECT file_mtime, file_size FROM import_logs WHERE file_name = ?", (f.name,))
                log = cur.fetchone()
                stat = f.stat()
                if log and log["file_mtime"] == stat.st_mtime and log["file_size"] == stat.st_size:
                    continue
        res = import_excel_file(f)
        results.append(res)

    return {"status": "success", "processed": results, "total_files": len(excel_files)}

def recalculate_all_orders():
    init_db()
    config = load_config()
    hpp_cover_unit = float(config.get("hpp_cover", 6000))
    hpp_bolt_unit_default = float(config.get("hpp_bolt", 2000))
    extra_bubble_cost_val = float(config.get("extra_bubble_cost", 0))

    with get_db() as conn:
        rows = conn.execute("SELECT id, qty, subtotal, net_revenue, has_bolt, pack_type FROM orders").fetchall()
        for r in rows:
            qty = r["qty"]
            subtotal = r["subtotal"] if r["subtotal"] > 0 else r["net_revenue"]
            has_bolt = r["has_bolt"]
            pack_type = r["pack_type"]

            bolt_unit = hpp_bolt_unit_default if has_bolt else 0.0
            bubble_unit = extra_bubble_cost_val if pack_type == "Extra Bubble" else 0.0

            total_hpp_cover = hpp_cover_unit * qty
            total_hpp_bolt = bolt_unit * qty
            total_hpp = total_hpp_cover + total_hpp_bolt + (bubble_unit * qty)

            deductions = calculate_shopee_deductions(subtotal, config)
            total_shopee_deductions = deductions["total_shopee_deductions"]
            net_payout = deductions["net_payout"]

            profit = net_payout - total_hpp
            margin_pct = (profit / subtotal * 100.0) if subtotal > 0 else 0.0

            conn.execute("""
            UPDATE orders SET
                shopee_admin_fee = ?,
                shopee_process_fee = ?,
                shopee_gratis_ongkir_xtra = ?,
                shopee_promo_fee = ?,
                shopee_pph22 = ?,
                total_shopee_deductions = ?,
                net_payout = ?,
                hpp_cover_unit = ?,
                hpp_bolt_unit = ?,
                total_hpp_cover = ?,
                total_hpp_bolt = ?,
                total_hpp = ?,
                profit = ?,
                margin_pct = ?
            WHERE id = ?
            """, (
                deductions["shopee_admin_fee"],
                deductions["shopee_process_fee"],
                deductions["shopee_gratis_ongkir_xtra"],
                deductions["shopee_promo_fee"],
                deductions["shopee_pph22"],
                total_shopee_deductions,
                net_payout,
                hpp_cover_unit,
                bolt_unit,
                total_hpp_cover,
                total_hpp_bolt,
                total_hpp,
                profit,
                margin_pct,
                r["id"]
            ))
        conn.commit()
    return {"status": "success", "count": len(rows)}

if __name__ == "__main__":
    init_db()
    recalculate_all_orders()
    res = sync_watch_folder(force=True)
    print("Recalculate & Sync result:", res)
