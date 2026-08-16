from __future__ import annotations

import os
import xml.etree.ElementTree as ET

import requests

from .models import Paper
from .utils import chunks, compact_text, normalize_doi


EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def _text(node: ET.Element | None) -> str:
    return compact_text("" if node is None else "".join(node.itertext()))


def _pub_date(article: ET.Element) -> str:
    node = article.find("./MedlineCitation/Article/Journal/JournalIssue/PubDate")
    if node is None:
        return ""
    year = _text(node.find("Year"))
    month = _text(node.find("Month"))
    day = _text(node.find("Day"))
    medline = _text(node.find("MedlineDate"))
    if year:
        value = "-".join(x for x in (year, month, day) if x)
        return value
    return medline


def fetch_pubmed(config: dict, start_date: str, end_date: str, limit: int = 150) -> list[Paper]:
    terms = config.get("discovery_terms", [])
    if not terms:
        return []

    term_query = " OR ".join(f'"{term}"[Title/Abstract]' for term in terms)
    query = f"({term_query}) AND ({start_date}[crdt] : {end_date}[crdt])"
    pubmed_cfg = config.get("pubmed", {})
    email = os.getenv("PUBMED_EMAIL", "").strip() or str(pubmed_cfg.get("email", "")).strip()
    api_key = os.getenv("NCBI_API_KEY", "").strip()
    common = {"tool": pubmed_cfg.get("tool", "paperdaily")}
    if email:
        common["email"] = email
    if api_key:
        common["api_key"] = api_key

    response = requests.get(
        f"{EUTILS}/esearch.fcgi",
        params={"db": "pubmed", "term": query, "retmode": "json", "retmax": limit, **common},
        timeout=30,
    )
    response.raise_for_status()
    ids = response.json().get("esearchresult", {}).get("idlist", [])
    if not ids:
        return []

    papers: list[Paper] = []
    for batch in chunks(ids, 100):
        fetched = requests.get(
            f"{EUTILS}/efetch.fcgi",
            params={"db": "pubmed", "id": ",".join(batch), "retmode": "xml", **common},
            timeout=45,
        )
        fetched.raise_for_status()
        root = ET.fromstring(fetched.content)

        for record in root.findall("PubmedArticle"):
            citation = record.find("MedlineCitation")
            article = citation.find("Article") if citation is not None else None
            if citation is None or article is None:
                continue

            pmid = _text(citation.find("PMID"))
            title = _text(article.find("ArticleTitle"))
            abstract = " ".join(_text(x) for x in article.findall("Abstract/AbstractText"))
            authors = []
            for author in article.findall("AuthorList/Author"):
                collective = _text(author.find("CollectiveName"))
                full = " ".join(x for x in (_text(author.find("ForeName")), _text(author.find("LastName"))) if x)
                if collective or full:
                    authors.append(collective or full)

            doi = ""
            for aid in record.findall("./PubmedData/ArticleIdList/ArticleId"):
                if aid.attrib.get("IdType") == "doi":
                    doi = normalize_doi(_text(aid))
                    break

            journal = _text(article.find("Journal/Title"))
            indexed = _text(citation.find("DateCompleted/Year"))
            if indexed:
                indexed = "-".join(
                    x for x in (
                        indexed,
                        _text(citation.find("DateCompleted/Month")),
                        _text(citation.find("DateCompleted/Day")),
                    ) if x
                )

            papers.append(Paper(
                source="pubmed",
                source_id=pmid,
                title=title,
                abstract=compact_text(abstract),
                authors=authors,
                published_date=_pub_date(record),
                indexed_date=indexed,
                journal=journal,
                doi=doi,
                url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
            ))

    return papers
