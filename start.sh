#!/bin/bash
cd "$(dirname "$0")"

echo "=========================================================="
echo "   SISTEM PEMBUKUAN SHOPEE - COVER KNALPOT & BAUT"
echo "=========================================================="
echo ""
echo "Memeriksa folder penjualan & memperbarui data..."
python3 importer.py

echo "Membuka browser ke http://localhost:8000 ..."
sleep 1 && open "http://localhost:8000" &

echo "Menjalankan Web Server Pembukuan..."
python3 -m uvicorn server:app --host 127.0.0.1 --port 8000
