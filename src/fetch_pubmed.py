import logging
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Optional

import requests

from .config import NCBI_API_KEY, FETCH_DAYS, PUBMED_DATE_FIELD

logger = logging.getLogger(__name__)

BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
_DELAY = 0.11 if NCBI_API_KEY else 0.34
_EFETCH_BATCH = 100  # PubMed recommends ≤ 200; 100 is safe for GET URL length


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
        "term": f'{journal_query} AND "{date_from}"[{PUBMED_DATE_FIELD}]:"{date_to}"[{PUBMED_DATE_FIELD}]',
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
    """Fetch articles in batches to avoid URL-length issues and PubMed limits."""
    if not pmids:
        return []

    all_articles: list[dict] = []
    for i in range(0, len(pmids), _EFETCH_BATCH):
        batch = pmids[i : i + _EFETCH_BATCH]
        logger.info(
            "  efetch batch %d-%d / %d ...",
            i + 1, min(i + _EFETCH_BATCH, len(pmids)), len(pmids),
        )
        try:
            articles = _fetch_batch(batch)
            all_articles.extend(articles)
        except Exception as exc:
            logger.error("efetch batch %d-%d failed: %s", i + 1, i + len(batch), exc)
        if i + _EFETCH_BATCH < len(pmids):
            time.sleep(_DELAY)

    return all_articles


def _fetch_batch(pmids: list[str]) -> list[dict]:
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
    # PubMed XML may contain undefined named entities (&alpha; etc.) not in
    # the internal subset.  Replace the external DOCTYPE reference with an
    # inline subset that declares the most common ones so ElementTree won't
    # raise ParseError.  We strip the DOCTYPE entirely to avoid network fetch.
    if "<!DOCTYPE" in xml_text:
        start = xml_text.find("<!DOCTYPE")
        end = xml_text.find(">", start) + 1
        xml_text = xml_text[:start] + xml_text[end:]

    try:
        root = ET.fromstring(xml_text.encode("utf-8"))
    except ET.ParseError as exc:
        logger.error("XML ParseError for PubMed response: %s", exc)
        logger.debug("First 500 chars of XML: %s", xml_text[:500])
        return []

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

    title_el = art.find("ArticleTitle")
    if title_el is not None:
        title = "".join(title_el.itertext()).strip()
    else:
        title = ""

    if not title:
        # Fallback: VernacularTitle sometimes carries the real title
        vt_el = art.find("VernacularTitle")
        if vt_el is not None:
            title = "".join(vt_el.itertext()).strip()

    if not title:
        logger.warning("PMID %s: ArticleTitle is empty or missing", pmid)

    abstract = _extract_abstract(art)
    if not abstract:
        logger.debug("PMID %s: abstract empty (article type may lack abstract)", pmid)
    else:
        logger.debug("PMID %s: abstract length %d chars", pmid, len(abstract))

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
        "journal": "",
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
        if text:
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
