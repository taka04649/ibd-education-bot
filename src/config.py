"""設定ファイル。環境変数と検索クエリを一元管理。"""
import os
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# PubMed 検索クエリ（IBD全般・教育的用途）
# ------------------------------------------------------------
# 対象: UC, CD, IBDU, pouchitis, IBD 関連合併症を広くカバー
# 品質フィルタ: RCT / Meta-analysis / Systematic Review /
#              Practice Guideline / Phase II-III + 主要誌
# 期間: 直近 1 年以内
# ============================================================
PUBMED_QUERY = (
    # === 対象疾患 ===
    '('
    '"inflammatory bowel diseases"[MeSH Terms] '
    'OR "colitis, ulcerative"[MeSH Terms] '
    'OR "Crohn Disease"[MeSH Terms] '
    'OR "pouchitis"[MeSH Terms] '
    'OR "inflammatory bowel disease"[Title/Abstract] '
    'OR "ulcerative colitis"[Title/Abstract] '
    'OR "Crohn"[Title/Abstract] '
    'OR "IBD"[Title] '
    'OR "pouchitis"[Title/Abstract]'
    ') '
    # === 品質フィルタ ===
    'AND ('
    # 研究デザイン
    'Randomized Controlled Trial[PT] '
    'OR Meta-Analysis[PT] '
    'OR Systematic Review[PT] '
    'OR Practice Guideline[PT] '
    'OR Guideline[PT] '
    'OR Clinical Trial, Phase III[PT] '
    'OR Clinical Trial, Phase II[PT] '
    # 主要誌
    'OR "Gastroenterology"[Journal] '
    'OR "Gut"[Journal] '
    'OR "Lancet"[Journal] '
    'OR "Lancet Gastroenterol Hepatol"[Journal] '
    'OR "N Engl J Med"[Journal] '
    'OR "J Crohns Colitis"[Journal] '
    'OR "Am J Gastroenterol"[Journal] '
    'OR "Clin Gastroenterol Hepatol"[Journal] '
    'OR "Aliment Pharmacol Ther"[Journal] '
    'OR "Inflamm Bowel Dis"[Journal] '
    'OR "Nat Rev Gastroenterol Hepatol"[Journal]'
    ') '
    # === 期間 ===
    'AND ("1 year"[PDat]) '
    # === 言語 ===
    'AND (English[Language] OR Japanese[Language]) '
    # === 除外 ===
    'NOT (comment[PT] OR editorial[PT] OR letter[PT] OR "retracted publication"[PT])'
)

# 1回の実行で処理する論文数（2本/回 × 4回/日 = 8本/日）
MAX_PAPERS_PER_RUN = 2

# ============================================================
# API 設定
# ============================================================
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
PUBMED_API_KEY = os.getenv("PUBMED_API_KEY", "")
PUBMED_EMAIL = os.getenv("PUBMED_EMAIL", "")

CLAUDE_MODEL = "claude-sonnet-4-5"
POSTED_PMIDS_FILE = "data/posted_pmids.json"


def validate() -> None:
    """必須環境変数のチェック"""
    missing = []
    if not ANTHROPIC_API_KEY:
        missing.append("ANTHROPIC_API_KEY")
    if not DISCORD_WEBHOOK_URL:
        missing.append("DISCORD_WEBHOOK_URL")
    if missing:
        raise RuntimeError(
            f"必須の環境変数が設定されていません: {', '.join(missing)}\n"
            f".env ファイルまたは GitHub Secrets を確認してください。"
        )
