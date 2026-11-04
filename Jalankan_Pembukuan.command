#!/bin/bash
cd "$(dirname "$0")"

clear
echo "=========================================================="
echo "   SISTEM PEMBUKUAN SHOPEE - COVER KNALPOT & BAUT"
echo "=========================================================="
echo ""
echo "Sinkronisasi otomatis dengan folder:"
echo "-> /Users/risanggalih/Downloads/penjualan"
echo ""

# Jalankan import awal
python3 importer.py

# Buka browser
sleep 1 && open "http://localhost:8000" &

# Jalankan server
python3 -m uvicorn server:app --host 127.0.0.1 --port 8000
