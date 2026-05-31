"""
Groq Analyst — Natural Language Business Insights untuk G Coffee Shop.

Menggunakan Groq API (gratis, tanpa perlu billing):
  - Daftar: https://console.groq.com
  - Model: llama-3.3-70b-versatile (gratis, 30 req/menit)
  - Tidak perlu CC

Arsitektur:
  Engine (existing) → DataContext (dict) → Prompt → Groq API → NL Insight
"""

import json
import os
from typing import Optional
from datetime import datetime

import streamlit as st
from groq import Groq


# ══════════════════════════════════════════════════════════════════════════════
#  KONFIGURASI
# ══════════════════════════════════════════════════════════════════════════════

_GROQ_MODEL = "llama-3.3-70b-versatile"  # gratis, 30 req/menit ✅


def _get_api_key() -> Optional[str]:
    """Cari API key dari st.secrets dulu, fallback ke env var."""
    try:
        return st.secrets["GROQ_API_KEY"]
    except (KeyError, FileNotFoundError):
        return os.environ.get("GROQ_API_KEY", None)


# ══════════════════════════════════════════════════════════════════════════════
#  SYSTEM PROMPT — panduan tetap untuk model
# ══════════════════════════════════════════════════════════════════════════════

_SYSTEM_PROMPT = """Anda adalah asisten preskriptif untuk jaringan kedai kopi G Coffee (Malaysia).
Tugas anda adalah memberi rekomendasi bisnis berdasarkan DATA yang diberikan.

## ATURAN KETAT:
1. HANYA gunakan data yang diberikan di bawah ini — JANGAN halusinasi angka
2. JANGAN merekomendasikan diskon >25% (batas kebijakan)
3. Jika data margin tidak mencukupi, beri peringatan "estimasi"
4. Bedakan rekomendasi berdasarkan SEGMEN pelanggan
5. Sertakan REASONING singkat mengapa rekomendasi itu diberikan
6. Bahasa Indonesia yang natural, tidak kaku

## FORMAT OUTPUT:
<rekomendasi>
... rekomendasi di sini ...
</rekomendasi>

Di luar tag itu boleh ada penjelasan tambahan.

Contoh:
<rekomendasi>
Untuk segmen At Risk di USJ (Weekend, peak 14-16):
- Bundle: Latte + Matcha Latte (diskon 10%, margin masih aman)
- Channel: Push notification jam 12:00
- Reasoning: Weekend traffic tinggi + forecast naik 5% → diskon ringan cukup
- ⚠️ Margin adalah ESTIMASI karena data HPP tidak tersedia
</rekomendasi>
"""


# ══════════════════════════════════════════════════════════════════════════════
#  GROQ ANALYST CLASS
# ══════════════════════════════════════════════════════════════════════════════

class GroqAnalyst:
    """
    Mengubah data engine → natural language insight via Groq API (gratis).

    Cara pakai:
        analyst = GroqAnalyst()
        insight = analyst.analyze(context_json)
        st.markdown(insight)
    """

    def __init__(self):
        self.api_key = _get_api_key()
        self._client = None
        self._ready = False

        if self.api_key:
            try:
                self._client = Groq(api_key=self.api_key)
                # Test panggil model
                self._client.chat.completions.create(
                    model=_GROQ_MODEL,
                    messages=[{"role": "user", "content": "test"}],
                    max_tokens=1,
                )
                self._ready = True
            except Exception as e:
                st.warning(f"⚠️ Groq gagal init: {e}")
        else:
            st.info(
                "🔑 **Set API Key Groq**\n\n"
                "1. Daftar gratis di https://console.groq.com (tidak perlu CC)\n"
                "2. Buat API key\n"
                "3. Set environment variable:\n"
                "   ```powershell\n"
                '   $env:GROQ_API_KEY = "gsk_..."\n'
                "   ```\n"
                "4. Restart app"
            )

    @property
    def is_ready(self) -> bool:
        return self._ready

    # ── Method utama: kirim data → dapat insight ──────────────────────────

    @st.cache_data(ttl=300, show_spinner="🧠 Menganalisis data...")
    def analyze(_self, context_json: str) -> str:
        """
        Terima data context (JSON string), kirim ke Groq, return insight.
        Di-cache 5 menit.
        """
        if not _self._ready:
            return "🔑 Set API Key Groq dulu (lihat info di atas)."

        try:
            context = json.loads(context_json)
        except json.JSONDecodeError:
            return "⚠️ Error: context_json tidak valid."

        # ── Currency-aware formatting ──────────────────────────────────────
        _cur_sym = context.get("currency", "RM")  # 'RM' or 'IDR'
        _rate = 3500
        def _c(v):
            return v * _rate if _cur_sym == "IDR" else v
        def _fmt_idr(n, fmt=",.0f"):
            """Format number in Indonesian style: . = thousand sep, , = decimal sep."""
            s = format(n, fmt)
            s = s.replace(",", "X")
            s = s.replace(".", ",")
            s = s.replace("X", ".")
            return s

        # ── Bangun user prompt ────────────────────────────────────────────
        lines = ["## DATA BISNIS SAAT INI\n"]

        # Segmen
        seg = context.get("segment", {})
        if seg:
            lines.append("### Segmen Pelanggan")
            lines.append(f"- Nama: {seg.get('name', '-')}")
            lines.append(f"- Jumlah: {_fmt_idr(seg.get('count', 0), ',.0f')} orang")
            lines.append(f"- Persentase: {seg.get('pct', 0):.1f}%")
            lines.append(f"- Rata-rata Recency: {seg.get('recency_mean', '-')} hari")
            lines.append(f"- Rata-rata Frequency: {seg.get('frequency_mean', '-')}x")
            lines.append(f"- Rata-rata Monetary: {_cur_sym} {seg.get('monetary_mean', '-')}")
            lines.append("")

        # Cabang
        branch = context.get("branch", {})
        if branch:
            lines.append("### Cabang")
            lines.append(f"- Nama: {branch.get('name', '-')}")
            lines.append(f"- Kota: {branch.get('city', '-')}")
            lines.append(f"- Hari: {branch.get('day_type', '-')}")
            lines.append(f"- Jam puncak: {branch.get('peak_hour', '-')}")
            lines.append("")

        # Bundling
        rules = context.get("bundling_rules", [])
        if rules:
            lines.append("### Aturan Bundling (Apriori)")
            for r in rules[:5]:
                lines.append(
                    f"- {r.get('A', '?')} + {r.get('B', '?')}  "
                    f"(confidence: {r.get('confidence', 0):.2f}, "
                    f"lift: {r.get('lift', 0):.2f})"
                )
            lines.append("")

        # Margin
        margins = context.get("margins", [])
        if margins:
            lines.append("### Margin Estimasi per Item")
            for m in margins:
                lines.append(
                    f"- {m.get('item', '?')}: "
                    f"{_cur_sym} {_fmt_idr(_c(m.get('price', 0)), ',.0f')}, "
                    f"margin {m.get('margin_pct', 0):.1f}% "
                    f"{'⚠️ ESTIMASI' if m.get('is_estimate') else ''}"
                )
            lines.append("")

        # Forecast
        fc = context.get("forecast", {})
        if fc:
            lines.append("### Forecast 90 Hari")
            lines.append(f"- Conservative Growth: {_cur_sym} {_fmt_idr(_c(fc.get('conservative', 0)), ',.0f')}")
            lines.append(f"- Aggressive Growth: {_cur_sym} {_fmt_idr(_c(fc.get('aggressive', 0)), ',.0f')}")
            lines.append("")

        # Constraint
        lines.append("### Constraint Bisnis")
        lines.append("- Diskon maksimal: 25%")
        lines.append(f"- Tanggal: {datetime.now().strftime('%Y-%m-%d')}")
        lines.append("")

        # Question
        question = context.get("question", None)
        if question:
            lines.append(f"### Pertanyaan Spesifik: {question}")
        else:
            lines.append(
                "### Tugas:\n"
                "Berdasarkan data di atas, beri rekomendasi:\n"
                "1. Voucher apa yang tepat? (jenis, besaran diskon, jam)\n"
                "2. Bundle produk apa yang direkomendasikan?\n"
                "3. Channel promosi terbaik?\n"
                "4. Margin safety check\n"
                "5. Insight tambahan"
            )

        user_prompt = "\n".join(lines)

        # ── Panggil Groq ──────────────────────────────────────────────────
        try:
            response = _self._client.chat.completions.create(
                model=_GROQ_MODEL,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=1024,
            )
            return response.choices[0].message.content or "(kosong)"

        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "rate limit" in err_str.lower():
                return (
                    "⚠️ **Rate limit Groq tercapai.**\n\n"
                    "Gratis: 30 request/menit, 6000 request/hari.\n\n"
                    "Coba:\n"
                    "1. Tunggu 1-2 menit, lalu coba lagi\n"
                    "2. Cek pemakaian di https://console.groq.com"
                )
            return f"⚠️ Error Groq: {e}"


# ══════════════════════════════════════════════════════════════════════════════
#  HELPER: Build context dari engine yang sudah ada
# ══════════════════════════════════════════════════════════════════════════════

def build_context(
    segment_name: str = "",
    seg_counts=None,
    branch_name: str = "",
    branch_city: str = "",
    day_type: str = "Weekday",
    peak_hour: str = "-",
    rules_df=None,
    menu_df=None,
    fin_engine=None,
    fc_engine=None,
    question: str = "",
    currency: str = "RM",
) -> str:
    """
    Kumpulin data dari semua engine → JSON string siap kirim ke Groq.
    """
    ctx = {"currency": currency}

    # ── Segment ───────────────────────────────────────────────────────────
    if segment_name and seg_counts is not None:
        row = seg_counts[seg_counts["segment"] == segment_name]
        if not row.empty:
            ctx["segment"] = {
                "name": segment_name,
                "count": int(row.iloc[0]["count"]),
                "pct": float(row.iloc[0]["pct"]),
            }

    # ── Branch ────────────────────────────────────────────────────────────
    ctx["branch"] = {
        "name": branch_name,
        "city": branch_city,
        "day_type": day_type,
        "peak_hour": peak_hour,
    }

    # ── Bundling Rules ────────────────────────────────────────────────────
    if rules_df is not None and segment_name:
        seg_rules = rules_df[rules_df["segment_name"] == segment_name]
        ctx["bundling_rules"] = []
        for _, r in seg_rules.head(5).iterrows():
            ctx["bundling_rules"].append({
                "A": str(r.get("antecedents", "")),
                "B": str(r.get("consequents", "")),
                "confidence": float(r.get("confidence", 0)),
                "lift": float(r.get("lift", 0)),
                "support": float(r.get("support", 0)),
            })

    # ── Margins ───────────────────────────────────────────────────────────
    if menu_df is not None and fin_engine is not None:
        ctx["margins"] = []
        for _, row in menu_df.iterrows():
            item_name = row["item_name"]
            margin = fin_engine.get_net_margin(item_name)
            ctx["margins"].append({
                "item": item_name,
                "price": margin["price"],
                "margin_pct": margin["net_margin_pct"],
                "is_estimate": True,
            })

    # ── Forecast ──────────────────────────────────────────────────────────
    if fc_engine is not None:
        try:
            profit_fc = fc_engine.get_profit_forecast(margin_pct=0.25)
            agg = profit_fc.groupby("scenario")["projected_profit"].sum()
            ctx["forecast"] = {
                "conservative": round(float(agg.get("Conservative Growth", 0))),
                "aggressive": round(float(agg.get("Aggressive Growth", 0))),
            }
        except Exception:
            ctx["forecast"] = {}

    # ── Question ──────────────────────────────────────────────────────────
    if question:
        ctx["question"] = question

    return json.dumps(ctx, ensure_ascii=False, indent=2)
