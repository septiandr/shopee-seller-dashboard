# shopee-seller-dashboard

Platform Pembukuan Shopee & Pelacakan Iklan ROAS (Cover Knalpot)

Sistem otomasi pembukuan dan pelacakan laba/rugi toko Shopee terintegrasi dengan **Potongan Biaya Resmi Shopee** dan **Modal HPP Barang**.

---

### 🚀 Cara Menjalankan Aplikasi
1. **Cara Termudah (Klik 2x):**
   - Double-click file **`Jalankan_Pembukuan.command`** di folder ini.
   - Browser akan otomatis terbuka di **`http://localhost:8000`**.
2. **Atau Melalui Terminal:**
   ```bash
   cd ~/Desktop/shopee
   ./start.sh
   ```

---

### 💸 Struktur Lengkap Potongan Shopee yang Dihitung
Sistem menghitung seluruh komponen potongan Shopee secara otomatis sesuai rincian transaksi:

| Komponen Biaya Shopee | Tarif / Formula | Keterangan |
| :--- | :--- | :--- |
| **Biaya Administrasi** | `8.25%` × Subtotal | Biaya admin kategori produk |
| **Biaya Proses Pesanan** | `Rp 1.250` (flat) | Biaya penanganan per pesanan |
| **Biaya Gratis Ongkir XTRA** | `5.50%` × Subtotal | Program Gratis Ongkir XTRA Kategori G |
| **Biaya Promosi / Saldo Otomatis** | `3.33%` × Subtotal | Top up saldo promosi/iklan otomatis |
| **Pajak PPh 22** | `0.50%` × Subtotal | Pajak PPh Pasal 22 |
| **TOTAL POTONGAN SHOPEE** | **`17.58%` + Rp 1.250** | Dipotong langsung dari Subtotal |

---

### 📦 Logika Modal HPP & Laba Bersih Real

1. **Modal Beli Produk:**
   - **Cover Knalpot**: `Rp 6.000` / pcs
   - **Baut**: `Rp 2.000` / pasang (otomatis `Rp 0` untuk variasi *Tanpa Baut*)

2. **Perhitungan Finansial Bersih:**
   $$\text{Estimasi Cair dari Shopee} = \text{Subtotal Pesanan} - \text{Total Potongan Shopee}$$
   $$\text{Laba Bersih Real (Masuk Kantong)} = \text{Estimasi Cair dari Shopee} - \text{Total Modal HPP}$$

---

### 🔄 Alur Sinkronisasi Harian
- Cukup download file laporan Shopee (`Order.all.*.xlsx`) ke folder `~/Downloads/penjualan/`.
- Klik tombol **"⚡ Sinkronkan Folder"** di dashboard (atau upload langsung via drag & drop).
- Sistem otomatis menghitung potongan Shopee, HPP barang, laba bersih, dan memperbarui status pesanan lama tanpa membuat data ganda.
