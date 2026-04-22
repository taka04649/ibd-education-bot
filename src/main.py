"""メインエントリポイント。"""
import json
import sys
import time
from collections import Counter
from pathlib import Path

# src/ を import path に追加
sys.path.insert(0, str(Path(__file__).parent))

from config import (
    DISCORD_WEBHOOK_URL,
    MAX_PAPERS_PER_RUN,
    POSTED_PMIDS_FILE,
    PUBMED_QUERY,
    validate,
)
from pubmed_client import fetch_paper_details, rank_papers, search_pubmed
from claude_client import summarize_paper
from discord_client import post_header, post_to_discord

# 候補として取得する PMID 数（多めに取って信頼度スコア順に上位を選ぶ）
SEARCH_CANDIDATES = 80


def load_posted_pmids() -> set:
    p = Path(POSTED_PMIDS_FILE)
    if not p.exists():
        return set()
    try:
        return set(json.loads(p.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError) as e:
        print(f"[warn] posted_pmids.json の読み込みに失敗: {e}. 空集合で開始します。")
        return set()


def save_posted_pmids(pmids: set) -> None:
    p = Path(POSTED_PMIDS_FILE)
    p.parent.mkdir(parents=True, exist_ok=True)
    sorted_pmids = sorted(pmids, key=lambda x: int(x) if x.isdigit() else 0, reverse=True)[:5000]
    p.write_text(
        json.dumps(sorted_pmids, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def summarize_paper_types(papers: list) -> dict:
    """論文タイプごとの件数を集計する。"""
    counter = Counter(p.get("primary_ptype", "Other") for p in papers)
    return dict(counter.most_common())


def main() -> None:
    print("=== IBD Education Bot 起動 ===")
    validate()

    posted = load_posted_pmids()
    print(f"既投稿 PMID 数: {len(posted)}")

    # 候補を多めに取得
    candidate_pmids = search_pubmed(PUBMED_QUERY, max_results=SEARCH_CANDIDATES)
    print(f"PubMed 検索ヒット: {len(candidate_pmids)} 件（候補）")

    # 未投稿のみ残す
    new_pmids = [p for p in candidate_pmids if p not in posted]
    print(f"未投稿の候補: {len(new_pmids)} 件")

    if not new_pmids:
        print("新規論文なし。終了。")
        return

    # まず上位 10 件程度の詳細を取得してスコアリング
    fetch_limit = min(len(new_pmids), 15)
    papers = fetch_paper_details(new_pmids[:fetch_limit])
    print(f"詳細取得成功: {len(papers)} 件")
    if not papers:
        print("Abstract を持つ論文がありませんでした。終了。")
        return

    # 信頼度スコア順に並び替え、上位 MAX_PAPERS_PER_RUN 本を選ぶ
    ranked = rank_papers(papers)
    selected = ranked[:MAX_PAPERS_PER_RUN]
    print(f"選定結果（上位 {len(selected)} 件）:")
    for p in selected:
        print(f"  - [score={p.get('trust_score')}] [{p.get('primary_ptype')}] PMID={p['pmid']}: {p['title'][:60]}...")

    # ヘッダー投稿
    ptype_summary = summarize_paper_types(selected)
    post_header(DISCORD_WEBHOOK_URL, len(selected), ptype_summary)
    time.sleep(1)

    # 各論文を解説して投稿
    success_count = 0
    for paper in selected:
        pmid = paper.get("pmid", "?")
        try:
            print(f"[解説生成] PMID={pmid}...")
            summary = summarize_paper(paper)
            post_to_discord(DISCORD_WEBHOOK_URL, paper, summary)
            posted.add(pmid)
            success_count += 1
            time.sleep(2)  # Discord rate limit 対策
        except Exception as e:
            print(f"[error] PMID={pmid}: {e}")
            continue

    save_posted_pmids(posted)
    print(f"=== 完了: {success_count}/{len(selected)} 件投稿 ===")


if __name__ == "__main__":
    main()
