# 📈 Resume Saham

Aplikasi sederhana untuk meringkas satu saham dan membandingkannya dengan saham sejenis:

| Bagian | Isi |
|---|---|
| **Fundamental** | ROE, ROA, margin laba bersih, pertumbuhan pendapatan & laba, DER, current ratio (DER & current ratio otomatis diabaikan untuk bank) |
| **Valuasi** | PER, PBV |
| **Dividen** | Dividend yield 12 bulan, dividen per saham, payout ratio, konsistensi 5 tahun, CAGR dividen, grafik dividen per tahun |
| **Tren** | Tahunan (return 1/3 tahun, YTD, posisi vs MA200, rentang 52 minggu) dan bulanan (return 1/3/6 bulan, MA20 vs MA50, RSI 14), grafik candlestick + MA, return per tahun & per bulan |
| **Rekomendasi** | Skor 0–100 → **BELI** (≥65), **TAHAN** (45–64), **JUAL** (<45), lengkap dengan daftar kekuatan & hal yang perlu diperhatikan |
| **Perbandingan** | Tabel peer, "alternatif yang lebih baik", juara per kategori, grafik kinerja relatif 1 tahun |

## Cara menjalankan

1. Pasang Python 3.10 atau lebih baru (python.org).
2. Buka Terminal / Command Prompt di folder ini, lalu jalankan:
   ```
   pip install -r requirements.txt
   streamlit run app.py
   ```
3. Browser akan terbuka otomatis di `http://localhost:8501`.
4. Ketik kode saham (mis. `BBCA`, `TLKM`, `ASII`), lalu klik **Analisis**.
   Untuk saham luar negeri (mis. `AAPL`), hilangkan centang "Saham BEI".

## Cara skor dihitung

Skor total = Fundamental 35% + Valuasi 20% + Dividen 15% + Tren 30%.
Setiap rasio diubah menjadi skor 0–100 secara linier terhadap patokan umum (mis. ROE 5% → 0, ROE 20% → 100).
Patokan dan bobot bisa diubah di fungsi `analyze()` dalam `app.py`. Kelompok saham pembanding bisa diubah di `PEER_GROUPS`.

## Catatan penting

- Data diambil dari Yahoo Finance (gratis, tertunda ±15 menit). Untuk saham BEI, beberapa rasio kadang kosong atau terlambat diperbarui. Cek ulang dengan laporan keuangan resmi di idx.co.id.
- Data disimpan sementara 1 jam agar aplikasi cepat dan tidak membebani Yahoo.
- Rekomendasi dihasilkan otomatis dari aturan sederhana dan **bukan nasihat investasi**.
