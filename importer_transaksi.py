import os
import glob
import datetime
from pathlib import Path
import openpyxl

from importer import get_db, load_config, DB_FILE

def init_transactions_table():
    with get_db() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS balance_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tx_date TEXT NOT NULL,
            tx_type TEXT,
            description TEXT NOT NULL,
            order_no TEXT,
            direction TEXT,
            amount REAL NOT NULL,
            status TEXT,
            final_balance REAL,
            source_file TEXT,
            imported_at TEXT,
            UNIQUE(tx_date, description, amount)
        )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_bt_tx_date ON balance_transactions(tx_date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_bt_order_no ON balance_transactions(order_no)")

        conn.execute("""
        CREATE TABLE IF NOT EXISTS balance_import_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT UNIQUE,
            file_path TEXT,
            file_size INTEGER,
            file_mtime REAL,
            imported_at TEXT,
            total_rows INTEGER,
            inserted_rows INTEGER
        )
        """)

        # Add actual_settlement column to orders if not exists
        order_cols = [c[1] for c in conn.execute("PRAGMA table_info(orders)").fetchall()]
        if "actual_settlement" not in order_cols:
            try:
                conn.execute("ALTER TABLE orders ADD COLUMN actual_settlement REAL DEFAULT NULL")
            except Exception:
                pass
        if "settlement_date" not in order_cols:
            try:
                conn.execute("ALTER TABLE orders ADD COLUMN settlement_date TEXT DEFAULT NULL")
            except Exception:
                pass

def import_balance_report_file(file_path):
    """
    Import file Laporan Saldo / Transaksi Shopee (my_balance_transaction_report.shopee.*.xlsx):
    1. Menyimpan seluruh riwayat mutasi saldo ke tabel balance_transactions.
    2. Mendeteksi pengeluaran 'Isi Ulang Saldo Iklan/Koin Penjual' dan otomatis mencatatkannya ke tabel expenses (Iklan / Ads).
    3. Mengaitkan pencairan dana pesanan ('Penghasilan dari Pesanan') ke tabel orders sebagai actual_settlement.
    """
    init_transactions_table()
    p = Path(file_path)
    if not p.exists():
        return {"status": "error", "message": f"File {file_path} tidak ditemukan"}

    wb = openpyxl.load_workbook(str(p), data_only=True)
    ws = wb.active

    # Cari header baris tabel transaksi
    header_row = None
    header_map = {}
    for r in range(1, min(25, ws.max_row + 1)):
        row_vals = [str(ws.cell(r, c).value or "").strip() for c in range(1, ws.max_column + 1)]
        if "Tanggal Transaksi" in row_vals and "Jumlah" in row_vals:
            header_row = r
            header_map = {val: idx + 1 for idx, val in enumerate(row_vals) if val}
            break

    if not header_row:
        return {"status": "error", "message": "Header tabel transaksi tidak ditemukan di template laporan saldo"}

    def get_val(r, col_name):
        c_idx = header_map.get(col_name)
        if not c_idx:
            return None
        v = ws.cell(r, c_idx).value
        return v

    total_rows = 0
    inserted_tx = 0
    expenses_added = 0
    settlements_linked = 0
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with get_db() as conn:
        for r in range(header_row + 1, ws.max_row + 1):
            raw_date = get_val(r, "Tanggal Transaksi")
            if not raw_date:
                continue

            tx_date = str(raw_date).strip()
            tx_type = str(get_val(r, "Tipe Transaksi") or "").strip()
            description = str(get_val(r, "Deskripsi") or "").strip()
            order_no = str(get_val(r, "No. Pesanan") or "").strip()
            direction = str(get_val(r, "Jenis Transaksi") or "").strip()
            raw_amount = get_val(r, "Jumlah")
            status = str(get_val(r, "Status") or "").strip()
            raw_balance = get_val(r, "Saldo Akhir")

            try:
                amount = float(str(raw_amount).replace(",", "")) if raw_amount is not None else 0.0
            except Exception:
                amount = 0.0

            try:
                final_balance = float(str(raw_balance).replace(",", "")) if raw_balance is not None else 0.0
            except Exception:
                final_balance = 0.0

            total_rows += 1

            # 1. Masukkan ke balance_transactions (idempotent via UNIQUE)
            try:
                conn.execute("""
                INSERT OR IGNORE INTO balance_transactions (
                    tx_date, tx_type, description, order_no, direction, amount, status, final_balance, source_file, imported_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (tx_date, tx_type, description, order_no if order_no != "-" else None, direction, amount, status, final_balance, p.name, now_str))
                inserted_tx += 1
            except Exception as e:
                pass

            # 2. Otomatis catat ke Biaya Operasional (Expenses) jika merupakan Isi Ulang Iklan
            is_ads_topup = ("iklan" in description.lower() or "iklan" in tx_type.lower()) and amount < 0
            if is_ads_topup:
                exp_date = tx_date[:10]  # Format YYYY-MM-DD
                exp_amt = abs(amount)
                exp_title = "Isi Ulang Saldo Iklan Shopee (Saldo Penjual)"
                exp_notes = f"Dipotong otomatis dari Saldo Penjual Shopee (Waktu: {tx_date})"
                
                # Cek apakah expense ini sudah tercatat sebelumnya
                cur = conn.execute(
                    "SELECT id FROM expenses WHERE expense_date = ? AND amount = ? AND category = 'Iklan / Ads'",
                    (exp_date, exp_amt)
                )
                if not cur.fetchone():
                    conn.execute("""
                    INSERT INTO expenses (expense_date, category, title, amount, notes, created_at, updated_at)
                    VALUES (?, 'Iklan / Ads', ?, ?, ?, ?, ?)
                    """, (exp_date, exp_title, exp_amt, exp_notes, now_str, now_str))
                    expenses_added += 1

            # 3. Kaitkan actual settlement dengan order jika ada No. Pesanan
            if order_no and order_no != "-" and amount > 0:
                cur = conn.execute("SELECT id FROM orders WHERE order_no = ?", (order_no,))
                if cur.fetchone():
                    conn.execute("""
                    UPDATE orders SET
                        actual_settlement = ?,
                        settlement_date = ?
                    WHERE order_no = ?
                    """, (amount, tx_date, order_no))
                    settlements_linked += 1

        # Catat log import
        stat = p.stat()
        conn.execute("""
        INSERT OR REPLACE INTO balance_import_logs (
            file_name, file_path, file_size, file_mtime, imported_at, total_rows, inserted_rows
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (p.name, str(p.resolve()), stat.st_size, stat.st_mtime, now_str, total_rows, inserted_tx))

    return {
        "status": "success",
        "file": p.name,
        "total_rows": total_rows,
        "inserted_transactions": inserted_tx,
        "expenses_added": expenses_added,
        "settlements_linked": settlements_linked
    }

def sync_transaksi_watch_folders(force=False):
    """
    Sinkronisasi file laporan mutasi saldo dari folder ./transaksi atau folder konfigurasi
    """
    init_transactions_table()
    base_dir = Path(__file__).parent
    candidate_folders = [
        base_dir / "transaksi",
        Path.home() / "Downloads" / "transaksi",
        Path.home() / "Downloads"
    ]

    files_to_process = []
    seen = set()

    for folder in candidate_folders:
        if folder.exists() and folder.is_dir():
            for f in folder.glob("*balance_transaction_report*.xlsx"):
                if f.name not in seen:
                    seen.add(f.name)
                    files_to_process.append(f)

    files_to_process.sort(key=os.path.getmtime)
    results = []
    for f in files_to_process:
        res = import_balance_report_file(f)
        results.append(res)

    return {"status": "success", "processed": results, "total_files": len(files_to_process)}

if __name__ == "__main__":
    res = sync_transaksi_watch_folders(force=True)
    print("Hasil sinkronisasi transaksi:", res)
