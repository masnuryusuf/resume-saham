"""
Resume Saham — aplikasi sederhana untuk meringkas saham berdasarkan:
  1. Kekuatan fundamental keuangan
  2. Imbal hasil dividen
  3. Tren harga tahunan & bulanan
  4. Rekomendasi BELI / TAHAN / JUAL
  5. Perbandingan dengan saham sejenis (peer)

Data: Yahoo Finance (via library yfinance). Saham BEI memakai akhiran .JK (mis. BBCA.JK).
Jalankan:  streamlit run app.py

Catatan: skor & rekomendasi dihitung dengan aturan sederhana (rule-based),
BUKAN nasihat investasi. Selalu lakukan riset sendiri.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

# ---------------------------------------------------------------------------
# Daftar saham sejenis (peer) BEI. Silakan tambah/ubah sesuai kebutuhan.
# ---------------------------------------------------------------------------
PEER_GROUPS: dict[str, list[str]] = {
    "Perbankan": ["BBCA", "BBRI", "BMRI", "BBNI", "BRIS", "BNGA", "BBTN"],
    "Telekomunikasi": ["TLKM", "ISAT", "EXCL", "MTEL", "TOWR","KLBF","TRON"],
    "Konsumer": ["UNVR", "ICBP", "INDF", "MYOR", "CPIN", "JPFA", "SIDO"],
    "Farmasi & Kesehatan": ["KLBF", "SIDO", "MIKA", "HEAL", "SILO"],
    "Batu Bara": ["PTBA", "ITMG", "AADI", "ADRO", "INDY", "BUMI"],
    "Logam & Nikel": ["ANTM", "INCO", "MDKA", "NCKL", "TINS", "MBMA"],
    "Otomotif & Konglomerasi": ["ASII", "UNTR", "AUTO", "DRMA"],
    "Semen & Konstruksi": ["SMGR", "INTP", "WIKA", "PTPP", "ADHI"],
    "Energi & Migas": ["PGAS", "MEDC", "AKRA", "ELSA", "PGEO"],
    "Ritel": ["AMRT", "MIDI", "MAPI", "ACES", "ERAA"],
    "Properti": ["BSDE", "CTRA", "PWON", "SMRA", "PANI"],
    "Teknologi": ["GOTO", "BUKA", "EMTK", "DCII"],
    "Perkebunan (CPO)": ["AALI", "LSIP", "SSMS", "DSNG", "TAPG"],
}

FINANCIAL_SECTORS = {"Financial Services", "Banks", "Financial"}


# ---------------------------------------------------------------------------
# KAMUS ISTILAH & SINGKATAN (untuk belajar)
#   nama    : kepanjangan / nama lengkap
#   arti    : penjelasan singkat dengan bahasa sederhana
#   patokan : cara membaca angkanya (patokan umum, bukan aturan mutlak)
# ---------------------------------------------------------------------------
GLOSARIUM: dict[str, dict[str, str]] = {
    # --- Umum
    "BEI / .JK": dict(nama="Bursa Efek Indonesia",
                      arti="Bursa saham Indonesia. Di Yahoo Finance, kode saham BEI diberi akhiran .JK (Jakarta), mis. BBCA.JK.",
                      patokan="—"),
    "Harga": dict(nama="Harga saham terakhir",
                  arti="Harga transaksi terakhir per lembar saham. Di BEI, 1 lot = 100 lembar.",
                  patokan="Harga murah/mahal tidak bisa dinilai dari angkanya saja — lihat PER dan PBV."),
    "Kapitalisasi pasar": dict(nama="Market capitalization (market cap)",
                               arti="Harga saham × jumlah seluruh saham beredar. Menggambarkan 'harga' seluruh perusahaan di bursa.",
                               patokan="Big cap (> Rp100 T) umumnya lebih stabil; small cap lebih fluktuatif."),
    "TTM": dict(nama="Trailing Twelve Months",
                arti="Data 12 bulan terakhir (4 kuartal terakhir), bukan per tahun kalender.",
                patokan="—"),
    "YoY": dict(nama="Year on Year",
                arti="Dibandingkan dengan periode yang sama tahun lalu, mis. kuartal III 2026 vs kuartal III 2025.",
                patokan="—"),
    "Peer": dict(nama="Saham sejenis / pembanding",
                 arti="Perusahaan dalam sektor/industri yang sama. Rasio keuangan sebaiknya dibandingkan dengan peer, "
                      "bukan dengan sektor lain (PER bank tidak sebanding dengan PER tambang).",
                 patokan="—"),
    # --- Fundamental
    "Fundamental": dict(nama="Analisis fundamental",
                        arti="Menilai kesehatan bisnis dari laporan keuangan: seberapa besar labanya, seberapa cepat tumbuh, "
                             "seberapa besar utangnya.",
                        patokan="Skor ≥ 65 kuat · 45–64 cukup · < 45 lemah."),
    "ROE": dict(nama="Return on Equity (imbal hasil ekuitas)",
                arti="Laba bersih ÷ modal pemegang saham. Dari setiap Rp100 modal pemilik, berapa rupiah laba yang dihasilkan setahun.",
                patokan="≥ 15% bagus · 8–15% cukup · < 8% lemah."),
    "ROA": dict(nama="Return on Assets (imbal hasil aset)",
                arti="Laba bersih ÷ total aset. Seberapa efisien seluruh aset (termasuk yang dibiayai utang) menghasilkan laba.",
                patokan="Bank ≥ 2% bagus (aset bank sangat besar) · non-bank ≥ 8% bagus."),
    "NPM": dict(nama="Net Profit Margin (margin laba bersih)",
                arti="Laba bersih ÷ pendapatan. Dari setiap Rp100 penjualan, berapa yang tersisa menjadi laba setelah semua biaya & pajak.",
                patokan="≥ 15% tebal · 5–15% wajar · < 5% tipis. Ritel memang biasanya tipis."),
    "Pertumbuhan pendapatan": dict(nama="Revenue growth (YoY)",
                                   arti="Kenaikan/penurunan penjualan dibanding periode yang sama tahun lalu.",
                                   patokan="≥ 10% bagus · negatif = penjualan menyusut."),
    "Pertumbuhan laba": dict(nama="Earnings growth (YoY)",
                             arti="Kenaikan/penurunan laba bersih dibanding periode yang sama tahun lalu.",
                             patokan="≥ 10% bagus · negatif = laba turun."),
    "DER": dict(nama="Debt to Equity Ratio (rasio utang terhadap modal)",
                arti="Total utang ÷ modal sendiri. DER 0,5x = utang setengah dari modal. Makin tinggi, makin berat beban bunga & risikonya.",
                patokan="≤ 0,5x sehat · 0,5–1,5x wajar · > 1,5x tinggi. Tidak dipakai untuk bank (simpanan nasabah tercatat sebagai utang)."),
    "Current ratio": dict(nama="Rasio lancar",
                          arti="Aset lancar ÷ utang lancar. Kemampuan membayar kewajiban yang jatuh tempo dalam 1 tahun.",
                          patokan="≥ 1,5x sehat · 1–1,5x cukup · < 1x ketat. Tidak dipakai untuk bank."),
    "EPS": dict(nama="Earnings per Share (laba per saham)",
                arti="Laba bersih ÷ jumlah saham beredar. Jatah laba untuk setiap lembar saham.",
                patokan="Positif = untung, negatif = rugi. Yang dicari: EPS naik dari tahun ke tahun."),
    # --- Valuasi
    "Valuasi": dict(nama="Penilaian murah/mahal",
                    arti="Membandingkan harga saham dengan laba (PER) dan nilai buku (PBV) perusahaan.",
                    patokan="Skor tinggi = relatif murah. Saham bagus jarang murah — bandingkan dengan peer."),
    "PER": dict(nama="Price to Earnings Ratio",
                arti="Harga ÷ EPS. Berapa kali laba setahun yang Anda bayar. PER 10x ≈ butuh 10 tahun laba (jika laba tetap) "
                     "untuk 'balik modal'.",
                patokan="< 12x murah · 12–25x wajar · > 25x mahal. Kosong/negatif = perusahaan rugi."),
    "PBV": dict(nama="Price to Book Value",
                arti="Harga ÷ nilai buku (modal) per saham. PBV 1x = harga sama dengan nilai bersih aset perusahaan.",
                patokan="< 1,5x murah · 1,5–4x wajar · > 4x mahal. Perusahaan dengan ROE tinggi wajar ber-PBV tinggi."),
    # --- Dividen
    "Dividen": dict(nama="Dividen",
                    arti="Bagian laba yang dibagikan tunai kepada pemegang saham, biasanya setahun sekali atau dua kali (interim & final).",
                    patokan="—"),
    "Dividend yield": dict(nama="Imbal hasil dividen",
                           arti="Total dividen 12 bulan terakhir ÷ harga sekarang. Mirip 'bunga' tahunan dari memegang saham.",
                           patokan="≥ 5% tinggi (di atas bunga deposito) · 2–5% sedang · < 1% kecil."),
    "DPS": dict(nama="Dividend per Share (dividen per saham)",
                arti="Rupiah dividen yang diterima untuk setiap lembar saham.",
                patokan="Contoh: DPS Rp200 × 1 lot (100 lembar) = Rp20.000."),
    "Payout ratio": dict(nama="Rasio pembagian dividen",
                         arti="Dividen ÷ laba bersih. Porsi laba yang dibagikan; sisanya ditahan untuk ekspansi.",
                         patokan="30–70% ideal · > 100% berarti membagi melebihi laba (tidak bisa bertahan lama)."),
    "Konsistensi dividen": dict(nama="Rutin dibagikan",
                                arti="Berapa tahun dari 5 tahun terakhir perusahaan membagikan dividen.",
                                patokan="5/5 sangat rutin · ≤ 2/5 tidak bisa diandalkan."),
    "CAGR": dict(nama="Compound Annual Growth Rate",
                 arti="Rata-rata pertumbuhan per tahun yang 'majemuk' (berbunga), di sini untuk dividen 3 tahun.",
                 patokan="Positif = dividen makin besar dari tahun ke tahun."),
    # --- Tren / teknikal
    "Candle": dict(nama="Candlestick (grafik lilin)",
                   arti="Satu batang yang merangkum 4 harga dalam satu periode: Open, High, Low, Close. "
                        "Hijau = naik (close > open), merah = turun (close < open).",
                   patokan="Lihat panduan '🕯️ Cara membaca grafik candle' di tab Tren."),
    "OHLC": dict(nama="Open · High · Low · Close",
                 arti="Harga pembukaan, tertinggi, terendah, dan penutupan dalam satu periode (di sini: 1 hari bursa).",
                 patokan="—"),
    "MA": dict(nama="Moving Average (rata-rata bergerak)",
               arti="Rata-rata harga penutupan N hari terakhir yang terus bergeser setiap hari. Menghaluskan grafik "
                    "sehingga arah tren lebih jelas.",
               patokan="Harga di atas MA = cenderung naik; di bawah MA = cenderung turun."),
    "MA20": dict(nama="Moving Average 20 hari",
                 arti="Rata-rata 20 hari bursa (± 1 bulan). Menggambarkan tren jangka pendek.",
                 patokan="MA20 di atas MA50 = momentum jangka pendek menguat."),
    "MA50": dict(nama="Moving Average 50 hari",
                 arti="Rata-rata 50 hari bursa (± 2,5 bulan). Tren jangka menengah.",
                 patokan="Sering jadi area 'support' (penahan turun) saat tren naik."),
    "MA200": dict(nama="Moving Average 200 hari",
                  arti="Rata-rata 200 hari bursa (± 1 tahun). Patokan tren jangka panjang yang paling populer.",
                  patokan="Harga di atas MA200 & MA200 menanjak = uptrend jangka panjang."),
    "Golden / death cross": dict(nama="Persilangan MA",
                                 arti="Golden cross: MA pendek (MA50) memotong ke atas MA panjang (MA200) → sinyal tren naik. "
                                      "Death cross: memotong ke bawah → sinyal tren turun.",
                                 patokan="Sinyal lambat, lebih untuk konfirmasi daripada waktu beli."),
    "RSI": dict(nama="Relative Strength Index (14 hari)",
                arti="Indikator kecepatan naik-turun harga, skala 0–100.",
                patokan="≥ 70 jenuh beli (overbought, rawan koreksi) · ≤ 30 jenuh jual (oversold, bisa memantul) · 30–70 netral."),
    "Jenuh beli / jenuh jual": dict(nama="Overbought / oversold",
                                    arti="Jenuh beli: harga naik terlalu cepat sehingga rawan turun sementara. "
                                         "Jenuh jual: turun terlalu dalam sehingga berpotensi memantul.",
                                    patokan="Dibaca dari RSI ≥ 70 atau ≤ 30."),
    "Uptrend / downtrend / sideways": dict(nama="Arah tren",
                                           arti="Uptrend: puncak & lembah makin tinggi. Downtrend: makin rendah. "
                                                "Sideways: bergerak mendatar dalam rentang tertentu.",
                                           patokan="—"),
    "Momentum": dict(nama="Momentum harga",
                     arti="Kekuatan & kecepatan pergerakan harga belakangan ini (di sini: 1 bulan terakhir dan MA20 vs MA50).",
                     patokan="—"),
    "Koreksi": dict(nama="Koreksi harga",
                    arti="Penurunan harga sementara (biasanya 5–20%) di tengah tren naik.",
                    patokan="—"),
    "Support / resistance": dict(nama="Area penahan harga",
                                 arti="Support: area harga di mana penurunan sering tertahan (banyak pembeli). "
                                      "Resistance: area di mana kenaikan sering tertahan (banyak penjual).",
                                 patokan="MA50/MA200 dan harga terendah/tertinggi sebelumnya sering menjadi support/resistance."),
    "Return": dict(nama="Imbal hasil harga",
                   arti="Persentase kenaikan/penurunan harga dalam suatu periode (belum termasuk dividen).",
                   patokan="—"),
    "YTD": dict(nama="Year to Date",
                arti="Perubahan harga sejak penutupan akhir tahun lalu sampai hari ini.",
                patokan="—"),
    "Rentang 52 minggu": dict(nama="52-week range",
                              arti="Harga terendah dan tertinggi dalam 1 tahun terakhir. Posisi 0% = di titik terendah, 100% = di puncak.",
                              patokan="—"),
    "Kinerja relatif": dict(nama="Perbandingan return",
                            arti="Semua saham dimulai dari 0% pada hari yang sama, sehingga kenaikan/penurunannya bisa dibandingkan "
                                 "walau harganya berbeda jauh.",
                            patokan="—"),
    # --- Hasil
    "Skor": dict(nama="Skor 0–100 aplikasi ini",
                 arti="Penilaian otomatis dari aturan sederhana. Skor total = Fundamental 35% + Valuasi 20% + Dividen 15% + Tren 30%.",
                 patokan="BELI ≥ 65 · TAHAN 45–64 · JUAL < 45."),
    "BELI / TAHAN / JUAL": dict(nama="Rekomendasi sistem",
                                arti="BELI: skor tinggi di banyak aspek. TAHAN: campuran — pegang jika sudah punya, tunggu jika belum. "
                                     "JUAL: banyak kelemahan. DATA KURANG: data fundamental tidak tersedia.",
                                patokan="Bahan belajar, bukan nasihat investasi."),
}


def tip(key: str) -> str:
    """Teks tooltip (ikon ⓘ) untuk sebuah istilah."""
    g = GLOSARIUM[key]
    teks = f"**{key}** — {g['nama']}.\n\n{g['arti']}"
    if g["patokan"] != "—":
        teks += f"\n\n*Patokan:* {g['patokan']}"
    return teks


def catatan_kaki(keys: list[str], judul: str = "📘 Catatan kaki: arti istilah di bagian ini") -> None:
    """Daftar istilah bernomor di bawah setiap bagian (hanya tampil saat Mode belajar aktif)."""
    if not st.session_state.get("belajar", True):
        return
    with st.expander(judul):
        baris = []
        for i, k in enumerate(keys, 1):
            g = GLOSARIUM[k]
            s = f"{i}. **{k}** — *{g['nama']}*. {g['arti']}"
            if g["patokan"] != "—":
                s += f"  \n   ↳ *Patokan:* {g['patokan']}"
            baris.append(s)
        st.markdown("\n".join(baris))


# ---------------------------------------------------------------------------
# Utilitas
# ---------------------------------------------------------------------------
def normalize_ticker(raw: str, idx_default: bool = True) -> str:
    t = raw.strip().upper()
    if not t:
        return t
    if idx_default and "." not in t and "^" not in t and "=" not in t:
        t += ".JK"
    return t


def base_code(ticker: str) -> str:
    return ticker.split(".")[0].upper()


def find_peers(ticker: str) -> tuple[str | None, list[str]]:
    code = base_code(ticker)
    for group, members in PEER_GROUPS.items():
        if code in members:
            return group, [m for m in members if m != code]
    return None, []


def num(x) -> float | None:
    """Ubah ke float; None jika kosong/NaN/tak valid."""
    try:
        if x is None:
            return None
        v = float(x)
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    except (TypeError, ValueError):
        return None


def scale(x: float | None, bad: float, good: float) -> float | None:
    """Skor 0–100 linier: nilai 'bad' -> 0, 'good' -> 100 (bisa terbalik)."""
    if x is None:
        return None
    if good == bad:
        return 50.0
    s = (x - bad) / (good - bad) * 100
    return float(max(0.0, min(100.0, s)))


def avg(values) -> float | None:
    vals = [v for v in values if v is not None]
    return float(np.mean(vals)) if vals else None


def weighted(parts: list[tuple[float | None, float]]) -> float | None:
    avail = [(s, w) for s, w in parts if s is not None]
    if not avail:
        return None
    tw = sum(w for _, w in avail)
    return sum(s * w for s, w in avail) / tw


def fmt_pct(x, digits=1) -> str:
    return "–" if x is None else f"{x * 100:.{digits}f}%".replace(".", ",")


def fmt_num(x, digits=2) -> str:
    return "–" if x is None else f"{x:,.{digits}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def fmt_price(x, currency="IDR") -> str:
    if x is None:
        return "–"
    if currency == "IDR":
        return "Rp " + f"{x:,.0f}".replace(",", ".")
    return f"{currency} {x:,.2f}"


def fmt_big(x, currency="IDR") -> str:
    if x is None:
        return "–"
    for div, suf in [(1e12, " T"), (1e9, " M"), (1e6, " Jt")]:
        if abs(x) >= div:
            v = f"{x / div:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
            return ("Rp " if currency == "IDR" else currency + " ") + v + suf
    return fmt_price(x, currency)


def _resample(series: pd.Series, rule_new: str, rule_old: str) -> pd.Series:
    try:
        return series.resample(rule_new).last()
    except (ValueError, KeyError):
        return series.resample(rule_old).last()


def rsi(close: pd.Series, period: int = 14) -> float | None:
    if len(close) < period + 1:
        return None
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    val = 100 - 100 / (1 + rs.iloc[-1])
    return num(val) if not pd.isna(val) else 100.0


# ---------------------------------------------------------------------------
# Ambil data (di-cache 1 jam agar tidak membebani Yahoo)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def fetch(ticker: str) -> dict:
    t = yf.Ticker(ticker)
    try:
        info = t.info or {}
    except Exception:  # noqa: BLE001
        info = {}
    try:
        hist = t.history(period="5y", interval="1d", auto_adjust=True)
    except Exception:  # noqa: BLE001
        hist = pd.DataFrame()
    try:
        divs = t.dividends
    except Exception:  # noqa: BLE001
        divs = pd.Series(dtype=float)
    if hist is not None and not hist.empty and getattr(hist.index, "tz", None) is not None:
        hist.index = hist.index.tz_localize(None)
    if divs is not None and not divs.empty and getattr(divs.index, "tz", None) is not None:
        divs.index = divs.index.tz_localize(None)
    return {"info": info, "hist": hist, "divs": divs}


# ---------------------------------------------------------------------------
# Analisis
# ---------------------------------------------------------------------------
def analyze(ticker: str) -> dict | None:
    data = fetch(ticker)
    info, hist, divs = data["info"], data["hist"], data["divs"]
    if hist is None or hist.empty or "Close" not in hist:
        return None

    close = hist["Close"].dropna()
    if close.empty:
        return None
    price = num(info.get("currentPrice")) or num(info.get("regularMarketPrice")) or float(close.iloc[-1])
    currency = info.get("currency") or "IDR"
    sector = info.get("sector") or "-"
    industry = info.get("industry") or "-"
    is_fin = sector in FINANCIAL_SECTORS or "bank" in str(industry).lower()

    # ---- 1. Fundamental -------------------------------------------------
    roe = num(info.get("returnOnEquity"))
    roa = num(info.get("returnOnAssets"))
    npm = num(info.get("profitMargins"))
    rev_g = num(info.get("revenueGrowth"))
    eps_g = num(info.get("earningsGrowth"))
    der = num(info.get("debtToEquity"))  # dalam persen, mis. 45 = 0,45x
    cur = num(info.get("currentRatio"))

    f_scores = {
        "ROE": scale(roe, 0.05, 0.20),
        "ROA": scale(roa, 0.005, 0.025) if is_fin else scale(roa, 0.02, 0.10),
        "Margin laba bersih": scale(npm, 0.02, 0.25),
        "Pertumbuhan pendapatan": scale(rev_g, -0.05, 0.15),
        "Pertumbuhan laba": scale(eps_g, -0.10, 0.20),
    }
    if not is_fin:  # DER & current ratio kurang relevan untuk bank
        f_scores["Rasio utang (DER)"] = scale(der, 200, 30)
        f_scores["Current ratio"] = scale(cur, 0.8, 2.0)
    fund_score = avg(f_scores.values())

    # ---- Valuasi ---------------------------------------------------------
    pe = num(info.get("trailingPE"))
    pbv = num(info.get("priceToBook"))
    eps = num(info.get("trailingEps"))
    if pe is None and eps is not None and eps <= 0:
        pe_score = 10.0  # rugi
    else:
        pe_score = scale(pe, 30, 8) if (pe is not None and pe > 0) else None
    val_scores = {"PER": pe_score, "PBV": scale(pbv, 5, 1)}
    val_score = avg(val_scores.values())

    # ---- 2. Dividen -----------------------------------------------------
    last_date = close.index[-1]
    div_ttm = 0.0
    div_by_year = pd.Series(dtype=float)
    if divs is not None and not divs.empty:
        div_ttm = float(divs[divs.index > last_date - timedelta(days=365)].sum())
        div_by_year = divs.groupby(divs.index.year).sum()
    div_yield = div_ttm / price if price else None
    payout = num(info.get("payoutRatio"))
    this_year = last_date.year
    last5 = [y for y in range(this_year - 5, this_year)]
    years_paid = sum(1 for y in last5 if y in div_by_year.index and div_by_year[y] > 0)
    consistency = years_paid / 5

    if payout is None:
        payout_score = None
    elif payout <= 0:
        payout_score = 0.0
    elif 0.3 <= payout <= 0.7:
        payout_score = 100.0
    elif payout < 0.3:
        payout_score = scale(payout, 0.0, 0.3)
    elif payout <= 1.0:
        payout_score = scale(payout, 1.0, 0.7)
    else:
        payout_score = 10.0  # membagi lebih dari laba -> tidak berkelanjutan
    div_score = weighted([
        (scale(div_yield, 0.0, 0.06), 0.5),
        (consistency * 100, 0.3),
        (payout_score, 0.2),
    ])

    # Pertumbuhan dividen (CAGR 3 tahun penuh terakhir)
    div_cagr = None
    y_end, y_start = this_year - 1, this_year - 4
    if y_end in div_by_year.index and y_start in div_by_year.index and div_by_year[y_start] > 0:
        div_cagr = (div_by_year[y_end] / div_by_year[y_start]) ** (1 / 3) - 1

    # ---- 3. Tren --------------------------------------------------------
    ma20 = close.rolling(20).mean()
    ma50 = close.rolling(50).mean()
    ma200 = close.rolling(200).mean()

    def ret_over(days: int) -> float | None:
        past = close[close.index <= last_date - timedelta(days=days)]
        return float(close.iloc[-1] / past.iloc[-1] - 1) if not past.empty else None

    r1m, r3m, r6m, r1y, r3y = (ret_over(d) for d in (30, 91, 182, 365, 1095))
    ytd_base = close[close.index < datetime(this_year, 1, 1)]
    ytd = float(close.iloc[-1] / ytd_base.iloc[-1] - 1) if not ytd_base.empty else None

    last_1y = close[close.index > last_date - timedelta(days=365)]
    hi52, lo52 = float(last_1y.max()), float(last_1y.min())
    pos52 = (close.iloc[-1] - lo52) / (hi52 - lo52) if hi52 > lo52 else None

    above200 = num(ma200.iloc[-1]) is not None and close.iloc[-1] > ma200.iloc[-1]
    ma200_slope = None
    if len(ma200.dropna()) > 21:
        ma200_slope = float(ma200.iloc[-1] / ma200.iloc[-21] - 1)
    ma20_above_50 = num(ma50.iloc[-1]) is not None and ma20.iloc[-1] > ma50.iloc[-1]
    rsi14 = rsi(close)

    def trend_label(ret, up_flag, thr):
        if ret is None:
            return "–"
        if ret > thr and up_flag:
            return "Naik (uptrend)"
        if ret < -thr and not up_flag:
            return "Turun (downtrend)"
        return "Sideways / campuran"

    yearly_trend = trend_label(r1y, above200, 0.10)
    monthly_trend = trend_label(r1m, ma20_above_50, 0.03)

    yearly_score = avg([
        scale(r1y, -0.20, 0.30),
        100.0 if above200 else 0.0,
        scale(ma200_slope, -0.03, 0.03),
    ])
    rsi_score = None if rsi14 is None else max(0.0, 100 - abs(rsi14 - 55) * 2.2)
    monthly_score = avg([
        scale(r1m, -0.08, 0.08),
        100.0 if ma20_above_50 else 0.0,
        rsi_score,
    ])
    trend_score = weighted([(yearly_score, 0.6), (monthly_score, 0.4)])

    annual_ret = _resample(close, "YE", "Y").pct_change().dropna()
    annual_ret.index = annual_ret.index.year
    monthly_ret = _resample(close, "ME", "M").pct_change().dropna().tail(12)

    # ---- 4. Skor total & rekomendasi -----------------------------------
    total = weighted([
        (fund_score, 0.35),
        (val_score, 0.20),
        (div_score, 0.15),
        (trend_score, 0.30),
    ])
    if total is None or fund_score is None:
        reco = "DATA KURANG"
    elif total >= 65:
        reco = "BELI"
    elif total >= 45:
        reco = "TAHAN"
    else:
        reco = "JUAL"

    # Alasan (kekuatan & kelemahan)
    pros, cons = [], []
    if roe is not None:
        (pros if roe >= 0.15 else cons if roe < 0.08 else []).append(f"ROE {fmt_pct(roe)}")
    if npm is not None:
        (pros if npm >= 0.15 else cons if npm < 0.05 else []).append(f"margin laba bersih {fmt_pct(npm)}")
    if eps_g is not None:
        (pros if eps_g >= 0.10 else cons if eps_g < 0 else []).append(f"pertumbuhan laba {fmt_pct(eps_g)}")
    if not is_fin and der is not None:
        (pros if der <= 50 else cons if der > 150 else []).append(f"DER {der / 100:.2f}x")
    if pe is not None and pe > 0:
        (pros if pe <= 12 else cons if pe > 25 else []).append(f"PER {pe:.1f}x")
    elif eps is not None and eps <= 0:
        cons.append("perusahaan sedang rugi (EPS negatif)")
    if pbv is not None:
        (pros if pbv <= 1.5 else cons if pbv > 4 else []).append(f"PBV {pbv:.2f}x")
    if div_yield is not None:
        (pros if div_yield >= 0.04 else cons if div_yield < 0.01 else []).append(f"dividend yield {fmt_pct(div_yield)}")
    if consistency >= 0.8:
        pros.append(f"rutin bagi dividen ({years_paid}/5 tahun)")
    elif consistency <= 0.4:
        cons.append(f"dividen tidak rutin ({years_paid}/5 tahun)")
    if payout is not None and payout > 1:
        cons.append(f"payout ratio {fmt_pct(payout, 0)} (> laba)")
    if yearly_trend.startswith("Naik"):
        pros.append("tren tahunan naik (di atas MA200)")
    elif yearly_trend.startswith("Turun"):
        cons.append("tren tahunan turun (di bawah MA200)")
    if monthly_trend.startswith("Naik"):
        pros.append("momentum bulanan positif")
    elif monthly_trend.startswith("Turun"):
        cons.append("momentum bulanan negatif")
    if rsi14 is not None and rsi14 >= 70:
        cons.append(f"RSI {rsi14:.0f} (jenuh beli, rawan koreksi)")
    elif rsi14 is not None and rsi14 <= 30:
        pros.append(f"RSI {rsi14:.0f} (jenuh jual, potensi pantul)")

    return {
        "ticker": ticker,
        "code": base_code(ticker),
        "name": info.get("longName") or info.get("shortName") or ticker,
        "sector": sector,
        "industry": industry,
        "is_fin": is_fin,
        "currency": currency,
        "price": price,
        "market_cap": num(info.get("marketCap")),
        "hist": hist,
        "close": close,
        "ma20": ma20, "ma50": ma50, "ma200": ma200,
        # fundamental
        "roe": roe, "roa": roa, "npm": npm, "rev_g": rev_g, "eps_g": eps_g,
        "der": der, "cur": cur, "pe": pe, "pbv": pbv, "eps": eps,
        "f_scores": f_scores, "fund_score": fund_score,
        "val_scores": val_scores, "val_score": val_score,
        # dividen
        "div_ttm": div_ttm, "div_yield": div_yield, "payout": payout,
        "years_paid": years_paid, "div_by_year": div_by_year, "div_cagr": div_cagr,
        "div_score": div_score,
        # tren
        "r1m": r1m, "r3m": r3m, "r6m": r6m, "r1y": r1y, "r3y": r3y, "ytd": ytd,
        "hi52": hi52, "lo52": lo52, "pos52": pos52, "rsi": rsi14,
        "above200": above200, "ma20_above_50": ma20_above_50,
        "yearly_trend": yearly_trend, "monthly_trend": monthly_trend,
        "yearly_score": yearly_score, "monthly_score": monthly_score,
        "trend_score": trend_score,
        "annual_ret": annual_ret, "monthly_ret": monthly_ret,
        # hasil
        "total": total, "reco": reco, "pros": pros, "cons": cons,
    }


def summary_text(a: dict) -> str:
    parts = [f"**{a['name']} ({a['code']})** bergerak di sektor {a['sector']} / {a['industry']}."]
    fs = a["fund_score"]
    if fs is not None:
        lvl = "kuat" if fs >= 65 else "cukup" if fs >= 45 else "lemah"
        parts.append(f"Fundamental keuangan tergolong **{lvl}** (skor {fs:.0f}/100) dengan ROE {fmt_pct(a['roe'])} "
                     f"dan margin laba bersih {fmt_pct(a['npm'])}.")
    if a["val_score"] is not None:
        lvl = "murah" if a["val_score"] >= 65 else "wajar" if a["val_score"] >= 40 else "mahal"
        parts.append(f"Valuasi relatif **{lvl}** (PER {fmt_num(a['pe'], 1)}x, PBV {fmt_num(a['pbv'])}x).")
    parts.append(f"Dividend yield 12 bulan terakhir {fmt_pct(a['div_yield'], 2)}, "
                 f"dibagikan {a['years_paid']} dari 5 tahun terakhir.")
    parts.append(f"Tren tahunan: **{a['yearly_trend']}** (1 tahun {fmt_pct(a['r1y'])}); "
                 f"tren bulanan: **{a['monthly_trend']}** (1 bulan {fmt_pct(a['r1m'])}).")
    if a["total"] is not None:
        parts.append(f"Skor total **{a['total']:.0f}/100** → rekomendasi sistem: **{a['reco']}**.")
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Tampilan
# ---------------------------------------------------------------------------
RECO_COLOR = {"BELI": "#1a9850", "TAHAN": "#f39c12", "JUAL": "#d73027", "DATA KURANG": "#7f8c8d"}


def penilaian(skor) -> str:
    if skor is None or pd.isna(skor):
        return "–"
    return "👍 baik" if skor >= 70 else "😐 sedang" if skor >= 40 else "👎 lemah"


def score_badge(label: str, score: float | None, help: str | None = None) -> None:
    val = "–" if score is None else f"{score:.0f}"
    st.metric(label, f"{val} / 100", help=help)
    if score is not None:
        st.progress(int(round(score)) / 100)


def price_chart(a: dict, period_days: int) -> go.Figure:
    start = a["close"].index[-1] - timedelta(days=period_days)
    h = a["hist"][a["hist"].index >= start]
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=h.index, open=h["Open"], high=h["High"], low=h["Low"], close=h["Close"],
                                 name="Harga (candle harian)", increasing_line_color=HIJAU, decreasing_line_color=MERAH))
    for col, name, color in [("ma20", "MA20", "#3498db"), ("ma50", "MA50", "#9b59b6"), ("ma200", "MA200", "#e67e22")]:
        s = a[col][a[col].index >= start]
        fig.add_trace(go.Scatter(x=s.index, y=s, name=name, line=dict(width=1.4, color=color)))
    fig.update_layout(height=420, margin=dict(l=10, r=10, t=30, b=10), xaxis_rangeslider_visible=False,
                      legend=dict(orientation="h", y=1.08))
    return fig


# ---------------------------------------------------------------------------
# Panduan membaca grafik candle
# ---------------------------------------------------------------------------
HIJAU, MERAH = "#1a9850", "#d73027"


def candle_anatomy_chart() -> go.Figure:
    """Gambar 2 candle (naik & turun) dengan label bagian-bagiannya."""
    naik, turun = "Candle NAIK (hijau)", "Candle TURUN (merah)"
    fig = go.Figure(go.Candlestick(
        x=[naik, turun], open=[100, 140], high=[155, 155], low=[85, 85], close=[140, 100],
        increasing_line_color=HIJAU, decreasing_line_color=MERAH, showlegend=False, hoverinfo="skip"))
    label = [
        (naik, 155, "<b>High</b> — harga tertinggi hari itu", -1),
        (naik, 147, "Sumbu atas (upper shadow / wick)", -1),
        (naik, 140, "<b>Close</b> — harga penutupan (di ATAS)", -1),
        (naik, 120, "<b>Badan (body)</b> — jarak Open↔Close", -1),
        (naik, 100, "<b>Open</b> — harga pembukaan (di BAWAH)", -1),
        (naik, 85, "<b>Low</b> — harga terendah hari itu", -1),
        (turun, 140, "<b>Open</b> — pembukaan (di ATAS)", 1),
        (turun, 120, "Badan merah = harga turun", 1),
        (turun, 100, "<b>Close</b> — penutupan (di BAWAH)", 1),
        (turun, 92, "Sumbu bawah (lower shadow)", 1),
    ]
    for x, y, teks, sisi in label:
        fig.add_annotation(x=x, y=y, text=teks, showarrow=True, arrowhead=2, arrowwidth=1,
                           ax=150 * sisi, ay=0,
                           xanchor="left" if sisi > 0 else "right", font=dict(size=12))
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10), xaxis_rangeslider_visible=False,
                      yaxis=dict(visible=False, range=[75, 165]), xaxis=dict(fixedrange=True),
                      dragmode=False)
    return fig


POLA_CANDLE = [
    # nama, OHLC (bisa 2 candle), arti
    ("Doji", [(100, 112, 88, 100.5)],
     "Open ≈ Close, badan sangat tipis. Pembeli & penjual seimbang → pasar ragu-ragu. "
     "Setelah tren panjang, bisa menandakan tren melemah."),
    ("Hammer", [(108, 111, 80, 110)],
     "Badan kecil di atas, sumbu bawah panjang (≥ 2× badan). Harga sempat jatuh, lalu pembeli mendorong naik lagi. "
     "Jika muncul setelah penurunan → potensi berbalik naik."),
    ("Shooting star", [(92, 120, 89, 90)],
     "Kebalikan hammer: badan kecil di bawah, sumbu atas panjang. Harga sempat naik tinggi lalu ditekan penjual. "
     "Jika muncul setelah kenaikan → potensi berbalik turun."),
    ("Marubozu", [(88, 112, 88, 112)],
     "Badan penuh tanpa (atau hampir tanpa) sumbu. Satu pihak menguasai pasar sepanjang hari "
     "(hijau = pembeli sangat kuat, merah = penjual sangat kuat)."),
    ("Bullish engulfing", [(104, 106, 95, 97), (95, 112, 93, 110)],
     "Candle hijau besar 'menelan' seluruh badan candle merah sebelumnya. Sinyal pembalikan naik, "
     "terutama setelah penurunan. Kebalikannya: bearish engulfing."),
]


def candle_patterns_chart() -> go.Figure:
    xs, o, h, l, c = [], [], [], [], []
    for nama, candles, _ in POLA_CANDLE:
        for i, (co, ch, cl, cc) in enumerate(candles):
            xs.append(nama if len(candles) == 1 else f"{nama} ({i + 1})")
            o.append(co), h.append(ch), l.append(cl), c.append(cc)
    fig = go.Figure(go.Candlestick(x=xs, open=o, high=h, low=l, close=c, showlegend=False,
                                   increasing_line_color=HIJAU, decreasing_line_color=MERAH))
    fig.update_layout(height=260, margin=dict(l=10, r=10, t=10, b=10), xaxis_rangeslider_visible=False,
                      yaxis=dict(visible=False), xaxis=dict(fixedrange=True), dragmode=False)
    return fig


def baca_candle_terakhir(a: dict) -> list[str]:
    """Membaca candle hari terakhir secara otomatis, dengan bahasa sederhana."""
    h = a["hist"].dropna(subset=["Open", "High", "Low", "Close"])
    if len(h) < 2:
        return []
    cur, prev = h.iloc[-1], h.iloc[-2]
    o, hi, lo, c = (float(cur[k]) for k in ("Open", "High", "Low", "Close"))
    rentang = hi - lo
    badan = abs(c - o)
    atas = hi - max(o, c)
    bawah = min(o, c) - lo
    cur_fmt = lambda v: fmt_price(v, a["currency"])  # noqa: E731
    tgl = h.index[-1].strftime("%d %b %Y")
    out = []
    if c > o:
        out.append(f"Candle **{tgl}** berwarna **hijau (naik)**: dibuka {cur_fmt(o)}, ditutup lebih tinggi di {cur_fmt(c)}.")
    elif c < o:
        out.append(f"Candle **{tgl}** berwarna **merah (turun)**: dibuka {cur_fmt(o)}, ditutup lebih rendah di {cur_fmt(c)}.")
    else:
        out.append(f"Candle **{tgl}**: harga ditutup sama dengan harga pembukaan ({cur_fmt(c)}).")
    out.append(f"Rentang hari itu {cur_fmt(lo)} (Low) – {cur_fmt(hi)} (High).")

    if rentang > 0:
        r_badan = badan / rentang
        if r_badan < 0.1:
            out.append("Badannya sangat tipis → mirip **Doji**: pasar ragu-ragu, belum ada pemenang antara pembeli dan penjual.")
        elif bawah >= 2 * badan and atas <= max(badan, rentang * 0.1):
            out.append("Sumbu bawah panjang → mirip **Hammer**: harga sempat ditekan, tapi pembeli berhasil mendorongnya naik lagi.")
        elif atas >= 2 * badan and bawah <= max(badan, rentang * 0.1):
            out.append("Sumbu atas panjang → mirip **Shooting star**: harga sempat naik tinggi, tapi penjual menekannya turun lagi.")
        elif r_badan >= 0.9:
            out.append("Badannya hampir penuh tanpa sumbu → **Marubozu**: "
                       + ("pembeli menguasai hari itu." if c > o else "penjual menguasai hari itu."))
        po, pc = float(prev["Open"]), float(prev["Close"])
        if pc < po and c > o and c >= po and o <= pc:
            out.append("Candle hijau ini menelan candle merah sebelumnya → **Bullish engulfing** (sinyal pembalikan naik).")
        elif pc > po and c < o and o >= pc and c <= po:
            out.append("Candle merah ini menelan candle hijau sebelumnya → **Bearish engulfing** (sinyal pembalikan turun).")
        rata2 = float((h["High"] - h["Low"]).tail(20).mean())
        if rata2 > 0:
            if rentang > 1.5 * rata2:
                out.append("Rentangnya **lebih lebar** dari rata-rata 20 hari → pergerakan hari itu cukup bergejolak.")
            elif rentang < 0.5 * rata2:
                out.append("Rentangnya **lebih sempit** dari rata-rata 20 hari → pasar sedang tenang.")

    posisi = []
    for key, nama in (("ma20", "MA20"), ("ma50", "MA50"), ("ma200", "MA200")):
        v = num(a[key].iloc[-1])
        if v is not None:
            posisi.append(f"{'di atas' if c > v else 'di bawah'} {nama}")
    if posisi:
        out.append("Harga penutupan berada " + ", ".join(posisi) + ".")
    return out


def bar_chart(series: pd.Series, title: str, pct: bool = True) -> go.Figure:
    colors = ["#1a9850" if v >= 0 else "#d73027" for v in series.values]
    y = series.values * 100 if pct else series.values
    x = [str(i) if not isinstance(i, pd.Timestamp) else i.strftime("%b %Y") for i in series.index]
    fig = go.Figure(go.Bar(x=x, y=y, marker_color=colors,
                           text=[f"{v:.1f}%" if pct else fmt_num(v, 0) for v in y], textposition="outside"))
    fig.update_layout(title=title, height=320, margin=dict(l=10, r=10, t=40, b=10),
                      yaxis_title="%" if pct else None)
    return fig


def main() -> None:
    st.set_page_config(page_title="Resume Saham", page_icon="📈", layout="wide")
    st.title("📈 Resume Saham")
    st.caption("Ringkasan fundamental, dividen, tren, dan rekomendasi — dibandingkan dengan saham sejenis. "
               "Data: Yahoo Finance (bisa tertunda ±15 menit).")

    with st.sidebar:
        st.header("Pengaturan")
        raw = st.text_input("Kode saham", value="BBCA", help="Contoh: BBCA, TLKM, ASII. "
                                                               "Untuk saham luar negeri, matikan opsi di bawah (mis. AAPL).")
        idx = st.checkbox("Saham BEI (tambah .JK otomatis)", value=True)
        ticker = normalize_ticker(raw, idx)
        group, default_peers = find_peers(ticker)
        if group:
            st.caption(f"Kelompok peer: **{group}**")
        peers_raw = st.text_input("Saham pembanding (pisahkan koma)", value=", ".join(default_peers[:5]),
                                  help="Kosongkan atau ubah sesuai keinginan.")
        chart_period = st.radio("Periode grafik", ["6 bulan", "1 tahun", "3 tahun", "5 tahun"], index=1,
                                horizontal=True)
        run = st.button("Analisis", type="primary", width="stretch")
        st.divider()
        st.markdown("**Bobot skor total**  \nFundamental 35% · Valuasi 20% · Dividen 15% · Tren 30%  \n"
                    "**BELI** ≥ 65 · **TAHAN** 45–64 · **JUAL** < 45")
        st.divider()
        st.toggle("🎓 Mode belajar", value=True, key="belajar",
                  help="Tampilkan kolom penjelasan di sebelah angka dan catatan kaki istilah di setiap bagian.")
        st.markdown("**📘 Cari arti istilah**")
        istilah = st.selectbox("Istilah / singkatan", sorted(GLOSARIUM, key=str.lower), index=None,
                               placeholder="Pilih, mis. PER atau RSI", label_visibility="collapsed")
        if istilah:
            st.info(tip(istilah))
        st.caption("Arahkan kursor / ketuk ikon ⓘ di samping angka untuk penjelasan singkat.")

    if not ticker:
        st.info("Masukkan kode saham di panel kiri.")
        return
    if not run and "last_ticker" not in st.session_state:
        st.info("Masukkan kode saham lalu klik **Analisis**.")
        return
    if run:
        st.session_state["last_ticker"] = ticker
        st.session_state["last_peers"] = peers_raw
    ticker = st.session_state["last_ticker"]
    peers_raw = st.session_state.get("last_peers", peers_raw)

    with st.spinner(f"Mengambil data {ticker}…"):
        a = analyze(ticker)
    if a is None:
        st.error(f"Data untuk **{ticker}** tidak ditemukan. Periksa kode saham atau koneksi internet.")
        return

    # ---------------- Header ----------------
    c1, c2, c3, c4 = st.columns([2.2, 1, 1, 1.2])
    with c1:
        st.subheader(f"{a['name']} ({a['code']})")
        st.caption(f"{a['sector']} · {a['industry']}")
    c2.metric("Harga", fmt_price(a["price"], a["currency"]), fmt_pct(a["r1m"]) + " (1 bln)" if a["r1m"] is not None else None,
              help=tip("Harga") + "\n\nAngka kecil di bawahnya = perubahan harga 1 bulan terakhir.")
    c3.metric("Kapitalisasi pasar", fmt_big(a["market_cap"], a["currency"]), help=tip("Kapitalisasi pasar")
              + "\n\nSingkatan: T = triliun, M = miliar, Jt = juta.")
    color = RECO_COLOR[a["reco"]]
    total_txt = "–" if a["total"] is None else f"{a['total']:.0f}/100"
    c4.markdown(
        f"<div style='background:{color};color:white;border-radius:12px;padding:12px 8px;text-align:center'>"
        f"<div style='font-size:13px;opacity:.9'>Rekomendasi sistem</div>"
        f"<div style='font-size:28px;font-weight:700;line-height:1.2'>{a['reco']}</div>"
        f"<div style='font-size:13px'>Skor {total_txt}</div></div>", unsafe_allow_html=True,
        help=tip("BELI / TAHAN / JUAL"))

    st.markdown("#### Ringkasan")
    st.markdown(summary_text(a))
    k1, k2 = st.columns(2)
    with k1:
        st.markdown("**✅ Kekuatan**")
        st.markdown("\n".join(f"- {p}" for p in a["pros"]) or "_Tidak ada yang menonjol._")
    with k2:
        st.markdown("**⚠️ Perhatian**")
        st.markdown("\n".join(f"- {c}" for c in a["cons"]) or "_Tidak ada yang menonjol._")

    s1, s2, s3, s4 = st.columns(4)
    with s1:
        score_badge("Fundamental", a["fund_score"], tip("Fundamental"))
    with s2:
        score_badge("Valuasi", a["val_score"], tip("Valuasi"))
    with s3:
        score_badge("Dividen", a["div_score"], tip("Dividen") + "\n\nSkor = 50% yield + 30% konsistensi + 20% payout ratio.")
    with s4:
        score_badge("Tren", a["trend_score"], "Arah pergerakan harga. Skor = 60% tren tahunan (return 1 th, posisi vs MA200, "
                    "arah MA200) + 40% tren bulanan (return 1 bln, MA20 vs MA50, RSI).")
    catatan_kaki(["ROE", "NPM", "PER", "PBV", "DER", "Dividend yield", "Payout ratio", "MA200", "RSI", "Momentum",
                  "Jenuh beli / jenuh jual", "Uptrend / downtrend / sideways", "Skor", "BELI / TAHAN / JUAL"],
                 "📘 Catatan kaki: arti singkatan di ringkasan")

    tab_f, tab_d, tab_t, tab_p = st.tabs(["🏦 Fundamental", "💰 Dividen", "📊 Tren", "⚖️ Perbandingan"])

    # ---------------- Fundamental ----------------
    with tab_f:
        if a["is_fin"]:
            st.info("Saham sektor keuangan/bank: DER dan current ratio tidak dipakai dalam skor "
                    "karena struktur neraca bank berbeda.")
        rows = [
            ("ROE (laba / ekuitas)", fmt_pct(a["roe"]), "≥ 15% bagus", a["f_scores"].get("ROE"), "ROE"),
            ("ROA (laba / aset)", fmt_pct(a["roa"]), "bank ≥ 2%, non-bank ≥ 8%", a["f_scores"].get("ROA"), "ROA"),
            ("NPM — margin laba bersih", fmt_pct(a["npm"]), "≥ 15% bagus", a["f_scores"].get("Margin laba bersih"), "NPM"),
            ("Pertumbuhan pendapatan (YoY)", fmt_pct(a["rev_g"]), "≥ 10% bagus", a["f_scores"].get("Pertumbuhan pendapatan"),
             "Pertumbuhan pendapatan"),
            ("Pertumbuhan laba (YoY)", fmt_pct(a["eps_g"]), "≥ 10% bagus", a["f_scores"].get("Pertumbuhan laba"),
             "Pertumbuhan laba"),
            ("DER (utang / ekuitas)", "–" if a["der"] is None else f"{a['der'] / 100:.2f}x", "≤ 0,5x sehat",
             a["f_scores"].get("Rasio utang (DER)"), "DER"),
            ("Current ratio", fmt_num(a["cur"]), "≥ 1,5x sehat", a["f_scores"].get("Current ratio"), "Current ratio"),
            ("PER", "–" if a["pe"] is None else f"{a['pe']:.1f}x", "< 12x murah, > 25x mahal", a["val_scores"]["PER"], "PER"),
            ("PBV", "–" if a["pbv"] is None else f"{a['pbv']:.2f}x", "< 1,5x murah, > 4x mahal", a["val_scores"]["PBV"], "PBV"),
            ("EPS (TTM)", fmt_num(a["eps"]), "positif = untung", None, "EPS"),
        ]
        df = pd.DataFrame(rows, columns=["Rasio", "Nilai", "Patokan umum", "Skor", "_key"])
        df["Penilaian"] = df["Skor"].apply(penilaian)
        if a["eps"] is not None:
            df.loc[df["_key"] == "EPS", "Penilaian"] = "👍 untung" if a["eps"] > 0 else "👎 rugi"
        if a["is_fin"]:
            df.loc[df["_key"].isin(["DER", "Current ratio"]), "Penilaian"] = "— tidak dinilai (bank)"
        df["Skor"] = df["Skor"].apply(lambda v: "–" if v is None or pd.isna(v) else f"{v:.0f}")
        df["Artinya"] = df["_key"].apply(lambda k: GLOSARIUM[k]["arti"])
        kolom = ["Rasio", "Nilai", "Penilaian", "Patokan umum", "Skor"]
        if st.session_state.get("belajar", True):
            kolom.append("Artinya")
        st.dataframe(df[kolom], hide_index=True, width="stretch", column_config={
            "Rasio": st.column_config.TextColumn(help="Nama rasio keuangan. Arti lengkapnya ada di kolom 'Artinya' dan catatan kaki."),
            "Nilai": st.column_config.TextColumn(help="Angka terbaru dari Yahoo Finance. x = kali, % = persen."),
            "Penilaian": st.column_config.TextColumn(help="👍 skor ≥ 70 · 😐 40–69 · 👎 < 40"),
            "Patokan umum": st.column_config.TextColumn(help="Batas umum yang sering dipakai analis. Bandingkan juga dengan peer."),
            "Skor": st.column_config.TextColumn(help="Nilai 0–100 untuk rasio ini. Skor Fundamental = rata-rata skor rasio fundamental."),
            "Artinya": st.column_config.TextColumn(width="large", help="Penjelasan singkat untuk belajar."),
        })
        st.caption("Pertumbuhan YoY dari Yahoo Finance biasanya membandingkan kuartal terakhir dengan kuartal yang sama tahun lalu. "
                   "Satuan: **x** = kali (mis. PER 10x = harga 10 kali laba per saham).")
        catatan_kaki(["ROE", "ROA", "NPM", "Pertumbuhan pendapatan", "Pertumbuhan laba", "YoY", "DER", "Current ratio",
                      "PER", "PBV", "EPS", "TTM", "Valuasi", "Peer"])

    # ---------------- Dividen ----------------
    with tab_d:
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("Dividend yield (12 bln)", fmt_pct(a["div_yield"], 2), help=tip("Dividend yield"))
        d2.metric("DPS — dividen per saham (12 bln)", fmt_price(a["div_ttm"], a["currency"]) if a["div_ttm"] else "–",
                  help=tip("DPS"))
        d3.metric("Payout ratio", fmt_pct(a["payout"], 0), help=tip("Payout ratio"))
        d4.metric("Rutin dibagikan", f"{a['years_paid']}/5 tahun", help=tip("Konsistensi dividen"))
        if a["div_cagr"] is not None:
            st.caption(f"Pertumbuhan dividen per tahun (CAGR 3 tahun): **{fmt_pct(a['div_cagr'])}** "
                       "— CAGR = rata-rata pertumbuhan majemuk per tahun.")
        dby = a["div_by_year"]
        if dby is not None and not dby.empty:
            dby = dby[dby.index >= a["close"].index[-1].year - 9]
            st.plotly_chart(bar_chart(dby, "Dividen per saham per tahun", pct=False), width="stretch")
        else:
            st.info("Tidak ada riwayat dividen.")
        st.caption("Yield dihitung dari total dividen 12 bulan terakhir dibagi harga saat ini. "
                   "Payout ideal 30–70%: cukup besar untuk pemegang saham, tetapi masih menyisakan laba untuk ekspansi.")
        if a["div_yield"]:
            st.info(f"💡 Contoh hitungan: memegang 1 lot (100 lembar) {a['code']} seharga "
                    f"{fmt_price(a['price'] * 100, a['currency'])} memberi dividen ± "
                    f"{fmt_price(a['div_ttm'] * 100, a['currency'])} setahun (sebelum pajak dividen).")
        catatan_kaki(["Dividen", "Dividend yield", "DPS", "Payout ratio", "Konsistensi dividen", "CAGR", "TTM"])

    # ---------------- Tren ----------------
    with tab_t:
        days = {"6 bulan": 182, "1 tahun": 365, "3 tahun": 1095, "5 tahun": 1825}[chart_period]
        st.plotly_chart(price_chart(a, days), width="stretch")
        st.caption("Setiap batang (candle) = 1 hari bursa. 🟩 hijau = harga naik hari itu, 🟥 merah = turun. "
                   "Garis: **MA20** (biru, ± 1 bulan), **MA50** (ungu, ± 2,5 bulan), **MA200** (oranye, ± 1 tahun). "
                   "Perbesar dengan menyeret area grafik; klik dua kali untuk kembali.")

        with st.expander("🕯️ Cara membaca grafik candle (candlestick)", expanded=st.session_state.get("belajar", True)):
            st.markdown(
                "**1. Satu candle = ringkasan 4 harga dalam satu hari** — *Open* (pembukaan), *High* (tertinggi), "
                "*Low* (terendah), *Close* (penutupan), disingkat **OHLC**.\n\n"
                "- **Badan (body)** — kotak tebal, jarak antara Open dan Close.\n"
                "- **Sumbu / ekor (shadow, wick)** — garis tipis di atas & bawah badan, menunjukkan High dan Low.\n"
                "- **Warna** — 🟩 **hijau**: Close > Open (naik; Open di bawah, Close di atas). "
                "🟥 **merah**: Close < Open (turun; Open di atas, Close di bawah).")
            st.plotly_chart(candle_anatomy_chart(), width="stretch", config={"displayModeBar": False})
            st.markdown(
                "**2. Apa yang diceritakan bentuknya?**\n\n"
                "- **Badan panjang** = satu pihak (pembeli atau penjual) dominan. **Badan pendek** = pertarungan seimbang.\n"
                "- **Sumbu atas panjang** = harga sempat naik tapi ditolak (tekanan jual). "
                "**Sumbu bawah panjang** = harga sempat turun tapi diangkat lagi (dukungan beli).\n"
                "- Satu candle saja jarang cukup — lihat **beberapa candle berurutan** dan **posisinya terhadap tren**.")
            st.markdown("**3. Pola candle yang sering ditemui**")
            st.plotly_chart(candle_patterns_chart(), width="stretch", config={"displayModeBar": False})
            st.markdown("\n".join(f"- **{nama}** — {arti}" for nama, _, arti in POLA_CANDLE))
            st.markdown(
                "**4. Membaca candle bersama garis MA**\n\n"
                "- Candle-candle berada **di atas MA200** dan MA200 **menanjak** → tren besar naik (uptrend).\n"
                "- Candle **menembus MA dari bawah ke atas** dengan badan hijau panjang → tanda penguatan; "
                "menembus ke bawah dengan badan merah panjang → tanda pelemahan.\n"
                "- Saat uptrend, harga sering **memantul di sekitar MA50/MA200** (area *support*). Hammer di area "
                "support lebih bermakna daripada hammer di tengah-tengah.\n"
                "- **MA20 di atas MA50** → momentum jangka pendek positif. MA50 memotong MA200 ke atas = *golden cross*, "
                "ke bawah = *death cross*.\n\n"
                "**5. Langkah praktis membaca grafik di atas**\n"
                "1. Pilih periode **1–3 tahun** di panel kiri, lihat arah besar: candle mayoritas di atas atau di bawah MA200?\n"
                "2. Pindah ke **6 bulan**: apakah puncak & lembah makin tinggi (uptrend) atau makin rendah (downtrend)?\n"
                "3. Perhatikan **5–10 candle terakhir**: dominan hijau atau merah? Ada pola pembalikan (hammer, engulfing)?\n"
                "4. Cocokkan dengan **RSI**: pola pembalikan naik + RSI ≤ 30 lebih kuat sinyalnya.\n\n"
                "⚠️ Pola candle adalah *petunjuk peluang*, bukan kepastian. Selalu cocokkan dengan fundamental.")

        bacaan = baca_candle_terakhir(a)
        if bacaan:
            st.markdown(f"#### 🔎 Bacaan otomatis candle terakhir {a['code']}")
            st.markdown("\n".join(f"- {b}" for b in bacaan))

        t1, t2 = st.columns(2)
        with t1:
            st.markdown(f"**Tren tahunan: {a['yearly_trend']}**")
            st.markdown(
                f"- Return 1 tahun: **{fmt_pct(a['r1y'])}** · 3 tahun: {fmt_pct(a['r3y'])} · YTD: {fmt_pct(a['ytd'])}\n"
                f"- Harga {'di atas' if a['above200'] else 'di bawah'} MA200\n"
                f"- Rentang 52 minggu: {fmt_price(a['lo52'], a['currency'])} – {fmt_price(a['hi52'], a['currency'])}"
                + (f" (posisi {a['pos52'] * 100:.0f}% dari bawah)" if a["pos52"] is not None else ""))
        with t2:
            st.markdown(f"**Tren bulanan: {a['monthly_trend']}**")
            st.markdown(
                f"- Return 1 bulan: **{fmt_pct(a['r1m'])}** · 3 bulan: {fmt_pct(a['r3m'])} · 6 bulan: {fmt_pct(a['r6m'])}\n"
                f"- MA20 {'di atas' if a['ma20_above_50'] else 'di bawah'} MA50 "
                f"({'momentum positif' if a['ma20_above_50'] else 'momentum melemah'})\n"
                f"- RSI(14): {fmt_num(a['rsi'], 0)} "
                f"({'jenuh beli' if (a['rsi'] or 0) >= 70 else 'jenuh jual' if (a['rsi'] or 100) <= 30 else 'netral'})")
        b1, b2 = st.columns(2)
        if not a["annual_ret"].empty:
            b1.plotly_chart(bar_chart(a["annual_ret"], "Return per tahun"), width="stretch")
        if not a["monthly_ret"].empty:
            b2.plotly_chart(bar_chart(a["monthly_ret"], "Return per bulan (12 bulan terakhir)"), width="stretch")
        catatan_kaki(["Candle", "OHLC", "MA", "MA20", "MA50", "MA200", "Golden / death cross", "RSI",
                      "Jenuh beli / jenuh jual", "Uptrend / downtrend / sideways", "Momentum", "Koreksi",
                      "Support / resistance", "Return", "YTD", "Rentang 52 minggu"])

    # ---------------- Perbandingan ----------------
    with tab_p:
        peer_list = [normalize_ticker(p, idx) for p in peers_raw.split(",") if p.strip()]
        peer_list = [p for p in dict.fromkeys(peer_list) if p != ticker]
        if not peer_list:
            st.info("Isi daftar saham pembanding di panel kiri untuk melihat perbandingan.")
        else:
            results = [a]
            prog = st.progress(0.0, text="Mengambil data pembanding…")
            for i, p in enumerate(peer_list, 1):
                r = analyze(p)
                if r is not None:
                    results.append(r)
                prog.progress(i / len(peer_list), text=f"Mengambil data pembanding… ({i}/{len(peer_list)})")
            prog.empty()

            table = pd.DataFrame([{
                "Saham": ("▶ " if r is a else "") + r["code"],
                "Nama": r["name"],
                "Harga": r["price"],
                "PER": r["pe"],
                "PBV": r["pbv"],
                "ROE %": None if r["roe"] is None else r["roe"] * 100,
                "Margin %": None if r["npm"] is None else r["npm"] * 100,
                "Div. yield %": None if r["div_yield"] is None else r["div_yield"] * 100,
                "Return 1 th %": None if r["r1y"] is None else r["r1y"] * 100,
                "Fundamental": r["fund_score"],
                "Valuasi": r["val_score"],
                "Dividen": r["div_score"],
                "Tren": r["trend_score"],
                "Skor total": r["total"],
                "Rekomendasi": r["reco"],
            } for r in results]).sort_values("Skor total", ascending=False, na_position="last")

            st.dataframe(
                table, hide_index=True, width="stretch",
                column_config={
                    "Saham": st.column_config.TextColumn(help="▶ = saham yang sedang dianalisis."),
                    "Harga": st.column_config.NumberColumn(format="%.0f", help=GLOSARIUM["Harga"]["arti"]),
                    "PER": st.column_config.NumberColumn(format="%.1f", help=tip("PER")),
                    "PBV": st.column_config.NumberColumn(format="%.2f", help=tip("PBV")),
                    "ROE %": st.column_config.NumberColumn(format="%.1f", help=tip("ROE")),
                    "Margin %": st.column_config.NumberColumn(format="%.1f", help=tip("NPM")),
                    "Div. yield %": st.column_config.NumberColumn(format="%.2f", help=tip("Dividend yield")),
                    "Return 1 th %": st.column_config.NumberColumn(format="%.1f", help=tip("Return")),
                    "Fundamental": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.0f",
                                                                   help=tip("Fundamental")),
                    "Valuasi": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.0f",
                                                               help=tip("Valuasi")),
                    "Dividen": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.0f"),
                    "Tren": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.0f"),
                    "Skor total": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.0f",
                                                                  help=tip("Skor")),
                    "Rekomendasi": st.column_config.TextColumn(help=tip("BELI / TAHAN / JUAL")),
                })
            if st.session_state.get("belajar", True):
                st.caption("💡 Cara membaca: urutkan tabel dengan klik judul kolom. Cari saham yang ROE-nya tinggi tetapi "
                           "PER/PBV-nya rendah — artinya kualitas bagus dengan harga relatif murah dibanding peer-nya.")

            # Saham yang lebih baik
            better = [r for r in results if r is not a and r["total"] is not None and r["reco"] != "DATA KURANG"
                      and a["total"] is not None and r["total"] > a["total"]]
            better.sort(key=lambda r: r["total"], reverse=True)
            st.markdown("#### Alternatif yang lebih baik")
            if not better:
                st.success(f"**{a['code']}** memiliki skor tertinggi di antara pembandingnya.")
            else:
                for r in better[:3]:
                    reasons = []
                    for key, label in [("fund_score", "fundamental"), ("val_score", "valuasi"),
                                       ("div_score", "dividen"), ("trend_score", "tren")]:
                        if r[key] is not None and a[key] is not None and r[key] - a[key] >= 10:
                            reasons.append(f"{label} lebih baik ({r[key]:.0f} vs {a[key]:.0f})")
                    st.markdown(f"- **{r['code']}** — skor {r['total']:.0f} ({r['reco']}): "
                                + (", ".join(reasons) if reasons else "unggul tipis di beberapa aspek"))

            # Juara per kategori
            st.markdown("#### Terbaik per kategori")
            cols = st.columns(4)
            for col, (key, label) in zip(cols, [("fund_score", "Fundamental"), ("val_score", "Valuasi termurah"),
                                                ("div_score", "Dividen"), ("trend_score", "Tren terkuat")]):
                cands = [r for r in results if r[key] is not None]
                if cands:
                    best = max(cands, key=lambda r: r[key])
                    col.metric(label, best["code"], f"skor {best[key]:.0f}", delta_color="off")

            # Grafik kinerja relatif 1 tahun
            fig = go.Figure()
            for r in results:
                c = r["close"][r["close"].index > r["close"].index[-1] - timedelta(days=365)]
                if len(c) > 1:
                    fig.add_trace(go.Scatter(x=c.index, y=(c / c.iloc[0] - 1) * 100, name=r["code"],
                                             line=dict(width=3 if r is a else 1.5)))
            fig.update_layout(title="Kinerja harga relatif 1 tahun (%)", height=380,
                              margin=dict(l=10, r=10, t=40, b=10), yaxis_title="%")
            st.plotly_chart(fig, width="stretch")
            st.caption("Semua garis dimulai dari 0% setahun lalu. Garis tebal = saham yang dianalisis.")
        catatan_kaki(["Peer", "PER", "PBV", "ROE", "NPM", "Dividend yield", "Return", "Kinerja relatif", "Skor",
                      "BELI / TAHAN / JUAL"])

    st.divider()
    with st.expander("📘 Kamus lengkap istilah & singkatan"):
        kamus = pd.DataFrame([{"Istilah": k, "Kepanjangan / nama": g["nama"], "Artinya": g["arti"], "Patokan": g["patokan"]}
                              for k, g in sorted(GLOSARIUM.items(), key=lambda kv: kv[0].lower())])
        st.dataframe(kamus, hide_index=True, width="stretch", height=500,
                     column_config={"Artinya": st.column_config.TextColumn(width="large"),
                                    "Patokan": st.column_config.TextColumn(width="medium")})
    st.caption("⚠️ Rekomendasi dihasilkan otomatis dari aturan sederhana atas data publik dan bukan nasihat investasi. "
               "Data Yahoo Finance untuk saham BEI kadang tidak lengkap atau terlambat diperbarui; cek ulang dengan "
               "laporan keuangan resmi (idx.co.id) sebelum mengambil keputusan.")


if __name__ == "__main__":
    main()
