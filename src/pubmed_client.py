"""PubMed E-utilities API クライアント（信頼度スコアリング + IBD関連性フィルタ）。"""
import re
import time
import xml.etree.ElementTree as ET
from typing import Dict, List

import requests

from config import (
    IBD_RELEVANCE_KEYWORDS,
    PUBMED_API_KEY,
    PUBMED_EMAIL,
    PUBMED_RELDATE_DAYS,
)

BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# 優先的に表示したい Publication Type
PRIORITY_PTYPES = [
    "Practice Guideline",
    "Guideline",
    "Meta-Analysis",
    "Systematic Review",
    "Randomized Controlled Trial",
    "Clinical Trial, Phase III",
    "Clinical Trial, Phase II",
    "Clinical Trial",
    "Multicenter Study",
    "Observational Study",
    "Review",
]

PTYPE_SCORE = {
    "Practice Guideline": 100,
    "Guideline": 90,
    "Meta-Analysis": 85,
    "Systematic Review": 80,
    "Randomized Controlled Trial": 70,
    "Clinical Trial, Phase III": 65,
    "Clinical Trial, Phase II": 50,
    "Clinical Trial": 40,
    "Multicenter Study": 30,
    "Review": 25,
    "Observational Study": 15,
}

JOURNAL_BONUS = {
    "N Engl J Med": 30,
    "Lancet": 30,
    "Lancet Gastroenterol Hepatol": 25,
    "Gastroenterology": 25,
    "Gut": 25,
    "Nat Rev Gastroenterol Hepatol": 25,
    "J Crohns Colitis": 20,
    "Am J Gastroenterol": 20,
    "Clin Gastroenterol Hepatol": 20,
    "Aliment Pharmacol Ther": 15,
    "Inflamm Bowel Dis": 15,
}

# IBD MeSH Term セット（事後フィルタで使用）
IBD_MESH_TERMS = {
    "inflammatory bowel diseases",
    "colitis, ulcerative",
    "crohn disease",
    "pouchitis",
    "ileitis",
    "colitis",
}

# IBD 関連の細粒度トピック MeSH（subhederとして許容）
IBD_RELATED_MESH = {
    "biological therapy",
    "tumor necrosis factor-alpha",
    "interleukins",
    "intestinal mucosa",
    "ileal pouch",
    "anastomosis, surgical",
}


def _common_params() -> Dict[str, str]:
    params: Dict[str, str] = {}
    if PUBMED_API_KEY:
        params["api_key"] = PUBMED_API_KEY
    if PUBMED_EMAIL:
        params["email"] = PUBMED_EMAIL
        params["tool"] = "ibd-education-bot"
    return params


def search_pubmed(query: str, max_results: int = 50) -> List[str]:
    """PubMed 検索で PMID リストを取得する（直近 PUBMED_RELDATE_DAYS 日以内）。"""
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": str(max_results),
        "sort": "date",
        "retmode": "json",
        "datetype": "pdat",
        "reldate": str(PUBMED_RELDATE_DAYS),
        **_common_params(),
    }
    r = requests.get(f"{BASE_URL}/esearch.fcgi", params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data.get("esearchresult", {}).get("idlist", [])


def fetch_paper_details(pmids: List[str]) -> List[Dict]:
    """PMID リストから論文詳細を取得し、信頼度スコア + IBD関連性チェック付きで返す。"""
    if not pmids:
        return []

    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
        **_common_params(),
    }
    r = requests.get(f"{BASE_URL}/efetch.fcgi", params=params, timeout=60)
    r.raise_for_status()

    root = ET.fromstring(r.content)
    papers: List[Dict] = []
    excluded_count = 0

    for article in root.findall(".//PubmedArticle"):
        try:
            paper = _parse_article(article)
            if not paper or not paper.get("abstract"):
                continue

            # IBD 関連性の事後チェック
            if not _is_ibd_relevant(paper):
                excluded_count += 1
                print(f"[除外: 非IBD] PMID={paper['pmid']}: {paper['title'][:80]}")
                continue

            paper["trust_score"] = _calculate_trust_score(paper)
            papers.append(paper)
        except Exception as e:
            print(f"[warn] Parse error for one article: {e}")
            continue
        time.sleep(0.1)

    if excluded_count > 0:
        print(f"[info] IBD関連性チェックで {excluded_count} 件を除外しました")

    return papers


def _is_ibd_relevant(paper: Dict) -> bool:
    """論文が IBD 領域に関連しているか判定する。
    
    判定基準（いずれかを満たす）:
    1. MeSH Term に IBD 関連の主要 Term が含まれる
    2. タイトルに IBD 関連キーワードが含まれる
    3. Abstract の冒頭に IBD 関連キーワードが複数回出現
    """
    title_lower = (paper.get("title") or "").lower()
    abstract_lower = (paper.get("abstract") or "").lower()
    mesh_terms_lower = {
        m.lower() for m in paper.get("mesh_terms", [])
    }

    # 判定1: MeSH Term に IBD 主要 Term が含まれる
    if mesh_terms_lower & IBD_MESH_TERMS:
        return True

    # 判定2: タイトルに IBD 関連キーワード
    for kw in IBD_RELEVANCE_KEYWORDS:
        if kw in title_lower:
            return True

    # 判定3: Abstract の冒頭1000文字に IBD 関連キーワードが2回以上出現
    abstract_head = abstract_lower[:1000]
    keyword_hits = sum(
        abstract_head.count(kw) for kw in IBD_RELEVANCE_KEYWORDS
    )
    if keyword_hits >= 2:
        return True

    return False


def _parse_article(article: ET.Element) -> Dict:
    """<PubmedArticle> 要素をパースして dict を返す。"""
    pmid = article.findtext(".//PMID", "") or ""
    title = article.findtext(".//ArticleTitle", "") or ""
    journal = article.findtext(".//Journal/Title", "") or ""
    journal_iso = article.findtext(".//Journal/ISOAbbreviation", "") or journal

    # Abstract
    abstract_parts: List[str] = []
    for el in article.findall(".//Abstract/AbstractText"):
        label = el.get("Label", "")
        text = el.text or ""
        if label:
            abstract_parts.append(f"{label}: {text}")
        else:
            abstract_parts.append(text)
    abstract = "\n".join(p for p in abstract_parts if p).strip()

    # 著者
    all_authors = article.findall(".//Author")
    authors: List[str] = []
    for au in all_authors[:3]:
        last = au.findtext("LastName", "") or ""
        init = au.findtext("Initials", "") or ""
        name = f"{last} {init}".strip()
        if name:
            authors.append(name)
    author_str = ", ".join(authors)
    if len(all_authors) > 3:
        author_str += ", et al."

    # 出版年
    year = article.findtext(".//PubDate/Year", "") or ""
    if not year:
        medline_date = article.findtext(".//PubDate/MedlineDate", "") or ""
        year = medline_date[:4]

    # DOI
    doi = ""
    for aid in article.findall(".//ArticleId"):
        if aid.get("IdType") == "doi":
            doi = (aid.text or "").strip()
            break

    # Publication Types
    ptypes = [
        (el.text or "").strip()
        for el in article.findall(".//PublicationTypeList/PublicationType")
        if el.text
    ]
    primary_ptype = _select_primary_ptype(ptypes)

    # MeSH Terms（IBD関連性チェックで使用）
    mesh_terms = []
    for mh in article.findall(".//MeshHeading/DescriptorName"):
        if mh.text:
            mesh_terms.append(mh.text.strip())

    return {
        "pmid": pmid,
        "title": title,
        "abstract": abstract,
        "journal": journal,
        "journal_iso": journal_iso,
        "authors": author_str,
        "year": year,
        "doi": doi,
        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        "publication_types": ptypes,
        "primary_ptype": primary_ptype,
        "mesh_terms": mesh_terms,
    }


def _select_primary_ptype(ptypes: List[str]) -> str:
    for priority in PRIORITY_PTYPES:
        if priority in ptypes:
            return priority
    for pt in ptypes:
        if pt and pt != "Journal Article":
            return pt
    return "Journal Article"


def _calculate_trust_score(paper: Dict) -> int:
    score = 0

    ptype_scores = [PTYPE_SCORE.get(pt, 0) for pt in paper.get("publication_types", [])]
    if ptype_scores:
        score += max(ptype_scores)

    journal_iso = paper.get("journal_iso", "")
    for key, bonus in JOURNAL_BONUS.items():
        if key.lower() == journal_iso.lower():
            score += bonus
            break

    abstract = paper.get("abstract", "")
    if len(abstract) > 1500:
        score += 5
    if "CONCLUSION" in abstract.upper() or "結論" in abstract:
        score += 3

    return score


def rank_papers(papers: List[Dict]) -> List[Dict]:
    return sorted(
        papers,
        key=lambda p: (p.get("trust_score", 0), int(p.get("pmid", "0")) if p.get("pmid", "").isdigit() else 0),
        reverse=True,
    )
