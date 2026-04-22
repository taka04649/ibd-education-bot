"""Discord Webhook への投稿クライアント。"""
from datetime import datetime, timezone, timedelta

import requests

MAX_DESC_LEN = 4000
MAX_TITLE_LEN = 250
MAX_FIELD_VALUE_LEN = 1024

# JST
JST = timezone(timedelta(hours=9))

# 論文タイプ別の色
PTYPE_COLORS = {
    "Practice Guideline": 0xE67E22,          # 濃いオレンジ（ガイドラインは最重要）
    "Guideline": 0xE67E22,
    "Meta-Analysis": 0x3498DB,               # 青
    "Systematic Review": 0x3498DB,
    "Randomized Controlled Trial": 0x2ECC71, # 緑
    "Clinical Trial, Phase III": 0x27AE60,
    "Clinical Trial, Phase II": 0x58D68D,
    "Clinical Trial": 0x58D68D,
    "Multicenter Study": 0x9B59B6,
    "Observational Study": 0xF39C12,
    "Review": 0x95A5A6,
}
DEFAULT_COLOR = 0x7F8C8D

# 論文タイプの短縮表示
PTYPE_SHORT = {
    "Practice Guideline": "📜 Guideline",
    "Guideline": "📜 Guideline",
    "Meta-Analysis": "📊 Meta-Analysis",
    "Systematic Review": "📚 Systematic Review",
    "Randomized Controlled Trial": "🎯 RCT",
    "Clinical Trial, Phase III": "💊 Phase III",
    "Clinical Trial, Phase II": "💊 Phase II",
    "Clinical Trial": "💊 Clinical Trial",
    "Multicenter Study": "🏥 Multicenter",
    "Observational Study": "👁️ Observational",
    "Review": "📖 Review",
}


def _get_time_slot() -> dict:
    """現在の JST 時刻から、朝/昼/夕/夜のスロット情報を返す。"""
    hour = datetime.now(JST).hour
    if 5 <= hour < 11:
        return {"emoji": "☀️", "label": "朝のIBDダイジェスト"}
    elif 11 <= hour < 15:
        return {"emoji": "🍱", "label": "昼のIBDダイジェスト"}
    elif 15 <= hour < 20:
        return {"emoji": "🌇", "label": "夕のIBDダイジェスト"}
    else:
        return {"emoji": "🌙", "label": "夜のIBDダイジェスト"}


def _ptype_display(ptype: str) -> str:
    return PTYPE_SHORT.get(ptype, f"📄 {ptype}")


def _ptype_color(ptype: str) -> int:
    return PTYPE_COLORS.get(ptype, DEFAULT_COLOR)


def post_to_discord(webhook_url: str, paper: dict, summary: str) -> None:
    """1論文 = 1 embed として投稿する。"""
    title = (paper.get("title") or "Untitled")[:MAX_TITLE_LEN]
    desc = summary[:MAX_DESC_LEN]
    primary_ptype = paper.get("primary_ptype", "Journal Article")

    fields = [
        {
            "name": "Study Type",
            "value": _ptype_display(primary_ptype),
            "inline": True,
        },
        {
            "name": "Journal",
            "value": f"{paper.get('journal_iso') or paper.get('journal', 'N/A')} ({paper.get('year', 'N/A')})"[:MAX_FIELD_VALUE_LEN],
            "inline": True,
        },
        {
            "name": "PMID",
            "value": paper.get("pmid", "N/A"),
            "inline": True,
        },
        {
            "name": "Authors",
            "value": (paper.get("authors") or "N/A")[:MAX_FIELD_VALUE_LEN],
            "inline": False,
        },
    ]

    if paper.get("doi"):
        fields.append({
            "name": "DOI",
            "value": f"[{paper['doi']}](https://doi.org/{paper['doi']})",
            "inline": False,
        })

    embed = {
        "title": f"📄 {title}",
        "url": paper.get("url", ""),
        "description": desc,
        "color": _ptype_color(primary_ptype),
        "fields": fields,
        "footer": {"text": "IBD Education Bot · via PubMed + Claude Sonnet"},
    }

    payload = {"embeds": [embed]}
    r = requests.post(webhook_url, json=payload, timeout=30)
    r.raise_for_status()


def post_header(webhook_url: str, n_papers: int, paper_summary: dict | None = None) -> None:
    """時間帯別のヘッダーメッセージを投稿する。"""
    slot = _get_time_slot()
    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    lines = [
        f"{slot['emoji']} **{slot['label']} — {now} JST**",
        f"厳選された IBD 論文: **{n_papers}本**",
    ]
    if paper_summary:
        breakdown = " / ".join(f"{k}: {v}" for k, v in paper_summary.items())
        lines.append(f"📊 内訳: {breakdown}")

    r = requests.post(webhook_url, json={"content": "\n".join(lines)}, timeout=30)
    r.raise_for_status()
