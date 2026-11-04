#!/bin/bash

# Arahkan direktori kerja ke folder shopee
cd "$(dirname "$0")"

echo "=========================================================="
echo "   🚀 PLATFORM PEMBUKUAN & IKLAN SHOPEE (COVER KNALPOT)"
echo "=========================================================="
echo ""

# 1. Matikan proses lama di port 8000 jika ada
OLD_PID=$(lsof -ti:8000)
if [ ! -z "$OLD_PID" ]; then
  echo "Menghentikan server sebelumnya (PID: $OLD_PID)..."
  kill -9 $OLD_PID 2>/dev/null
  sleep 1
fi

# 2. Sinkronisasi data awal
echo "1. Memeriksa file pesanan baru di ~/Downloads/penjualan/..."
python3 importer.py >/dev/null 2>&1

echo "2. Memeriksa file iklan baru di ~/Downloads/iklan/..."
python3 importer_ads.py >/dev/null 2>&1

# 3. Buka browser otomatis
BRAVE_BIN="/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
if [ -f "$BRAVE_BIN" ]; then
  echo "3. Membuka dashboard di Brave Browser (Profile: sdrisanggalih)..."
  (sleep 1 && "$BRAVE_BIN" --profile-directory="Profile 9" "http://localhost:8000" >/dev/null 2>&1 && open -a "Brave Browser") &
else
  echo "3. Membuka dashboard di browser default (http://localhost:8000)..."
  (sleep 1 && open "http://localhost:8000") &
fi

# 4. Jalankan server FastAPI / Uvicorn
echo "4. Server aktif di http://127.0.0.1:8000"
echo "   [Tekan CTRL + C di terminal ini untuk berhenti]"
echo ""
python3 -m uvicorn server:app --host 127.0.0.1 --port 8000
