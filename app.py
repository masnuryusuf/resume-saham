#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RESUME SAHAM — aplikasi sederhana untuk belajar menganalisis saham.

Apa yang dilakukan:
  1. Mengambil data harga, dividen, dan laporan keuangan ringkas dari Yahoo Finance.
  2. Menilai tiga hal: kekuatan fundamental, imbal hasil dividen, dan tren harga.
  3. Memberi rekomendasi BELI / TAHAN / JUAL (berbasis aturan sederhana, untuk belajar).
  4. Membandingkan dengan saham sejenis (satu sektor) dan menandai yang lebih baik.
  5. Menyimpan hasil (snapshot) supaya saat dijalankan lagi, terlihat apa yang berubah.

Cara pakai singkat (lihat README.md untuk lengkapnya):
  python3 resume_saham.py BBCA TLKM ADRO        # analisis saham tertentu
  python3 resume_saham.py                       # pakai daftar di watchlist.txt
  python3 resume_saham.py --demo                # coba tanpa internet (data karangan)

Kode saham Indonesia otomatis diberi akhiran .JK (BBCA -> BBCA.JK).
Saham luar negeri tulis apa adanya dengan titik di depan, mis. .AAPL -> AAPL.

PENTING: ini alat belajar, bukan nasihat investasi.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import json
import math
import random
import sys
import webbrowser
from pathlib import Path

try:
    import pandas as pd
except ImportError:  # pragma: no cover
    sys.exit("Butuh pandas. Jalankan:  pip3 install pandas yfinance")

FOLDER_APP = Path(__file__).resolve().parent
FOLDER_HASIL = FOLDER_APP / "hasil"
FILE_WATCHLIST = FOLDER_APP / "watchlist.txt"

# ---------------------------------------------------------------------------
# 1. KAMUS ISTILAH — dipakai untuk catatan kaki & penjelasan di laporan
# ---------------------------------------------------------------------------
ISTILAH = {
    "Harga": "Harga penutupan terakhir di bursa.",
    "Kapitalisasi": "Market cap = harga saham × jumlah saham beredar. Menggambarkan ukuran perusahaan.",
    "EPS": "Earning Per Share — laba bersih dibagi jumlah saham. Berapa rupiah laba yang 'dimiliki' tiap lembar saham. Makin besar & makin naik tiap tahun, makin baik.",
    "PER": "Price to Earnings Ratio — harga ÷ EPS. Berapa tahun laba yang Anda 'bayar' saat membeli. PER rendah = relatif murah, tapi bandingkan dengan saham satu sektor. PER negatif = perusahaan rugi.",
    "PBV": "Price to Book Value — harga ÷ nilai buku (ekuitas) per saham. PBV < 1 berarti harga di bawah nilai bukunya. Bank bagus wajar punya PBV tinggi karena ROE-nya tinggi.",
    "ROE": "Return on Equity — laba bersih ÷ ekuitas. Seberapa efisien perusahaan menghasilkan laba dari modal pemegang saham. >15% tergolong bagus.",
    "NPM": "Net Profit Margin — laba bersih ÷ pendapatan. Dari tiap Rp100 penjualan, berapa yang tersisa menjadi laba.",
    "DER": "Debt to Equity Ratio — total utang ÷ ekuitas. Mengukur beban utang. <1 umumnya sehat. Untuk bank/keuangan DER memang tinggi (dana nasabah dihitung utang), jadi tidak dinilai.",
    "Pertumbuhan Laba": "Perubahan laba dibanding periode yang sama tahun lalu (year-on-year).",
    "Pertumbuhan Pendapatan": "Perubahan pendapatan/penjualan dibanding periode yang sama tahun lalu.",
    "Current Ratio": "Aset lancar ÷ utang lancar. Kemampuan membayar kewajiban jangka pendek. >1 berarti aset lancar cukup menutup utang lancar.",
    "Dividend Yield": "Total dividen 12 bulan terakhir ÷ harga sekarang. 'Bunga' tahunan dari memegang saham. Bandingkan dengan bunga deposito (~4–5%).",
    "Yield Rata-rata 5 Th": "Rata-rata dividen per tahun dalam 5 tahun terakhir ÷ harga sekarang. Lebih stabil daripada yield 1 tahun.",
    "Payout Ratio": "Porsi laba yang dibagikan sebagai dividen. 30–70% wajar. >100% artinya membagi lebih dari labanya — sulit dipertahankan.",
    "Konsistensi Dividen": "Berapa tahun dari 5 tahun terakhir perusahaan membagi dividen.",
    "MA20": "Moving Average 20 hari — rata-rata harga 20 hari bursa (~1 bulan). Tren jangka pendek.",
    "MA50": "Moving Average 50 hari (~2,5 bulan). Tren jangka menengah.",
    "MA200": "Moving Average 200 hari (~1 tahun). Tren jangka panjang. Harga di atas MA200 = tren besar naik.",
    "Golden Cross": "MA50 memotong ke atas MA200 — sinyal awal tren naik jangka panjang.",
    "Death Cross": "MA50 memotong ke bawah MA200 — sinyal awal tren turun jangka panjang.",
    "RSI": "Relative Strength Index (14 hari), skala 0–100. >70 = 'overbought' (sudah naik terlalu cepat, rawan koreksi). <30 = 'oversold' (sudah turun terlalu dalam, bisa memantul).",
    "Return": "Persentase perubahan harga dalam periode tertentu (belum termasuk dividen).",
    "YTD": "Year to Date — perubahan sejak awal tahun berjalan sampai hari ini.",
    "Skor": "Nilai 0–100 hasil aturan sederhana aplikasi ini. Total = 50% fundamental + 20% dividen + 30% tren.",
    "Rekomendasi": "BELI jika skor total ≥ 65, TAHAN jika 45–64, JUAL jika < 45. Hanya untuk belajar, bukan nasihat investasi.",
}

# ---------------------------------------------------------------------------
# 2. KELOMPOK SAHAM SEJENIS (pembanding). Silakan tambah/ubah sendiri.
# ---------------------------------------------------------------------------
KELOMPOK = {
    "Bank": ["BBCA", "BBRI", "BMRI", "BBNI", "BRIS", "BBTN", "ARTO"],
    "Telekomunikasi": ["TLKM", "ISAT", "EXCL"],
    "Menara": ["TOWR", "TBIG", "MTEL"],
    "Konsumer": ["UNVR", "ICBP", "INDF", "MYOR", "KLBF", "SIDO", "CMRY"],
    "Batu Bara": ["ADRO", "PTBA", "ITMG", "HRUM", "INDY", "AADI"],
    "Logam & Tambang": ["ANTM", "INCO", "MDKA", "TINS", "NCKL"],
    "Otomotif & Alat Berat": ["ASII", "UNTR", "AUTO"],
    "Semen": ["SMGR", "INTP"],
    "Properti": ["BSDE", "CTRA", "PWON", "SMRA"],
    "Ritel": ["AMRT", "MIDI", "MAPI", "ACES"],
    "Energi & Gas": ["PGAS", "MEDC", "AKRA"],
    "Rumah Sakit": ["MIKA", "HEAL", "SILO"],
}
MAKS_PEMBANDING = 4


def normalisasi_kode(kode: str) -> str:
    kode = kode.strip().upper()
    if kode.startswith("."):
        return kode[1:]
    return kode if "." in kode else kode + ".JK"


def kode_pendek(simbol: str) -> str:
    return simbol[:-3] if simbol.endswith(".JK") else simbol


def cari_pembanding(simbol: str) -> tuple[str, list[str]]:
    pendek = kode_pendek(simbol)
    for nama, anggota in KELOMPOK.items():
        if pendek in anggota:
            lain = [normalisasi_kode(k) for k in anggota if k != pendek]
            return nama, lain[:MAKS_PEMBANDING]
    return "", []


# ---------------------------------------------------------------------------
# 3. PENGAMBILAN DATA
# ---------------------------------------------------------------------------
def ambil_data_yahoo(simbol: str) -> dict:
    try:
        import yfinance as yf
    except ImportError:
        sys.exit("Butuh yfinance. Jalankan:  pip3 install yfinance")
    t = yf.Ticker(simbol)
    hist = t.history(period="6y", auto_adjust=False)
    if hist.empty:
        raise ValueError(f"Data harga {simbol} kosong (kode salah?)")
    try:
        info = t.info or {}
    except Exception:
        info = {}
    close = hist["Close"].dropna()
    close.index = close.index.tz_localize(None)
    div = t.dividends
    if len(div):
        div.index = div.index.tz_localize(None)
    return {"simbol": simbol, "close": close, "dividen": div, "info": info}


def ambil_data_demo(simbol: str, sampai: dt.date) -> dict:
    """Data karangan yang konsisten per kode — untuk mencoba aplikasi tanpa internet."""
    rng = random.Random(sum(ord(c) * (i + 1) for i, c in enumerate(simbol)))
    akhir = pd.Timestamp(dt.date.today())
    tanggal = pd.bdate_range(end=akhir, periods=252 * 6)
    harga = rng.uniform(500, 9000)
    drift = rng.uniform(-0.0004, 0.0008)
    nilai = []
    for _ in tanggal:
        harga *= math.exp(drift + rng.gauss(0, 0.018))
        nilai.append(round(harga))
    close = pd.Series(nilai, index=tanggal, dtype=float)
    close = close[close.index <= pd.Timestamp(sampai)]
    bayar = rng.random() > 0.15
    div_idx, div_val = [], []
    if bayar:
        for th in range(sampai.year - 5, sampai.year + 1):
            d = pd.Timestamp(dt.date(th, rng.randint(4, 6), rng.randint(1, 28)))
            if d <= pd.Timestamp(sampai):
                div_idx.append(d)
                div_val.append(round(float(close.asof(d)) * rng.uniform(0.01, 0.07)))
    dividen = pd.Series(div_val, index=pd.DatetimeIndex(div_idx), dtype=float)
    grup, _ = cari_pembanding(simbol)
    eps = float(close.iloc[-1]) / rng.uniform(5, 35)
    info = {
        "longName": f"PT {kode_pendek(simbol)} Contoh Tbk (DEMO)",
        "sector": "Financial Services" if grup == "Bank" else "Demo",
        "industry": grup or "Lainnya",
        "marketCap": float(close.iloc[-1]) * rng.uniform(1e9, 1.2e11),
        "trailingEps": eps,
        "trailingPE": float(close.iloc[-1]) / eps,
        "priceToBook": rng.uniform(0.6, 5.5),
        "returnOnEquity": rng.uniform(-0.03, 0.30),
        "profitMargins": rng.uniform(-0.02, 0.35),
        "debtToEquity": rng.uniform(10, 220),
        "earningsGrowth": rng.uniform(-0.25, 0.35),
        "revenueGrowth": rng.uniform(-0.15, 0.25),
        "currentRatio": rng.uniform(0.6, 3.0),
        "payoutRatio": rng.uniform(0.2, 0.9) if bayar else 0,
    }
    return {"simbol": simbol, "close": close, "dividen": dividen, "info": info}


# ---------------------------------------------------------------------------
# 4. PERHITUNGAN
# ---------------------------------------------------------------------------
def angka(x):
    """Ubah ke float; kembalikan None jika kosong/tidak valid."""
    try:
        f = float(x)
        return None if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return None


def hitung_rsi(close: pd.Series, n: int = 14) -> float | None:
    d = close.diff().dropna()
    if len(d) < n + 1:
        return None
    naik = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    turun = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = naik.iloc[-1] / turun.iloc[-1] if turun.iloc[-1] else float("inf")
    return 100 - 100 / (1 + rs)


def ret(close: pd.Series, hari: int):
    if len(close) <= hari:
        return None
    return (close.iloc[-1] / close.iloc[-1 - hari] - 1) * 100


def analisis(data: dict) -> dict:
    close: pd.Series = data["close"]
    info = data["info"]
    div: pd.Series = data["dividen"]
    harga = float(close.iloc[-1])
    tgl_akhir = close.index[-1]

    # --- Teknikal / tren
    ma = {n: close.rolling(n).mean() for n in (20, 50, 200)}
    ma_now = {n: angka(ma[n].iloc[-1]) for n in ma}
    awal_tahun = close[close.index.year == tgl_akhir.year]
    ytd = (harga / float(close[close.index < awal_tahun.index[0]].iloc[-1]) - 1) * 100 \
        if len(close[close.index < awal_tahun.index[0]]) else None

    bulanan = close.resample("ME").last()
    ret_bulanan = (bulanan.pct_change() * 100).dropna().tail(12)
    tahunan = close.resample("YE").last()
    ret_tahunan = (tahunan.pct_change() * 100).dropna().tail(5)

    cross = None
    selisih = (ma[50] - ma[200]).dropna().tail(60)
    if len(selisih) > 1:
        tanda = (selisih > 0).astype(int).diff().fillna(0)
        if (tanda > 0).any():
            cross = ("Golden Cross", tanda[tanda > 0].index[-1])
        elif (tanda < 0).any():
            cross = ("Death Cross", tanda[tanda < 0].index[-1])

    m20, m50, m200 = ma_now[20], ma_now[50], ma_now[200]
    if m50 and m200 and harga > m50 > m200:
        tren = "Naik kuat"
    elif m50 and m200 and harga < m50 < m200:
        tren = "Turun kuat"
    elif m200 and harga > m200:
        tren = "Naik (koreksi jangka pendek)" if m50 and harga < m50 else "Naik"
    elif m200:
        tren = "Turun (memantul jangka pendek)" if m50 and harga > m50 else "Turun"
    else:
        tren = "Data belum cukup"

    rsi = hitung_rsi(close)

    # --- Dividen
    satu_th_lalu = tgl_akhir - pd.Timedelta(days=365)
    div12 = float(div[div.index > satu_th_lalu].sum()) if len(div) else 0.0
    yield1 = div12 / harga * 100 if harga else None
    tahun_lengkap = list(range(tgl_akhir.year - 5, tgl_akhir.year))
    per_tahun = {th: float(div[div.index.year == th].sum()) if len(div) else 0.0 for th in tahun_lengkap}
    tahun_bayar = sum(1 for v in per_tahun.values() if v > 0)
    yield5 = (sum(per_tahun.values()) / 5) / harga * 100 if harga else None
    payout = angka(info.get("payoutRatio"))

    # --- Fundamental
    f = {
        "PER": angka(info.get("trailingPE")),
        "PBV": angka(info.get("priceToBook")),
        "EPS": angka(info.get("trailingEps")),
        "ROE": pct(info.get("returnOnEquity")),
        "NPM": pct(info.get("profitMargins")),
        "DER": (angka(info.get("debtToEquity")) / 100) if angka(info.get("debtToEquity")) is not None else None,
        "Pertumbuhan Laba": pct(info.get("earningsGrowth")),
        "Pertumbuhan Pendapatan": pct(info.get("revenueGrowth")),
        "Current Ratio": angka(info.get("currentRatio")),
    }
    if f["PER"] is None and f["EPS"]:
        f["PER"] = harga / f["EPS"]
    keuangan = (info.get("sector") or "").lower().startswith("financial")

    hasil = {
        "simbol": data["simbol"],
        "kode": kode_pendek(data["simbol"]),
        "nama": info.get("longName") or info.get("shortName") or kode_pendek(data["simbol"]),
        "sektor": info.get("sector") or "-",
        "industri": info.get("industry") or "-",
        "tanggal_data": tgl_akhir.strftime("%Y-%m-%d"),
        "harga": harga,
        "kapitalisasi": angka(info.get("marketCap")),
        "keuangan": keuangan,
        "fundamental": f,
        "dividen": {
            "Dividend Yield": yield1, "Yield Rata-rata 5 Th": yield5,
            "Payout Ratio": payout * 100 if payout is not None else None,
            "Konsistensi Dividen": tahun_bayar, "div12": div12,
            "per_tahun": {str(k): v for k, v in per_tahun.items()},
        },
        "teknikal": {
            "MA20": m20, "MA50": m50, "MA200": m200, "RSI": rsi, "tren": tren,
            "cross": [cross[0], cross[1].strftime("%Y-%m-%d")] if cross else None,
            "Return 1 Bln": ret(close, 21), "Return 3 Bln": ret(close, 63),
            "Return 6 Bln": ret(close, 126), "Return 1 Th": ret(close, 252),
            "YTD": ytd,
            "bulanan": {k.strftime("%b %Y"): round(float(v), 2) for k, v in ret_bulanan.items()},
            "tahunan": {str(k.year): round(float(v), 2) for k, v in ret_tahunan.items()},
        },
        "grafik": {
            "tanggal": [d.strftime("%Y-%m-%d") for d in close.index[-252:]],
            "harga": [round(float(v), 2) for v in close.iloc[-252:]],
            **{f"ma{n}": [None if pd.isna(v) else round(float(v), 2) for v in ma[n].iloc[-252:]] for n in ma},
        },
    }
    beri_skor(hasil)
    return hasil


def pct(x):
    v = angka(x)
    return v * 100 if v is not None else None


# ---------------------------------------------------------------------------
# 5. SKOR & REKOMENDASI (aturan sederhana, transparan — ubah sesuai selera)
# ---------------------------------------------------------------------------
def tangga(nilai, aturan, default=0):
    """aturan = [(batas, poin), ...] dicek berurutan: nilai >= batas -> poin."""
    for batas, poin in aturan:
        if nilai >= batas:
            return poin
    return default


def beri_skor(h: dict) -> None:
    f, d, t = h["fundamental"], h["dividen"], h["teknikal"]
    alasan_plus, alasan_min = [], []

    # Fundamental (maks 100, dinormalisasi jika ada data kosong)
    poin, maks = 0.0, 0.0

    def tambah(p, m):
        nonlocal poin, maks
        poin += p
        maks += m

    if f["ROE"] is not None:
        tambah(tangga(f["ROE"], [(20, 25), (15, 20), (10, 12), (5, 6)]), 25)
        if f["ROE"] >= 15:
            alasan_plus.append(f"ROE tinggi ({fmt(f['ROE'], 1)}%)")
        elif f["ROE"] < 8:
            alasan_min.append(f"ROE rendah ({fmt(f['ROE'], 1)}%)")
    if f["NPM"] is not None:
        tambah(tangga(f["NPM"], [(20, 15), (10, 11), (5, 6), (0.01, 3)]), 15)
    if f["DER"] is not None and not h["keuangan"]:
        tambah(15 if f["DER"] <= 0.5 else 11 if f["DER"] <= 1 else 6 if f["DER"] <= 2 else 2, 15)
        if f["DER"] > 2:
            alasan_min.append(f"utang tinggi (DER {fmt(f['DER'], 2)}×)")
    if f["PER"] is not None:
        p = 0 if f["PER"] <= 0 else 20 if f["PER"] <= 10 else 16 if f["PER"] <= 15 else 11 if f["PER"] <= 20 else 6 if f["PER"] <= 30 else 0
        tambah(p, 20)
        if f["PER"] <= 0:
            alasan_min.append("perusahaan merugi (PER negatif)")
        elif f["PER"] <= 12:
            alasan_plus.append(f"valuasi murah (PER {fmt(f['PER'], 1)}×)")
        elif f["PER"] > 30:
            alasan_min.append(f"valuasi mahal (PER {fmt(f['PER'], 1)}×)")
    if f["PBV"] is not None:
        tambah(10 if f["PBV"] <= 1 else 8 if f["PBV"] <= 2 else 5 if f["PBV"] <= 3 else 2 if f["PBV"] <= 5 else 0, 10)
    if f["Pertumbuhan Laba"] is not None:
        tambah(tangga(f["Pertumbuhan Laba"], [(15, 15), (5, 10), (0, 5)]), 15)
        if f["Pertumbuhan Laba"] >= 15:
            alasan_plus.append(f"laba tumbuh {fmt(f['Pertumbuhan Laba'], 1)}%")
        elif f["Pertumbuhan Laba"] < 0:
            alasan_min.append(f"laba turun {fmt(f['Pertumbuhan Laba'], 1)}%")
    s_fund = round(poin / maks * 100) if maks else 50

    # Dividen
    y = d["Dividend Yield"] or 0
    s_div = tangga(y, [(6, 100), (4, 80), (2.5, 60), (1, 35), (0.01, 15)])
    s_div *= 0.6 + 0.08 * d["Konsistensi Dividen"]
    if d["Payout Ratio"] and d["Payout Ratio"] > 100:
        s_div -= 15
        alasan_min.append("payout ratio > 100%")
    s_div = round(max(0, min(100, s_div)))
    if y >= 4:
        alasan_plus.append(f"dividen tinggi ({fmt(y, 1)}%/th)")

    # Tren
    hrg = h["harga"]
    s_tek = 50
    for n, bobot in ((20, 8), (50, 10), (200, 15)):
        m = t[f"MA{n}"]
        if m:
            s_tek += bobot if hrg > m else -bobot
    if t["MA50"] and t["MA200"]:
        s_tek += 7 if t["MA50"] > t["MA200"] else -7
    if t["RSI"] is not None:
        if t["RSI"] > 70:
            s_tek -= 8
            alasan_min.append(f"RSI {fmt(t['RSI'], 0)} — rawan koreksi")
        elif t["RSI"] < 30:
            s_tek += 5
            alasan_plus.append(f"RSI {fmt(t['RSI'], 0)} — oversold")
    if t["Return 1 Th"] is not None:
        s_tek += 5 if t["Return 1 Th"] > 0 else -5
    s_tek = max(0, min(100, s_tek))
    if t["tren"].startswith("Naik kuat"):
        alasan_plus.append("tren naik kuat")
    elif t["tren"].startswith("Turun"):
        alasan_min.append(f"tren {t['tren'].lower()}")

    total = round(0.5 * s_fund + 0.2 * s_div + 0.3 * s_tek)
    rek = "BELI" if total >= 65 else "TAHAN" if total >= 45 else "JUAL"
    h["skor"] = {"fundamental": s_fund, "dividen": s_div, "tren": s_tek, "total": total}
    h["rekomendasi"] = rek
    h["alasan_plus"] = alasan_plus
    h["alasan_min"] = alasan_min


# ---------------------------------------------------------------------------
# 6. PENJELASAN SINGKAT DI SEBELAH ANGKA
# ---------------------------------------------------------------------------
def tafsir(nama: str, v, h: dict) -> str:
    if v is None:
        return "data tidak tersedia"
    if nama == "PER":
        return "rugi" if v <= 0 else "murah" if v <= 10 else "wajar" if v <= 20 else "agak mahal" if v <= 30 else "mahal"
    if nama == "PBV":
        return "di bawah nilai buku" if v < 1 else "wajar" if v <= 3 else "premium"
    if nama == "EPS":
        return "laba positif" if v > 0 else "rugi"
    if nama == "ROE":
        return "sangat baik" if v >= 20 else "baik" if v >= 15 else "cukup" if v >= 8 else "lemah"
    if nama == "NPM":
        return "tebal" if v >= 20 else "sehat" if v >= 10 else "tipis" if v > 0 else "rugi"
    if nama == "DER":
        if h["keuangan"]:
            return "wajar tinggi utk bank — tidak dinilai"
        return "rendah" if v <= 0.5 else "sehat" if v <= 1 else "cukup tinggi" if v <= 2 else "tinggi"
    if nama.startswith("Pertumbuhan"):
        return "tumbuh pesat" if v >= 15 else "tumbuh" if v >= 0 else "menurun"
    if nama == "Current Ratio":
        return "likuid" if v >= 1.5 else "cukup" if v >= 1 else "ketat"
    if nama in ("Dividend Yield", "Yield Rata-rata 5 Th"):
        return "tinggi (> deposito)" if v >= 5 else "menarik" if v >= 3 else "sedang" if v >= 1 else "kecil" if v > 0 else "tidak ada"
    if nama == "Payout Ratio":
        return "terlalu tinggi" if v > 100 else "dermawan" if v > 70 else "wajar" if v >= 30 else "rendah"
    if nama == "Konsistensi Dividen":
        return "konsisten" if v >= 5 else "cukup rutin" if v >= 3 else "jarang"
    if nama.startswith("MA"):
        return "harga di atas → menguat" if h["harga"] > v else "harga di bawah → melemah"
    if nama == "RSI":
        return "overbought" if v > 70 else "oversold" if v < 30 else "netral"
    return ""


# ---------------------------------------------------------------------------
# 7. SNAPSHOT & UPDATE
# ---------------------------------------------------------------------------
def snapshot_ringkas(h: dict) -> dict:
    return {k: h[k] for k in ("kode", "nama", "harga", "skor", "rekomendasi", "tanggal_data")} | {
        "PER": h["fundamental"]["PER"], "PBV": h["fundamental"]["PBV"], "ROE": h["fundamental"]["ROE"],
        "yield": h["dividen"]["Dividend Yield"], "tren": h["teknikal"]["tren"],
    }


def cari_snapshot_lama(hari_ini: str, pilihan: str | None) -> tuple[str, dict] | None:
    if pilihan:
        p = Path(pilihan)
        if not p.exists():
            p = FOLDER_HASIL / f"snapshot_{pilihan}.json"
        if not p.exists():
            sys.exit(f"Snapshot pembanding tidak ditemukan: {pilihan}")
        isi = json.loads(p.read_text(encoding="utf-8"))
        return isi["tanggal"], isi["saham"]
    kandidat = sorted(FOLDER_HASIL.glob("snapshot_*.json"))
    kandidat = [p for p in kandidat if p.stem.replace("snapshot_", "") < hari_ini]
    if not kandidat:
        return None
    isi = json.loads(kandidat[-1].read_text(encoding="utf-8"))
    return isi["tanggal"], isi["saham"]


def simpan_snapshot(hari_ini: str, semua: dict) -> Path:
    FOLDER_HASIL.mkdir(exist_ok=True)
    p = FOLDER_HASIL / f"snapshot_{hari_ini}.json"
    p.write_text(json.dumps({"tanggal": hari_ini, "saham": {v["kode"]: snapshot_ringkas(v) for v in semua.values()}},
                            ensure_ascii=False, indent=1), encoding="utf-8")
    riwayat = FOLDER_HASIL / "riwayat.csv"
    baru = not riwayat.exists()
    # Hapus baris tanggal yang sama agar menjalankan ulang di hari yang sama tidak dobel
    baris_lama = []
    if not baru:
        with riwayat.open(encoding="utf-8") as fh:
            baris_lama = [r for r in csv.DictReader(fh) if r["tanggal"] != hari_ini]
    kolom = ["tanggal", "kode", "harga", "skor_total", "skor_fundamental", "skor_dividen", "skor_tren", "rekomendasi"]
    with riwayat.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=kolom)
        w.writeheader()
        w.writerows(baris_lama)
        for h in semua.values():
            s = h["skor"]
            w.writerow({"tanggal": hari_ini, "kode": h["kode"], "harga": round(h["harga"], 2),
                        "skor_total": s["total"], "skor_fundamental": s["fundamental"],
                        "skor_dividen": s["dividen"], "skor_tren": s["tren"], "rekomendasi": h["rekomendasi"]})
    return p


# ---------------------------------------------------------------------------
# 8. LAPORAN HTML
# ---------------------------------------------------------------------------
def fmt(v, des=0, sat=""):
    """Format angka gaya Indonesia: 1.234,5"""
    if v is None:
        return "–"
    s = f"{v:,.{des}f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return s + sat


def fmt_besar(v):
    if v is None:
        return "–"
    for batas, sat in ((1e12, " T"), (1e9, " M"), (1e6, " Jt")):
        if abs(v) >= batas:
            return "Rp" + fmt(v / batas, 1) + sat
    return "Rp" + fmt(v)


def fmt_pct(v, des=1, tanda=False):
    if v is None:
        return "–"
    return ("+" if tanda and v > 0 else "") + fmt(v, des) + "%"


class Catatan:
    """Memberi nomor catatan kaki untuk tiap istilah yang muncul."""

    def __init__(self):
        self.urut: list[str] = []

    def __call__(self, nama: str, label: str | None = None) -> str:
        if nama not in ISTILAH:
            return html.escape(label or nama)
        if nama not in self.urut:
            self.urut.append(nama)
        no = self.urut.index(nama) + 1
        return (f'<span class="term" title="{html.escape(ISTILAH[nama])}">{html.escape(label or nama)}'
                f'<sup><a href="#cat-{no}">{no}</a></sup></span>')


BADGE = {"BELI": ("good", "▲"), "TAHAN": ("warn", "■"), "JUAL": ("crit", "▼")}


def badge(rek: str) -> str:
    kls, ikon = BADGE[rek]
    return f'<span class="badge {kls}">{ikon} {rek}</span>'


def bar_skor(nama, v):
    return (f'<div class="skor"><span>{nama}</span><div class="track"><div class="fill" style="width:{v}%"></div>'
            f'</div><b>{v}</b></div>')


def baris_metrik(cat, nama, v, teks, h, label=None):
    return (f"<tr><th>{cat(nama, label)}</th><td class='num'>{teks}</td>"
            f"<td class='tafsir'>{html.escape(tafsir(nama, v, h))}</td></tr>")


def grafik_harga(h: dict, idx: int) -> str:
    g = h["grafik"]
    W, H, pl, pr, pt, pb = 640, 220, 52, 12, 10, 24
    semua = [v for k in ("harga", "ma20", "ma50", "ma200") for v in g[k] if v is not None]
    lo, hi = min(semua), max(semua)
    pad = (hi - lo) * 0.05 or 1
    lo, hi = lo - pad, hi + pad
    n = len(g["harga"])

    def x(i):
        return pl + i * (W - pl - pr) / max(1, n - 1)

    def y(v):
        return pt + (hi - v) * (H - pt - pb) / (hi - lo)

    def path(seri):
        d, mulai = [], True
        for i, v in enumerate(seri):
            if v is None:
                mulai = True
                continue
            d.append(f"{'M' if mulai else 'L'}{x(i):.1f},{y(v):.1f}")
            mulai = False
        return " ".join(d)

    grid = []
    for k in range(5):
        v = lo + (hi - lo) * k / 4
        grid.append(f'<line class="grid" x1="{pl}" x2="{W - pr}" y1="{y(v):.1f}" y2="{y(v):.1f}"/>'
                    f'<text class="axis" x="{pl - 6}" y="{y(v) + 4:.1f}" text-anchor="end">{fmt(v)}</text>')
    bulan_terakhir = None
    for i, t in enumerate(g["tanggal"]):
        b = t[:7]
        if b != bulan_terakhir and i > 0 and int(t[5:7]) % 3 == 1:
            grid.append(f'<text class="axis" x="{x(i):.1f}" y="{H - 6}" text-anchor="middle">'
                        f'{dt.date.fromisoformat(t).strftime("%b %y")}</text>')
        bulan_terakhir = b
    # Urutan gambar: MA200 paling bawah, harga paling atas
    garis = "".join(f'<path class="ln s{j}" d="{path(g[k])}"/>' for j, k in
                    ((4, "ma200"), (3, "ma50"), (2, "ma20"), (1, "harga")))
    data = html.escape(json.dumps(g, separators=(",", ":")))
    return (f'<div class="chart" data-g="{data}" data-lo="{lo}" data-hi="{hi}">'
            f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Grafik harga 1 tahun {h["kode"]} dengan MA20, MA50, MA200">'
            f'{"".join(grid)}{garis}<line class="cross" x1="0" x2="0" y1="{pt}" y2="{H - pb}" visibility="hidden"/>'
            f'<rect class="hit" x="{pl}" y="{pt}" width="{W - pl - pr}" height="{H - pt - pb}"/></svg>'
            f'<div class="tip" hidden></div></div>')


def grafik_bulanan(h: dict) -> str:
    data = h["teknikal"]["bulanan"]
    if not data:
        return ""
    W, H, pt, pb = 640, 130, 14, 22
    vals = list(data.values())
    m = max(abs(v) for v in vals) or 1
    nol = pt + (H - pt - pb) / 2
    lebar = (W - 20) / len(vals)
    batang = []
    for i, (bln, v) in enumerate(data.items()):
        tinggi = abs(v) / m * (H - pt - pb) / 2
        yy = nol - tinggi if v >= 0 else nol
        kls = "pos" if v >= 0 else "neg"
        cx = 10 + i * lebar
        batang.append(
            f'<g class="bar"><title>{bln}: {fmt_pct(v, 1, True)}</title>'
            f'<rect class="hitbar" x="{cx:.1f}" y="{pt}" width="{lebar:.1f}" height="{H - pt - pb}"/>'
            f'<rect class="{kls}" x="{cx + 3:.1f}" y="{yy:.1f}" width="{lebar - 6:.1f}" height="{max(tinggi, 1):.1f}" rx="2"/>'
            f'<text class="axis" x="{cx + lebar / 2:.1f}" y="{H - 6}" text-anchor="middle">{bln[:3]}</text></g>')
    return (f'<svg class="bulanan" viewBox="0 0 {W} {H}" role="img" aria-label="Return bulanan 12 bulan">'
            f'<line class="zero" x1="10" x2="{W - 10}" y1="{nol}" y2="{nol}"/>{"".join(batang)}</svg>')


def tabel_pembanding(h: dict, semua: dict, cat) -> str:
    peers = [p for p in h.get("pembanding", []) if p in semua]
    if not peers:
        return "<p class='muted'>Belum ada saham pembanding untuk kode ini. Tambahkan di KELOMPOK dalam script, atau pakai opsi --pembanding.</p>"
    baris = []
    lebih_baik = []
    for s in [h["simbol"]] + peers:
        p = semua[s]
        f, d, t = p["fundamental"], p["dividen"], p["teknikal"]
        utama = s == h["simbol"]
        tanda = ""
        if not utama and p["skor"]["total"] > h["skor"]["total"]:
            tanda = ' <span class="star" title="Skor total lebih tinggi">★ lebih baik</span>'
            lebih_baik.append(p["kode"])
        baris.append(
            f"<tr class='{'utama' if utama else ''}'><th>{p['kode']}{tanda}</th>"
            f"<td class='num'>{fmt(f['PER'], 1)}</td><td class='num'>{fmt(f['PBV'], 2)}</td>"
            f"<td class='num'>{fmt_pct(f['ROE'])}</td><td class='num'>{fmt_pct(d['Dividend Yield'])}</td>"
            f"<td class='num'>{fmt_pct(t['Return 1 Th'], 1, True)}</td><td>{html.escape(t['tren'])}</td>"
            f"<td class='num'><b>{p['skor']['total']}</b></td><td>{badge(p['rekomendasi'])}</td></tr>")
    ringkas = (f"<p>Alternatif dengan skor lebih tinggi: <b>{', '.join(lebih_baik)}</b>. Pelajari kenapa — "
               f"apakah karena valuasi lebih murah, ROE lebih tinggi, atau trennya lebih kuat?</p>"
               if lebih_baik else f"<p><b>{h['kode']}</b> memiliki skor tertinggi di antara pembandingnya.</p>")
    return (f"<div class='scroll'><table class='banding'><thead><tr><th>Kode</th><th>{cat('PER')}</th><th>{cat('PBV')}</th>"
            f"<th>{cat('ROE')}</th><th>{cat('Dividend Yield', 'Yield')}</th><th>{cat('Return', 'Return 1Th')}</th>"
            f"<th>Tren</th><th>{cat('Skor')}</th><th>{cat('Rekomendasi', 'Rek.')}</th></tr></thead>"
            f"<tbody>{''.join(baris)}</tbody></table></div>{ringkas}")


def kartu(h: dict, semua: dict, lama: dict | None, cat, idx: int) -> str:
    f, d, t, s = h["fundamental"], h["dividen"], h["teknikal"], h["skor"]
    perubahan = ""
    if lama:
        dh = (h["harga"] / lama["harga"] - 1) * 100
        ds = s["total"] - lama["skor"]["total"]
        rek_ubah = (f" · rekomendasi <b>{lama['rekomendasi']} → {h['rekomendasi']}</b>"
                    if lama["rekomendasi"] != h["rekomendasi"] else "")
        perubahan = (f"<div class='delta'>Sejak resume sebelumnya: harga {fmt_pct(dh, 1, True)}, "
                     f"skor {'+' if ds > 0 else ''}{ds}{rek_ubah}</div>")

    fund_rows = "".join([
        baris_metrik(cat, "EPS", f["EPS"], "Rp" + fmt(f["EPS"], 1) if f["EPS"] is not None else "–", h),
        baris_metrik(cat, "PER", f["PER"], fmt(f["PER"], 1, "×"), h),
        baris_metrik(cat, "PBV", f["PBV"], fmt(f["PBV"], 2, "×"), h),
        baris_metrik(cat, "ROE", f["ROE"], fmt_pct(f["ROE"]), h),
        baris_metrik(cat, "NPM", f["NPM"], fmt_pct(f["NPM"]), h),
        baris_metrik(cat, "DER", f["DER"], fmt(f["DER"], 2, "×"), h),
        baris_metrik(cat, "Pertumbuhan Laba", f["Pertumbuhan Laba"], fmt_pct(f["Pertumbuhan Laba"], 1, True), h),
        baris_metrik(cat, "Pertumbuhan Pendapatan", f["Pertumbuhan Pendapatan"], fmt_pct(f["Pertumbuhan Pendapatan"], 1, True), h),
        baris_metrik(cat, "Current Ratio", f["Current Ratio"], fmt(f["Current Ratio"], 2, "×"), h),
    ])
    div_rows = "".join([
        baris_metrik(cat, "Dividend Yield", d["Dividend Yield"], fmt_pct(d["Dividend Yield"], 2), h),
        f"<tr><th>Dividen 12 bln</th><td class='num'>Rp{fmt(d['div12'], 1)}</td><td class='tafsir'>per lembar</td></tr>",
        baris_metrik(cat, "Yield Rata-rata 5 Th", d["Yield Rata-rata 5 Th"], fmt_pct(d["Yield Rata-rata 5 Th"], 2), h),
        baris_metrik(cat, "Payout Ratio", d["Payout Ratio"], fmt_pct(d["Payout Ratio"], 0), h),
        baris_metrik(cat, "Konsistensi Dividen", d["Konsistensi Dividen"], f"{d['Konsistensi Dividen']} dari 5 th", h),
    ])
    tek_rows = "".join([
        baris_metrik(cat, "MA20", t["MA20"], fmt(t["MA20"]), h),
        baris_metrik(cat, "MA50", t["MA50"], fmt(t["MA50"]), h),
        baris_metrik(cat, "MA200", t["MA200"], fmt(t["MA200"]), h),
        baris_metrik(cat, "RSI", t["RSI"], fmt(t["RSI"], 0), h),
    ])
    if t["cross"]:
        tek_rows += (f"<tr><th>{cat(t['cross'][0])}</th><td class='num'>{t['cross'][1]}</td>"
                     f"<td class='tafsir'>terjadi dalam 3 bulan terakhir</td></tr>")
    periode = [("1 Bln", "Return 1 Bln"), ("3 Bln", "Return 3 Bln"), ("6 Bln", "Return 6 Bln"),
               ("1 Th", "Return 1 Th"), (cat("YTD"), "YTD")]
    ret_html = "".join(f"<div class='ret'><span>{lbl}</span><b class='{'up' if (t[k] or 0) >= 0 else 'down'}'>"
                       f"{fmt_pct(t[k], 1, True)}</b></div>" for lbl, k in periode)
    tahunan = "".join(f"<div class='ret'><span>{th}</span><b class='{'up' if v >= 0 else 'down'}'>{fmt_pct(v, 1, True)}</b></div>"
                      for th, v in t["tahunan"].items())
    plus = "".join(f"<li class='plus'>✓ {html.escape(a)}</li>" for a in h["alasan_plus"]) or ""
    minus = "".join(f"<li class='minus'>✕ {html.escape(a)}</li>" for a in h["alasan_min"]) or ""
    grup = f" · kelompok {h['kelompok']}" if h.get("kelompok") else ""

    return f"""
<section class="card" id="{h['kode']}">
  <header>
    <div><h2>{h['kode']} <small>{html.escape(h['nama'])}</small></h2>
      <p class="muted">{html.escape(h['sektor'])} / {html.escape(h['industri'])}{grup} · data per {h['tanggal_data']}</p></div>
    <div class="harga"><b>Rp{fmt(h['harga'])}</b><span class="muted">{cat('Kapitalisasi')} {fmt_besar(h['kapitalisasi'])}</span></div>
  </header>
  {perubahan}
  <div class="ringkas">
    <div class="rek">{badge(h['rekomendasi'])}<div class="total">{s['total']}<small>/100</small></div>
      <span class="muted">{cat('Skor', 'skor total')}</span></div>
    <div class="skor-wrap">{bar_skor('Fundamental (50%)', s['fundamental'])}{bar_skor('Dividen (20%)', s['dividen'])}{bar_skor('Tren (30%)', s['tren'])}</div>
    <ul class="alasan">{plus}{minus}</ul>
  </div>
  <div class="grid3">
    <div><h3>1 · Fundamental</h3><table class="m">{fund_rows}</table></div>
    <div><h3>2 · Dividen</h3><table class="m">{div_rows}</table></div>
    <div><h3>3 · Tren — <span class="tren">{html.escape(t['tren'])}</span></h3><table class="m">{tek_rows}</table>
      <div class="rets">{ret_html}</div></div>
  </div>
  <h3>Harga 1 tahun &amp; moving average</h3>
  <div class="legend"><span><i class="k s1"></i>Harga</span><span><i class="k s2"></i>{cat('MA20')}</span>
    <span><i class="k s3"></i>{cat('MA50')}</span><span><i class="k s4"></i>{cat('MA200')}</span></div>
  {grafik_harga(h, idx)}
  <div class="grid2">
    <div><h3>{cat('Return', 'Return')} bulanan (12 bln)</h3>{grafik_bulanan(h)}</div>
    <div><h3>{cat('Return', 'Return')} tahunan</h3><div class="rets">{tahunan}</div>
      <p class="muted kecil">Tahun berjalan = sejak awal tahun sampai hari ini.</p></div>
  </div>
  <h3>4 · Pembanding sejenis</h3>
  {tabel_pembanding(h, semua, cat)}
</section>"""


CSS = """
:root{--surface:#fcfcfb;--card:#ffffff;--text:#0b0b0b;--text2:#52514e;--muted:#7a7974;--line:#e4e3df;
--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--s4:#eda100;--pos:#2a78d6;--neg:#e34948;--good:#0ca30c;--warn:#fab219;--crit:#d03b3b;--track:#f0efec}
@media (prefers-color-scheme:dark){:root{--surface:#1a1a19;--card:#222220;--text:#f0efec;--text2:#c3c2b7;--muted:#9b9a92;--line:#383835;
--s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#c98500;--pos:#3987e5;--neg:#e66767;--track:#383835}}
*{box-sizing:border-box}body{margin:0;background:var(--surface);color:var(--text);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
main{max-width:1100px;margin:auto;padding:24px 16px 60px}h1{margin:0 0 4px;font-size:26px}h2{margin:0;font-size:22px}h2 small{font-weight:400;color:var(--text2);font-size:15px}
h3{font-size:14px;text-transform:uppercase;letter-spacing:.04em;color:var(--text2);margin:22px 0 8px}
.muted{color:var(--muted)}.kecil{font-size:13px}a{color:var(--s1)}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:20px;margin:22px 0}
.card header{display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap}.card header p{margin:2px 0 0}
.harga{text-align:right;display:flex;flex-direction:column}.harga b{font-size:24px}
.delta{margin-top:12px;padding:8px 12px;border-radius:8px;background:var(--track);font-size:14px}
.ringkas{display:grid;grid-template-columns:150px 1fr 1fr;gap:20px;align-items:center;margin-top:16px}
.rek{text-align:center}.total{font-size:40px;font-weight:700;line-height:1.1;margin-top:6px}.total small{font-size:15px;color:var(--muted)}
.badge{display:inline-block;padding:4px 12px;border-radius:999px;font-weight:700;font-size:14px;border:2px solid}
.badge.good{color:var(--good);border-color:var(--good)}.badge.warn{color:#9a6a00;border-color:var(--warn)}.badge.crit{color:var(--crit);border-color:var(--crit)}
@media (prefers-color-scheme:dark){.badge.warn{color:var(--warn)}}
.skor{display:grid;grid-template-columns:150px 1fr 32px;gap:8px;align-items:center;font-size:14px;margin:6px 0}
.track{height:8px;background:var(--track);border-radius:4px;overflow:hidden}.fill{height:100%;background:var(--s1);border-radius:4px}
.alasan{list-style:none;margin:0;padding:0;font-size:14px}.alasan li{margin:3px 0}.plus{color:var(--text)}.plus::first-letter{color:var(--good)}.minus::first-letter{color:var(--crit)}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}.grid2{display:grid;grid-template-columns:1.4fr 1fr;gap:20px}
table{border-collapse:collapse;width:100%;font-size:14px}table.m th{text-align:left;font-weight:500;color:var(--text2);padding:5px 6px 5px 0;white-space:nowrap}
table.m td{padding:5px 6px;border-top:1px solid var(--line)}table.m th{border-top:1px solid var(--line)}
.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}.tafsir{color:var(--muted);font-size:12.5px}
.term{border-bottom:1px dotted var(--muted);cursor:help}.term sup a{text-decoration:none;font-size:10px;margin-left:1px}
.rets{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}.ret{background:var(--track);border-radius:8px;padding:6px 10px;display:flex;flex-direction:column;min-width:70px}
.ret span{font-size:12px;color:var(--text2)}.up{color:var(--text)}.up::before{content:"▲ ";color:var(--pos);font-size:10px}.down::before{content:"▼ ";color:var(--neg);font-size:10px}
.tren{color:var(--text);text-transform:none;letter-spacing:0}
.legend{display:flex;gap:16px;font-size:13px;color:var(--text2);flex-wrap:wrap}.k{display:inline-block;width:14px;height:3px;border-radius:2px;vertical-align:middle;margin-right:6px}
.k.s1{background:var(--s1);height:4px}.k.s2{background:var(--s2)}.k.s3{background:var(--s3)}.k.s4{background:var(--s4)}
.chart{position:relative}svg{width:100%;height:auto;display:block}.grid{stroke:var(--line);stroke-width:1}.axis{fill:var(--muted);font-size:11px}
.ln{fill:none;stroke-width:1.5}.ln.s1{stroke:var(--s1);stroke-width:2}.ln.s2{stroke:var(--s2)}.ln.s3{stroke:var(--s3)}.ln.s4{stroke:var(--s4)}
.cross{stroke:var(--muted);stroke-dasharray:3 3}.hit{fill:transparent;cursor:crosshair}
.tip{position:absolute;top:0;pointer-events:none;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:6px 10px;font-size:12.5px;box-shadow:0 4px 14px rgba(0,0,0,.12);white-space:nowrap}
.tip i{display:inline-block;width:10px;height:3px;margin-right:6px;vertical-align:middle}
.bulanan .pos{fill:var(--pos)}.bulanan .neg{fill:var(--neg)}.zero{stroke:var(--muted)}.hitbar{fill:transparent}.bar:hover .hitbar{fill:var(--track)}
.scroll{overflow-x:auto}table.banding th,table.banding td{padding:7px 8px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}
table.banding thead th{color:var(--text2);font-weight:500;font-size:13px}table.banding tr.utama{background:var(--track)}
.star{color:var(--text);font-size:12px;font-weight:600;background:var(--track);border-radius:6px;padding:1px 6px}
.ringkasan-tbl td,.ringkasan-tbl th{padding:8px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}
.disclaimer{border-left:4px solid var(--warn);padding:10px 14px;background:var(--card);border-radius:6px;font-size:14px}
ol.catatan li{margin:6px 0}ol.catatan b{display:inline-block;min-width:150px}
@media (max-width:820px){.grid3,.grid2,.ringkas{grid-template-columns:1fr}.harga{text-align:left}}
"""

JS = """
document.querySelectorAll('.chart').forEach(function(el){
  var g=JSON.parse(el.dataset.g), lo=+el.dataset.lo, hi=+el.dataset.hi;
  var svg=el.querySelector('svg'), hit=el.querySelector('.hit'), cr=el.querySelector('.cross'), tip=el.querySelector('.tip');
  var vb=svg.viewBox.baseVal, x0=+hit.getAttribute('x'), w=+hit.getAttribute('width'), n=g.harga.length;
  var f=function(v){return v==null?'–':Math.round(v).toLocaleString('id-ID')};
  function show(ev){
    var r=svg.getBoundingClientRect(), px=(ev.clientX-r.left)*vb.width/r.width;
    var i=Math.max(0,Math.min(n-1,Math.round((px-x0)/w*(n-1)))), xx=x0+i*w/(n-1);
    cr.setAttribute('x1',xx);cr.setAttribute('x2',xx);cr.setAttribute('visibility','visible');
    tip.innerHTML='<b>'+g.tanggal[i]+'</b><br><i style="background:var(--s1)"></i>Harga '+f(g.harga[i])+
      '<br><i style="background:var(--s2)"></i>MA20 '+f(g.ma20[i])+'<br><i style="background:var(--s3)"></i>MA50 '+f(g.ma50[i])+
      '<br><i style="background:var(--s4)"></i>MA200 '+f(g.ma200[i]);
    tip.hidden=false; var left=xx*r.width/vb.width; tip.style.left=(left>r.width*0.6?left-tip.offsetWidth-12:left+12)+'px';
  }
  hit.addEventListener('pointermove',show);hit.addEventListener('pointerdown',show);
  hit.addEventListener('pointerleave',function(){tip.hidden=true;cr.setAttribute('visibility','hidden')});
});
"""


def buat_laporan(utama: list[str], semua: dict, hari_ini: str, lama: tuple[str, dict] | None, demo: bool) -> str:
    cat = Catatan()
    lama_saham = lama[1] if lama else {}
    kartu_html = "".join(kartu(semua[s], semua, lama_saham.get(semua[s]["kode"]), cat, i) for i, s in enumerate(utama))

    # Tabel ringkasan di atas
    baris = []
    for s in sorted(utama, key=lambda k: -semua[k]["skor"]["total"]):
        h = semua[s]
        l = lama_saham.get(h["kode"])
        ubah = "baru"
        if l:
            ubah = f"{fmt_pct((h['harga'] / l['harga'] - 1) * 100, 1, True)} · skor {h['skor']['total'] - l['skor']['total']:+d}"
            if l["rekomendasi"] != h["rekomendasi"]:
                ubah += f" · {l['rekomendasi']}→{h['rekomendasi']}"
        baris.append(f"<tr><th><a href='#{h['kode']}'>{h['kode']}</a></th><td class='num'>Rp{fmt(h['harga'])}</td>"
                     f"<td class='num'>{h['skor']['fundamental']}</td><td class='num'>{h['skor']['dividen']}</td>"
                     f"<td class='num'>{h['skor']['tren']}</td><td class='num'><b>{h['skor']['total']}</b></td>"
                     f"<td>{badge(h['rekomendasi'])}</td><td class='muted'>{ubah if lama else '–'}</td></tr>")
    info_update = (f"Dibandingkan dengan resume sebelumnya tanggal <b>{lama[0]}</b>." if lama
                   else "Ini resume pertama — jalankan lagi nanti untuk melihat perubahannya.")
    catatan = "".join(f"<li id='cat-{i + 1}'><b>{html.escape(n)}</b> {html.escape(ISTILAH[n])}</li>"
                      for i, n in enumerate(cat.urut))
    demo_note = ("<p class='disclaimer'><b>MODE DEMO</b> — semua angka di laporan ini karangan, hanya untuk mencoba tampilan. "
                 "Jalankan tanpa <code>--demo</code> untuk data asli.</p>") if demo else ""

    return f"""<!DOCTYPE html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Resume Saham {hari_ini}</title>
<style>{CSS}</style></head><body><main>
<h1>Resume Saham</h1><p class="muted">Dibuat {hari_ini} · {info_update}</p>
{demo_note}
<div class="scroll"><table class="ringkasan-tbl"><thead><tr><th>Kode</th><th>Harga</th><th>Fundamental</th><th>Dividen</th>
<th>Tren</th><th>{cat('Skor', 'Total')}</th><th>{cat('Rekomendasi')}</th><th>Perubahan</th></tr></thead><tbody>{''.join(baris)}</tbody></table></div>
{kartu_html}
<section class="card"><h2>Cara skor dihitung</h2>
<p><b>Fundamental (50%)</b> — poin dari ROE, NPM, DER (bank dikecualikan), PER, PBV, dan pertumbuhan laba.
<b>Dividen (20%)</b> — dari dividend yield, dikalikan faktor konsistensi 5 tahun, dikurangi jika payout &gt; 100%.
<b>Tren (30%)</b> — mulai 50, naik/turun berdasarkan posisi harga terhadap MA20/MA50/MA200, posisi MA50 vs MA200, RSI, dan return 1 tahun.</p>
<p>Semua aturan ada di fungsi <code>beri_skor()</code> dalam script dan boleh diubah sesuai pemahaman Anda.</p></section>
<section class="card"><h2>Catatan kaki — kamus istilah</h2><p class="muted kecil">Arahkan kursor / ketuk istilah bergaris titik untuk penjelasan cepat, atau klik nomornya.</p>
<ol class="catatan">{catatan}</ol></section>
<p class="disclaimer"><b>Disclaimer:</b> laporan ini dibuat otomatis untuk tujuan belajar. Data dari Yahoo Finance bisa terlambat atau
tidak lengkap. Rekomendasi berasal dari aturan sederhana, bukan nasihat investasi — selalu cek laporan keuangan resmi (idx.co.id) sebelum memutuskan.</p>
</main><script>{JS}</script></body></html>"""


# ---------------------------------------------------------------------------
# 9. PROGRAM UTAMA
# ---------------------------------------------------------------------------
def baca_watchlist() -> list[str]:
    if not FILE_WATCHLIST.exists():
        FILE_WATCHLIST.write_text("# Satu kode per baris. Baris diawali # diabaikan.\nBBCA\nTLKM\nADRO\n", encoding="utf-8")
    return [b.strip() for b in FILE_WATCHLIST.read_text(encoding="utf-8").splitlines()
            if b.strip() and not b.strip().startswith("#")]


def main():
    ap = argparse.ArgumentParser(description="Resume saham: fundamental, dividen, tren, rekomendasi, pembanding.")
    ap.add_argument("kode", nargs="*", help="kode saham, mis. BBCA TLKM (kosong = pakai watchlist.txt)")
    ap.add_argument("--pembanding", help="kode pembanding manual, pisahkan koma: BBRI,BMRI")
    ap.add_argument("--tanpa-pembanding", action="store_true", help="lewati perbandingan (lebih cepat)")
    ap.add_argument("--bandingkan", help="tanggal (YYYY-MM-DD) atau file snapshot lama yang ingin dibandingkan")
    ap.add_argument("--demo", action="store_true", help="pakai data karangan (tanpa internet)")
    ap.add_argument("--tanggal", help=argparse.SUPPRESS)  # untuk uji coba mode demo
    ap.add_argument("--jangan-buka", action="store_true", help="jangan otomatis membuka laporan di browser")
    a = ap.parse_args()

    hari = dt.date.fromisoformat(a.tanggal) if a.tanggal else dt.date.today()
    hari_ini = hari.isoformat()
    utama = [normalisasi_kode(k) for k in (a.kode or baca_watchlist())]
    manual = [normalisasi_kode(k) for k in a.pembanding.split(",")] if a.pembanding else None

    semua, gagal = {}, []

    def proses(simbol):
        if simbol in semua:
            return True
        try:
            print(f"  mengambil {simbol} ...", flush=True)
            data = ambil_data_demo(simbol, hari) if a.demo else ambil_data_yahoo(simbol)
            semua[simbol] = analisis(data)
            return True
        except Exception as e:  # lanjut ke saham lain
            print(f"  ! gagal {simbol}: {e}")
            gagal.append(simbol)
            return False

    print(f"Resume Saham {hari_ini}{' (DEMO)' if a.demo else ''}")
    utama = [s for s in utama if proses(s)]
    if not utama:
        sys.exit("Tidak ada saham yang berhasil diambil. Cek koneksi internet / kode saham.")
    if not a.tanpa_pembanding:
        for s in utama:
            grup, peers = cari_pembanding(s)
            if manual:
                peers = [p for p in manual if p != s]
            semua[s]["kelompok"] = grup if not manual else "pilihan sendiri"
            semua[s]["pembanding"] = [p for p in peers if proses(p)]

    lama = cari_snapshot_lama(hari_ini, a.bandingkan)
    FOLDER_HASIL.mkdir(exist_ok=True)
    laporan = FOLDER_HASIL / f"resume_{hari_ini}.html"
    laporan.write_text(buat_laporan(utama, semua, hari_ini, lama, a.demo), encoding="utf-8")
    (FOLDER_HASIL / "resume_terbaru.html").write_text(laporan.read_text(encoding="utf-8"), encoding="utf-8")
    snap = simpan_snapshot(hari_ini, {s: semua[s] for s in semua})

    print("\nRingkasan:")
    for s in sorted(utama, key=lambda k: -semua[k]["skor"]["total"]):
        h = semua[s]
        print(f"  {h['kode']:<6} Rp{fmt(h['harga']):>9}  skor {h['skor']['total']:>3}  {h['rekomendasi']:<5}  {h['teknikal']['tren']}")
    if lama:
        print(f"\nDibandingkan dengan resume {lama[0]}.")
    if gagal:
        print(f"Gagal diambil: {', '.join(gagal)}")
    print(f"\nLaporan : {laporan}\nSnapshot: {snap}")
    if not a.jangan_buka:
        webbrowser.open(laporan.as_uri())


if __name__ == "__main__":
    main()
