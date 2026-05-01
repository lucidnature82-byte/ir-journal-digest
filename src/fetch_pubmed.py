import logging
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Optional

import requests

from .config import NCBI_API_KEY, FETCH_DAYS

logger = logging.getLogger(__name__)

BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
_DELAY = 0.11 if NCBI_API_KEY else 0.34  # stay within NCBI rate limits


def _params(extra: dict) -> dict:
    p = {"retmode": "json", **extra}
    if NCBI_API_KEY:
        p["api_key"] = NCBI_API_KEY
    return p


def search_pmids(journal_query: str, days: int = FETCH_DAYS) -> list[str]:
    date_from = (datetime.now() - timedelta(days=days)).strftime("%Y/%m/%d")
    date_to = datetime.now().strftime("%Y/%m/%d")

    params = _params({
        "db": "pubmed",
        "term": f'{journal_query} AND "{date_from}"[PDAT]:"{date_to}"[PDAT]',
        "retmax": 300,
        "usehistory": "y",
    })

    resp = requests.get(BASE_URL + "esearch.fcgi", params=params, timeout=30)
    resp.raise_for_status()
    time.sleep(_DELAY)

    data = resp.json()
    pmids: list[str] = data["esearchresult"]["idlist"]
    logger.info("  Found %d PMIDs for query: %s", len(pmids), journal_query)
    return pmids


def fetch_articles(pmids: list[str]) -> list[dict]:
    if not pmids:
        return []

    params: dict = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "rettype": "xml",
        "retmode": "xml",
    }
    if NCBI_API_KEY:
        params["api_key"] = NCBI_API_KEY

    resp = requests.get(BASE_URL + "efetch.fcgi", params=params, timeout=90)
    resp.raise_for_status()
    time.sleep(_DELAY)

    return _parse_pubmed_xml(resp.text)


def _parse_pubmed_xml(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    articles = []
    for node in root.findall(".//PubmedArticle"):
        try:
            art = _parse_article(node)
            if art:
                articles.append(art)
        except Exception as exc:
            logger.warning("Failed to parse article node: %s", exc)
    return articles


def _parse_article(node: ET.Element) -> Optional[dict]:
    medline = node.find("MedlineCitation")
    if medline is None:
        return None

    pmid_el = medline.find("PMID")
    pmid = pmid_el.text if pmid_el is not None else None
    if not pmid:
        return None

    art = medline.find("Article")
    if art is None:
        return None

    title = "".join((art.find("ArticleTitle") or ET.Element("x")).itertext()).strip()

    abstract = _extract_abstract(art)

    authors = _extract_authors(art)

    journal_abbr = medline.findtext("MedlineJournalInfo/MedlineTA") or ""

    pub_date = _extract_date(art)

    doi = ""
    for id_el in node.findall(".//ArticleId"):
        if id_el.get("IdType") == "doi":
            doi = (id_el.text or "").strip()
            break

    return {
        "pmid": pmid,
        "doi": doi,
        "title": title,
        "abstract": abstract,
        "authors": authors,
        "journal_abbr": journal_abbr,
        "pub_date": pub_date,
        "journal": "",          # filled by caller
        "is_interest": False,
        "interest_category": None,
        "summary": None,
    }


def _extract_abstract(art: ET.Element) -> str:
    abstract_el = art.find("Abstract")
    if abstract_el is None:
        return ""
    parts = []
    for el in abstract_el.findall("AbstractText"):
        label = el.get("Label", "")
        text = "".join(el.itertext()).strip()
        parts.append(f"{label}: {text}" if label else text)
    return " ".join(parts)


def _extract_authors(art: ET.Element) -> list[str]:
    author_list = art.find("AuthorList")
    if author_list is None:
        return []
    authors = []
    for author in author_list.findall("Author"):
        last = author.findtext("LastName", "")
        fore = author.findtext("ForeName", "")
        name = f"{last} {fore}".strip()
        if name:
            authors.append(name)
    return authors


def _extract_date(art: ET.Element) -> str:
    for date_el in art.findall("ArticleDate"):
        y = date_el.findtext("Year", "")
        m = date_el.findtext("Month", "01").zfill(2)
        d = date_el.findtext("Day", "01").zfill(2)
        if y:
            return f"{y}-{m}-{d}"

    pub = art.find("Journal/JournalIssue/PubDate")
    if pub is not None:
        y = pub.findtext("Year", "")
        raw_m = pub.findtext("Month", "1")
        d = pub.findtext("Day", "1")
        if y:
            try:
                month_int = int(raw_m) if raw_m.isdigit() else datetime.strptime(raw_m[:3], "%b").month
                return f"{y}-{str(month_int).zfill(2)}-{str(d).zfill(2) if d.isdigit() else '01'}"
            except ValueError:
                return f"{y}-01-01"

    return datetime.now().strftime("%Y-%m-%d")
