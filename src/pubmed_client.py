"""PubMed E-utilities API クライアント（信頼度スコアリング付き）。"""
import time
import xml.etree.ElementTree as ET
from typing import Dict, List

import requests

from config import PUBMED_API_KEY, PUBMED_EMAIL, PUBMED_RELDATE_DAYS

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

# ============================================================
# 信頼度スコア（大きいほど教育的価値が高い）
# ============================================================
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

# 主要誌の加点
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
        # 期間フィルタ: 直近 N 日（publication date 基準）
        "datetype": "pdat",
        "reldate": str(PUBMED_RELDATE_DAYS),
        **_common_params(),
    }
    r = requests.get(f"{BASE_URL}/esearch.fcgi", params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data.get("esearchresult", {}).get("idlist", [])


def fetch_paper_details(pmids: List[str]) -> List[Dict]:
    """PMID リストから論文詳細を取得し、信頼度スコア付きで返す。"""
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

    for article in root.findall(".//PubmedArticle"):
        try:
            paper = _parse_article(article)
            if paper and paper.get("abstract"):
                paper["trust_score"] = _calculate_trust_score(paper)
                papers.append(paper)
        except Exception as e:
            print(f"[warn] Parse error for one article: {e}")
            continue
        time.sleep(0.1)

    return papers


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
    }


def _select_primary_ptype(ptypes: List[str]) -> str:
    """複数の Publication Type から、最も重要なものを 1 つ選ぶ。"""
    for priority in PRIORITY_PTYPES:
        if priority in ptypes:
            return priority
    for pt in ptypes:
        if pt and pt != "Journal Article":
            return pt
    return "Journal Article"


def _calculate_trust_score(paper: Dict) -> int:
    """論文の信頼度スコアを計算する。"""
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
    """信頼度スコアの降順に並び替える。同点は出版日時が新しい順（PMID降順）。"""
    return sorted(
        papers,
        key=lambda p: (p.get("trust_score", 0), int(p.get("pmid", "0")) if p.get("pmid", "").isdigit() else 0),
        reverse=True,
    )
