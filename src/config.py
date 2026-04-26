"""設定ファイル。環境変数と検索クエリを一元管理。"""
import os
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# PubMed 検索クエリ（IBD領域に厳格に限定）
# ------------------------------------------------------------
# 設計思想:
#   1. IBD を「主題として」扱う論文に限定（MeSH Major Topic 優先）
#   2. タイトルでの IBD 言及を必須化（abstract のみの言及は除外）
#   3. 品質フィルタとジャーナルフィルタは構造を厳格化
#   4. "IBD"[Title] のような曖昧な略語マッチは削除
#   5. pouchitis は IBD 関連合併症として含めるが、postcolectomy 等の
#      IBD 文脈に限定するため Crohn/UC との共起を必須にしない
# ============================================================
PUBMED_QUERY = (
    # === 第1階層: IBD を主題とする論文に限定 ===
    # 以下のいずれかを満たす:
    # (a) MeSH Major Topic に IBD/UC/CD/Pouchitis が指定されている
    # (b) MeSH Term + タイトルに IBD/UC/CD のキーワードが含まれる
    '('
    # (a) MeSH Major Topic（主題）
    '"inflammatory bowel diseases"[MeSH Major Topic] '
    'OR "colitis, ulcerative"[MeSH Major Topic] '
    'OR "Crohn Disease"[MeSH Major Topic] '
    'OR "pouchitis"[MeSH Major Topic] '
    # (b) MeSH（主題でなくても）+ タイトルにキーワード（具体性あり）
    'OR ('
    '   ('
    '       "inflammatory bowel diseases"[MeSH Terms] '
    '       OR "colitis, ulcerative"[MeSH Terms] '
    '       OR "Crohn Disease"[MeSH Terms] '
    '       OR "pouchitis"[MeSH Terms]'
    '   ) '
    '   AND ('
    '       "inflammatory bowel disease"[Title] '
    '       OR "ulcerative colitis"[Title] '
    '       OR "Crohn disease"[Title] '
    '       OR "Crohn\'s disease"[Title] '
    '       OR "pouchitis"[Title]'
    '   )'
    ')'
    ') '
    # === 第2階層: 品質フィルタ（研究デザイン） ===
    'AND ('
    'Randomized Controlled Trial[PT] '
    'OR Meta-Analysis[PT] '
    'OR Systematic Review[PT] '
    'OR Practice Guideline[PT] '
    'OR Guideline[PT] '
    'OR Clinical Trial, Phase III[PT] '
    'OR Clinical Trial, Phase II[PT]'
    ') '
    # === 第3階層: 言語 ===
    'AND (English[Language] OR Japanese[Language]) '
    # === 除外 ===
    'NOT (comment[PT] OR editorial[PT] OR letter[PT] OR "retracted publication"[PT] '
    'OR "published erratum"[PT])'
)

# 期間フィルタ（reldate=N: 過去 N 日以内）
# 365 = 1年、730 = 2年、180 = 6ヶ月
PUBMED_RELDATE_DAYS = 730

# 1回の実行で処理する論文数（2本/回 × 4回/日 = 8本/日）
MAX_PAPERS_PER_RUN = 2

# ============================================================
# IBD 関連性の事後チェック用キーワード
# ------------------------------------------------------------
# クエリでヒットした論文を、念のためタイトル/abstract で再確認する
# ためのキーワードリスト。これらのいずれかが含まれていなければ除外。
# ============================================================
IBD_RELEVANCE_KEYWORDS = [
    "ulcerative colitis",
    "crohn disease",
    "crohn's disease",
    "crohns disease",
    "inflammatory bowel disease",
    "inflammatory bowel diseases",
    "pouchitis",
    "ileal pouch",
    "ileoanal anastomosis",
    "ileal pouch-anal anastomosis",
    "ipaa",  # Ileal Pouch-Anal Anastomosis
]

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
