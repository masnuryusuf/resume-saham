# Resume Saham

Aplikasi sederhana untuk belajar menganalisis saham. Untuk setiap kode saham, aplikasi membuat laporan HTML yang berisi:

1. **Fundamental**: EPS, PER, PBV, ROE, NPM, DER, pertumbuhan laba dan pendapatan, serta current ratio.
2. **Dividen**: dividend yield 12 bulan, yield rata-rata 5 tahun, payout ratio, dan konsistensi pembagian dividen.
3. **Tren**: MA20, MA50, MA200, RSI, golden/death cross, return 1/3/6 bulan, 1 tahun, YTD, return bulanan (12 bulan), dan return tahunan (5 tahun).
4. **Rekomendasi BELI / TAHAN / JUAL** dari skor 0–100, beserta alasannya (✓ / ✕).
5. **Pembanding sejenis**: saham satu sektor diberi tanda **★ lebih baik** jika skornya lebih tinggi.

Setiap angka punya penjelasan singkat di sebelahnya (misalnya "murah", "sehat", atau "overbought"). Setiap istilah juga diberi nomor catatan kaki yang mengarah ke kamus istilah di bagian bawah laporan.

---

## 1. Pemasangan (sekali saja, di Mac)

Buka **Terminal**, lalu jalankan:

```bash
python3 --version          # kalau belum ada, Mac akan menawarkan untuk memasangnya
pip3 install yfinance pandas
```

Simpan `resume_saham.py` dan `README.md` dalam satu folder, misalnya `~/Documents/resume-saham`.

## 2. Menjalankan

```bash
cd ~/Documents/resume-saham

python3 resume_saham.py BBCA TLKM ADRO     # analisis saham tertentu
python3 resume_saham.py                    # pakai daftar di watchlist.txt
python3 resume_saham.py --demo             # coba tanpa internet (data karangan)
```

* Kode saham Indonesia cukup ditulis `BBCA` karena akhiran `.JK` ditambahkan otomatis.
* Untuk saham AS, beri titik di depan kodenya: `.AAPL`, `.MSFT`.
* Laporan langsung terbuka di browser dan tersimpan di folder `hasil/`.

### Opsi yang berguna

| Opsi | Fungsi |
|---|---|
| `--pembanding BBRI,BMRI` | Memilih sendiri saham pembanding |
| `--tanpa-pembanding` | Melewati perbandingan agar lebih cepat |
| `--bandingkan 2026-10-01` | Membandingkan dengan resume pada tanggal tertentu |
| `--jangan-buka` | Tidak membuka browser otomatis |

## 3. Cara UPDATE dari resume sebelumnya

Cukup **jalankan perintah yang sama lagi** (misalnya seminggu sekali):

```bash
python3 resume_saham.py
```

Setiap kali dijalankan, aplikasi melakukan hal berikut:

1. Mengambil data terbaru.
2. Mencari snapshot terakhir di `hasil/` (`snapshot_YYYY-MM-DD.json`) yang tanggalnya lebih awal dari hari ini.
3. Menampilkan perubahannya di laporan:
   * Kolom **Perubahan** di tabel ringkasan, misalnya `+19,7% · skor +19 · TAHAN→BELI`.
   * Kotak **"Sejak resume sebelumnya"** di setiap kartu saham.
4. Menyimpan snapshot baru dan menambah baris di `hasil/riwayat.csv`.

Isi folder `hasil/`:

| File | Isi |
|---|---|
| `resume_YYYY-MM-DD.html` | Laporan per tanggal (arsip) |
| `resume_terbaru.html` | Laporan terakhir (selalu ditimpa) |
| `snapshot_YYYY-MM-DD.json` | Data ringkas untuk perbandingan |
| `riwayat.csv` | Sejarah harga, skor, dan rekomendasi. Bisa dibuka di Numbers atau Excel untuk melihat perkembangan dari waktu ke waktu |

Jika Anda menjalankannya beberapa kali di hari yang sama, hasil hari itu ditimpa dan tidak tercatat dobel.

Untuk membandingkan dengan tanggal tertentu, bukan yang terakhir:

```bash
python3 resume_saham.py --bandingkan 2026-09-01
```

### (Opsional) Update otomatis setiap Senin pukul 08.00

```bash
crontab -e
```

Tambahkan baris berikut (ganti path sesuai folder Anda):

```
0 8 * * 1 cd ~/Documents/resume-saham && /usr/bin/python3 resume_saham.py --jangan-buka
```

## 4. Melihat di iPad

Laporan berupa satu file HTML tanpa internet atau library luar. Simpan folder aplikasi di **iCloud Drive**, lalu buka `hasil/resume_terbaru.html` dari aplikasi **Files** di iPad. Ketuk grafik harga untuk melihat nilai harga dan MA pada tanggal tersebut. Script tetap dijalankan dari Mac.

## 5. Menyesuaikan

Bagian-bagian ini ada di dalam `resume_saham.py`:

* **`watchlist.txt`**: daftar saham yang dipantau, satu kode per baris.
* **`KELOMPOK`**: grup saham sejenis untuk pembanding. Tambah sektor atau kode sesuai kebutuhan.
* **`beri_skor()`**: semua aturan skor. Misalnya, jika menurut Anda PER ≤ 15 sudah murah, ubah batasnya di sini.
* **`ISTILAH`**: isi kamus istilah dan catatan kaki.

### Cara skor dihitung

| Bagian | Bobot | Dasar penilaian |
|---|---|---|
| Fundamental | 50% | ROE, NPM, DER (tidak dinilai untuk bank), PER, PBV, pertumbuhan laba |
| Dividen | 20% | Dividend yield × faktor konsistensi 5 tahun, dikurangi jika payout > 100% |
| Tren | 30% | Posisi harga terhadap MA20/50/200, MA50 vs MA200, RSI, return 1 tahun |

Rekomendasi: **BELI** jika total ≥ 65, **TAHAN** jika 45–64, **JUAL** jika < 45.

## 6. Catatan penting

* Data berasal dari Yahoo Finance (gratis dan tidak resmi). Untuk saham Indonesia, beberapa angka fundamental kadang kosong atau terlambat. Cek silang dengan laporan keuangan di idx.co.id.
* Dividend yield dihitung dari riwayat dividen yang benar-benar dibayar, sehingga lebih bisa diandalkan daripada angka yield bawaan.
* Rekomendasi berasal dari aturan sederhana untuk belajar, **bukan nasihat investasi**.
