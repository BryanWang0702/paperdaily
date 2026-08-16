from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable

import requests

from .models import Paper


RESPONSES_API = "https://api.openai.com/v1/responses"
CACHE_PATH = Path("data/ai_cache.json")
PROMPT_VERSION = "paperdaily-v0.2-2026-08"


def paper_key(paper: Paper) -> str:
    return f"{paper.source}:{paper.source_id}"


def _chunks(values: list[Paper], size: int) -> Iterable[list[Paper]]:
    for start in range(0, len(values), size):
        yield values[start:start + size]


def _profile_hash(ai_config: dict) -> str:
    material = {
        "prompt_version": PROMPT_VERSION,
        "model": ai_config.get("model", "gpt-5.6"),
        "interest_profile": ai_config.get("interest_profile", ""),
    }
    raw = json.dumps(material, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:20]


def _load_cache(profile_hash: str) -> dict:
    if CACHE_PATH.exists():
        try:
            cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            if cache.get("profile_hash") == profile_hash:
                cache.setdefault("papers", {})
                return cache
        except (OSError, json.JSONDecodeError):
            pass
    return {"profile_hash": profile_hash, "papers": {}}


def _save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def _extract_output_text(response_json: dict) -> str:
    for item in response_json.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                return content["text"]
    raise ValueError("OpenAI response did not contain output_text")


def _responses_json(api_key: str, model: str, prompt: str, schema_name: str, schema: dict) -> dict:
    response = requests.post(
        RESPONSES_API,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "input": prompt,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                }
            },
        },
        timeout=180,
    )
    if not response.ok:
        detail = response.text[:1200]
        raise RuntimeError(f"OpenAI API HTTP {response.status_code}: {detail}")
    return json.loads(_extract_output_text(response.json()))


def _ranking_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "score": {"type": "integer"},
                        "topic": {"type": "string"},
                        "reason": {"type": "string"},
                    },
                    "required": ["id", "score", "topic", "reason"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["items"],
        "additionalProperties": False,
    }


def _summary_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "summary": {"type": "string"},
                        "key_finding": {"type": "string"},
                        "why_relevant": {"type": "string"},
                    },
                    "required": ["id", "summary", "key_finding", "why_relevant"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["items"],
        "additionalProperties": False,
    }


def _rank_batch(api_key: str, model: str, profile: str, papers: list[Paper]) -> dict[str, dict[str, Any]]:
    records = [
        {
            "id": paper_key(p),
            "title": p.title,
            "journal": p.journal,
            "source": p.source,
            "abstract": (p.abstract or "")[:1200],
        }
        for p in papers
    ]
    prompt = f"""You are the ranking layer of a personal scientific literature radar.

RESEARCHER INTEREST PROFILE:
{profile}

Score each candidate for relevance to this specific researcher, not for general scientific quality.
Use a 0-100 scale:
- 90-100: directly addresses a current core question/project or provides a highly transferable method.
- 70-89: strongly relevant background, mechanism, dataset, or method.
- 40-69: adjacent and occasionally useful.
- 0-39: weakly related, keyword collision, broad clinical/general content, or outside the researcher's likely needs.

Give a short topic label and one concise reason for the score. Score every supplied id exactly once.

CANDIDATES:
{json.dumps(records, ensure_ascii=False)}"""
    result = _responses_json(api_key, model, prompt, "paper_ranking", _ranking_schema())
    output: dict[str, dict[str, Any]] = {}
    for item in result.get("items", []):
        item_id = str(item.get("id", ""))
        if not item_id:
            continue
        score = max(0, min(100, int(item.get("score", 0))))
        output[item_id] = {
            "score": score,
            "topic": str(item.get("topic", ""))[:120],
            "reason": str(item.get("reason", ""))[:600],
        }
    return output


def _summarize_batch(api_key: str, model: str, profile: str, papers: list[Paper]) -> dict[str, dict[str, str]]:
    records = [
        {
            "id": paper_key(p),
            "title": p.title,
            "journal": p.journal,
            "authors": p.authors[:8],
            "abstract": (p.abstract or "")[:5000],
        }
        for p in papers
    ]
    prompt = f"""You prepare concise reading notes for a neuroscience researcher.

RESEARCHER INTEREST PROFILE:
{profile}

For each paper, use only the supplied metadata/abstract. Do not invent results that are not stated.
Return:
- summary: 1-2 concise sentences describing what the paper did and found.
- key_finding: the single most important reported finding or contribution.
- why_relevant: 1-2 sentences explaining specifically why this researcher may want to read it. If relevance is methodological rather than topical, say so.

PAPERS:
{json.dumps(records, ensure_ascii=False)}"""
    result = _responses_json(api_key, model, prompt, "paper_summaries", _summary_schema())
    output: dict[str, dict[str, str]] = {}
    for item in result.get("items", []):
        item_id = str(item.get("id", ""))
        if not item_id:
            continue
        output[item_id] = {
            "summary": str(item.get("summary", ""))[:1600],
            "key_finding": str(item.get("key_finding", ""))[:1000],
            "why_relevant": str(item.get("why_relevant", ""))[:1600],
        }
    return output


def apply_ai_ranking(papers: list[Paper], config: dict) -> dict[str, Any]:
    ai_config = config.get("ai", {}) or {}
    requested = bool(ai_config.get("enabled", True))
    model = str(ai_config.get("model", "gpt-5.6"))
    top_n = max(1, int(ai_config.get("top_n", 15)))
    rank_batch_size = max(1, int(ai_config.get("rank_batch_size", 20)))
    summary_batch_size = max(1, int(ai_config.get("summary_batch_size", 5)))
    profile = str(ai_config.get("interest_profile", "")).strip()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()

    metadata: dict[str, Any] = {
        "requested": requested,
        "enabled": False,
        "model": model,
        "top_n": top_n,
        "ranked_count": 0,
        "newly_ranked": 0,
        "newly_summarized": 0,
        "errors": [],
    }
    if not requested:
        metadata["status"] = "disabled_in_config"
        return metadata
    if not api_key:
        metadata["status"] = "missing_api_key"
        return metadata
    if not profile:
        metadata["status"] = "missing_interest_profile"
        return metadata

    profile_hash = _profile_hash(ai_config)
    cache = _load_cache(profile_hash)
    cached_papers: dict[str, dict] = cache["papers"]

    missing_rank = [p for p in papers if not cached_papers.get(paper_key(p), {}).get("rank")]
    for batch in _chunks(missing_rank, rank_batch_size):
        try:
            ranked = _rank_batch(api_key, model, profile, batch)
            for p in batch:
                key = paper_key(p)
                if key in ranked:
                    cached_papers.setdefault(key, {})["rank"] = ranked[key]
                    metadata["newly_ranked"] += 1
        except Exception as exc:
            metadata["errors"].append(f"ranking batch: {type(exc).__name__}: {exc}")

    scored: list[tuple[Paper, int]] = []
    for p in papers:
        rank = cached_papers.get(paper_key(p), {}).get("rank")
        if rank:
            scored.append((p, int(rank.get("score", 0))))
    scored.sort(key=lambda pair: (pair[1], pair[0].indexed_date or pair[0].published_date), reverse=True)
    top_keys = {paper_key(p) for p, _ in scored[:top_n]}

    needs_summary = [
        p for p, _ in scored[:top_n]
        if not cached_papers.get(paper_key(p), {}).get("summary")
    ]
    for batch in _chunks(needs_summary, summary_batch_size):
        try:
            summaries = _summarize_batch(api_key, model, profile, batch)
            for p in batch:
                key = paper_key(p)
                if key in summaries:
                    cached_papers.setdefault(key, {})["summary"] = summaries[key]
                    metadata["newly_summarized"] += 1
        except Exception as exc:
            metadata["errors"].append(f"summary batch: {type(exc).__name__}: {exc}")

    for p in papers:
        key = paper_key(p)
        entry = cached_papers.get(key, {})
        rank = entry.get("rank")
        if not rank:
            continue
        ai = {
            "score": int(rank.get("score", 0)),
            "topic": rank.get("topic", ""),
            "reason": rank.get("reason", ""),
            "top_pick": key in top_keys,
        }
        if entry.get("summary"):
            ai.update(entry["summary"])
        p.extra["ai"] = ai

    _save_cache(cache)
    metadata["ranked_count"] = len(scored)
    metadata["enabled"] = bool(scored)
    metadata["status"] = "active" if scored else "ai_unavailable"
    metadata["profile_hash"] = profile_hash
    return metadata
