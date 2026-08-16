from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable

import requests

from .billing import add_usage, calculate_cost_cny, empty_usage, pricing_snapshot
from .models import Paper


OPENAI_RESPONSES_API = "https://api.openai.com/v1/responses"
CACHE_PATH = Path("data/ai_cache.json")
CACHE_SCHEMA_VERSION = "paperdaily-ai-cache-v2"
RANK_PROMPT_VERSION = "paperdaily-ranking-v1-2026-08"
SUMMARY_PROMPT_VERSION = "paperdaily-summary-v2-2026-08"
_RUN_USAGE: dict[str, int] = empty_usage()

PAPER_TYPES = (
    "Research Article",
    "Review",
    "Systematic Review",
    "Meta-analysis",
    "Methods/Resource",
    "Clinical Study",
    "Clinical Trial",
    "Case Report",
    "Protocol",
    "Commentary/Perspective",
    "Editorial",
    "Preprint",
    "Other",
)


def paper_key(paper: Paper) -> str:
    return f"{paper.source}:{paper.source_id}"


def _chunks(values: list[Paper], size: int) -> Iterable[list[Paper]]:
    for start in range(0, len(values), size):
        yield values[start:start + size]


def _provider_name(ai_config: dict) -> str:
    return str(ai_config.get("provider", "deepseek")).strip().lower()


def _api_key_env(ai_config: dict) -> str:
    explicit = str(ai_config.get("api_key_env", "")).strip()
    if explicit:
        return explicit
    return "OPENAI_API_KEY" if _provider_name(ai_config) == "openai" else "DEEPSEEK_API_KEY"


def _reset_run_usage() -> None:
    global _RUN_USAGE
    _RUN_USAGE = empty_usage()


def _record_usage(raw_usage: dict[str, Any] | None) -> None:
    global _RUN_USAGE
    if not raw_usage:
        return
    request_usage = dict(raw_usage)
    request_usage["requests"] = 1
    _RUN_USAGE = add_usage(_RUN_USAGE, request_usage)


def _finish_metadata(metadata: dict[str, Any], ai_config: dict) -> dict[str, Any]:
    usage = dict(_RUN_USAGE)
    pricing = pricing_snapshot(ai_config)
    metadata["usage"] = usage
    metadata["pricing_cny_per_million"] = pricing
    metadata["run_cost_cny"] = calculate_cost_cny(usage, pricing)
    return metadata


def _profile_hash(ai_config: dict) -> str:
    material = {
        "cache_schema": CACHE_SCHEMA_VERSION,
        "provider": _provider_name(ai_config),
        "model": ai_config.get("model", "deepseek-v4-flash"),
        "base_url": ai_config.get("base_url", ""),
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


def _openai_responses_json(api_key: str, model: str, prompt: str, schema_name: str, schema: dict) -> dict:
    response = requests.post(
        OPENAI_RESPONSES_API,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
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
    body = response.json()
    _record_usage(body.get("usage"))
    return json.loads(_extract_output_text(body))


def _chat_completions_json(
    api_key: str,
    model: str,
    prompt: str,
    schema_name: str,
    schema: dict,
    base_url: str,
    provider: str,
) -> dict:
    endpoint = base_url.rstrip("/") + "/chat/completions"
    json_instruction = (
        "Return JSON only. The output must be a valid JSON object matching this schema exactly. "
        f"Schema name: {schema_name}. JSON schema: {json.dumps(schema, ensure_ascii=False)}"
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": json_instruction},
            {"role": "user", "content": prompt + "\n\nReturn the requested result as JSON."},
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": 8192,
    }
    if provider == "deepseek":
        payload["thinking"] = {"type": "disabled"}

    last_error: Exception | None = None
    for _attempt in range(2):
        try:
            response = requests.post(
                endpoint,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=180,
            )
            if not response.ok:
                detail = response.text[:1200]
                raise RuntimeError(f"{provider} API HTTP {response.status_code}: {detail}")
            body = response.json()
            _record_usage(body.get("usage"))
            content = body.get("choices", [{}])[0].get("message", {}).get("content", "")
            if not content or not str(content).strip():
                raise ValueError(f"{provider} returned empty JSON content")
            parsed = json.loads(content)
            if not isinstance(parsed, dict):
                raise ValueError(f"{provider} JSON output was not an object")
            return parsed
        except (RuntimeError, ValueError, json.JSONDecodeError, requests.RequestException) as exc:
            last_error = exc
    assert last_error is not None
    raise last_error


def _provider_json(api_key: str, ai_config: dict, prompt: str, schema_name: str, schema: dict) -> dict:
    provider = _provider_name(ai_config)
    model = str(ai_config.get("model", "deepseek-v4-flash"))
    if provider == "openai":
        return _openai_responses_json(api_key, model, prompt, schema_name, schema)
    if provider == "deepseek":
        base_url = str(ai_config.get("base_url", "https://api.deepseek.com"))
    else:
        base_url = str(ai_config.get("base_url", "")).strip()
        if not base_url:
            raise ValueError(f"Provider {provider!r} requires ai.base_url")
    return _chat_completions_json(api_key, model, prompt, schema_name, schema, base_url, provider)


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
                        "keywords": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "paper_type": {"type": "string"},
                    },
                    "required": ["id", "summary", "keywords", "paper_type"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["items"],
        "additionalProperties": False,
    }


def _normalize_keywords(values: Any, fallback: list[str] | None = None) -> list[str]:
    candidates = values if isinstance(values, list) else []
    if not candidates and fallback:
        candidates = fallback
    result: list[str] = []
    seen: set[str] = set()
    for value in candidates:
        keyword = str(value).strip()
        marker = keyword.casefold()
        if not keyword or marker in seen:
            continue
        seen.add(marker)
        result.append(keyword[:100])
        if len(result) >= 5:
            break
    return result


def _normalize_paper_type(value: Any, publication_types: list[str] | None = None) -> str:
    raw = str(value or "").strip()
    for allowed in PAPER_TYPES:
        if raw.casefold() == allowed.casefold():
            return allowed

    source_text = " ".join(publication_types or []).casefold()
    if "meta-analysis" in source_text:
        return "Meta-analysis"
    if "systematic review" in source_text:
        return "Systematic Review"
    if "review" in source_text:
        return "Review"
    if "clinical trial" in source_text or "randomized controlled trial" in source_text:
        return "Clinical Trial"
    if "case reports" in source_text or "case report" in source_text:
        return "Case Report"
    if "protocol" in source_text:
        return "Protocol"
    if "editorial" in source_text:
        return "Editorial"
    if "comment" in source_text:
        return "Commentary/Perspective"
    if "journal article" in source_text:
        return "Research Article"
    if "preprint" in source_text:
        return "Preprint"
    return "Other"


def _rank_batch(api_key: str, ai_config: dict, profile: str, papers: list[Paper]) -> dict[str, dict[str, Any]]:
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
    result = _provider_json(api_key, ai_config, prompt, "paper_ranking", _ranking_schema())
    output: dict[str, dict[str, Any]] = {}
    for item in result.get("items", []):
        item_id = str(item.get("id", ""))
        if not item_id:
            continue
        output[item_id] = {
            "score": max(0, min(100, int(item.get("score", 0)))),
            "topic": str(item.get("topic", ""))[:120],
            "reason": str(item.get("reason", ""))[:600],
        }
    return output


def _summarize_batch(api_key: str, ai_config: dict, papers: list[Paper]) -> dict[str, dict[str, Any]]:
    records = [
        {
            "id": paper_key(p),
            "title": p.title,
            "journal": p.journal,
            "source": p.source,
            "authors": p.authors,
            "source_keywords": p.keywords,
            "publication_types": p.publication_types,
            "abstract": (p.abstract or "")[:5000],
        }
        for p in papers
    ]
    allowed_types = ", ".join(PAPER_TYPES)
    prompt = f"""You prepare a compact scientific reading list for a researcher.

For every supplied paper, use only the supplied title, metadata, and abstract. Do not invent findings.
Return three things for every paper:
1. summary: 1-2 compact sentences stating what the paper did and its most important reported result or contribution. Prefer concrete results over background.
2. keywords: 3-5 specific English scientific keywords or short phrases that best describe the paper. Prefer mechanisms, methods, models, species, signals, or core concepts over generic words such as study or neuroscience. Source keywords may be reused when informative.
3. paper_type: one normalized label from this exact set: {allowed_types}.

Use source publication_types as strong evidence when they are informative. For preprint servers, classify the scientific content when possible (for example Research Article or Review) rather than automatically using Preprint. Use English for all generated text.

PAPERS:
{json.dumps(records, ensure_ascii=False)}"""
    result = _provider_json(api_key, ai_config, prompt, "paper_summaries", _summary_schema())
    by_key = {paper_key(p): p for p in papers}
    output: dict[str, dict[str, Any]] = {}
    for item in result.get("items", []):
        item_id = str(item.get("id", ""))
        paper = by_key.get(item_id)
        if not item_id or paper is None:
            continue
        output[item_id] = {
            "summary": str(item.get("summary", ""))[:800],
            "keywords": _normalize_keywords(item.get("keywords"), paper.keywords),
            "paper_type": _normalize_paper_type(item.get("paper_type"), paper.publication_types),
        }
    return output


def apply_ai_ranking(papers: list[Paper], config: dict) -> dict[str, Any]:
    _reset_run_usage()
    ai_config = config.get("ai", {}) or {}
    requested = bool(ai_config.get("enabled", True))
    provider = _provider_name(ai_config)
    model = str(ai_config.get("model", "deepseek-v4-flash"))
    rank_batch_size = max(1, int(ai_config.get("rank_batch_size", 20)))
    summary_batch_size = max(1, int(ai_config.get("summary_batch_size", 5)))
    digest_min = max(1, int(ai_config.get("digest_min", 25)))
    digest_max = max(digest_min, int(ai_config.get("digest_max", 30)))
    digest_score_threshold = max(0, min(100, int(ai_config.get("digest_score_threshold", 45))))
    profile = str(ai_config.get("interest_profile", "")).strip()
    api_key_env = _api_key_env(ai_config)
    api_key = os.getenv(api_key_env, "").strip()

    metadata: dict[str, Any] = {
        "requested": requested,
        "enabled": False,
        "provider": provider,
        "model": model,
        "api_key_env": api_key_env,
        "ranked_count": 0,
        "newly_ranked": 0,
        "newly_summarized": 0,
        "digest_count": 0,
        "digest_min": digest_min,
        "digest_max": digest_max,
        "digest_score_threshold": digest_score_threshold,
        "rank_prompt_version": RANK_PROMPT_VERSION,
        "summary_prompt_version": SUMMARY_PROMPT_VERSION,
        "errors": [],
    }
    if not requested:
        metadata["status"] = "disabled_in_config"
        return _finish_metadata(metadata, ai_config)
    if not api_key:
        metadata["status"] = "missing_api_key"
        return _finish_metadata(metadata, ai_config)
    if not profile:
        metadata["status"] = "missing_interest_profile"
        return _finish_metadata(metadata, ai_config)

    profile_hash = _profile_hash(ai_config)
    cache = _load_cache(profile_hash)
    cached_papers: dict[str, dict] = cache["papers"]

    missing_rank = [
        p for p in papers
        if (
            not cached_papers.get(paper_key(p), {}).get("rank")
            or cached_papers.get(paper_key(p), {}).get("rank_version") != RANK_PROMPT_VERSION
        )
    ]
    for batch in _chunks(missing_rank, rank_batch_size):
        try:
            ranked = _rank_batch(api_key, ai_config, profile, batch)
            for p in batch:
                key = paper_key(p)
                if key in ranked:
                    entry = cached_papers.setdefault(key, {})
                    entry["rank"] = ranked[key]
                    entry["rank_version"] = RANK_PROMPT_VERSION
                    metadata["newly_ranked"] += 1
        except Exception as exc:
            metadata["errors"].append(f"ranking batch: {type(exc).__name__}: {exc}")

    scored: list[tuple[Paper, int]] = []
    for p in papers:
        entry = cached_papers.get(paper_key(p), {})
        rank = entry.get("rank") if entry.get("rank_version") == RANK_PROMPT_VERSION else None
        if rank:
            scored.append((p, int(rank.get("score", 0))))
    scored.sort(key=lambda pair: (pair[1], pair[0].indexed_date or pair[0].published_date), reverse=True)

    threshold_picks = [pair for pair in scored if pair[1] >= digest_score_threshold][:digest_max]
    minimum = min(digest_min, len(scored))
    if len(threshold_picks) < minimum:
        digest_pairs = scored[:minimum]
    else:
        digest_pairs = threshold_picks
    digest_pairs = digest_pairs[:digest_max]
    digest_keys = {paper_key(p) for p, _ in digest_pairs}

    needs_summary = [
        p for p, _ in digest_pairs
        if (
            not cached_papers.get(paper_key(p), {}).get("summary")
            or cached_papers.get(paper_key(p), {}).get("summary_version") != SUMMARY_PROMPT_VERSION
        )
    ]
    for batch in _chunks(needs_summary, summary_batch_size):
        try:
            summaries = _summarize_batch(api_key, ai_config, batch)
            for p in batch:
                key = paper_key(p)
                if key in summaries:
                    entry = cached_papers.setdefault(key, {})
                    entry["summary"] = summaries[key]["summary"]
                    entry["keywords"] = summaries[key]["keywords"]
                    entry["paper_type"] = summaries[key]["paper_type"]
                    entry["summary_version"] = SUMMARY_PROMPT_VERSION
                    metadata["newly_summarized"] += 1
        except Exception as exc:
            metadata["errors"].append(f"summary batch: {type(exc).__name__}: {exc}")

    for p in papers:
        key = paper_key(p)
        entry = cached_papers.get(key, {})
        rank = entry.get("rank") if entry.get("rank_version") == RANK_PROMPT_VERSION else None
        if not rank:
            continue
        summary_ok = entry.get("summary_version") == SUMMARY_PROMPT_VERSION
        p.extra["ai"] = {
            "score": int(rank.get("score", 0)),
            "topic": rank.get("topic", ""),
            "reason": rank.get("reason", ""),
            "summary": entry.get("summary", "") if summary_ok else "",
            "keywords": _normalize_keywords(entry.get("keywords"), p.keywords) if summary_ok else p.keywords[:5],
            "paper_type": _normalize_paper_type(entry.get("paper_type"), p.publication_types) if summary_ok else _normalize_paper_type("", p.publication_types),
            "digest_pick": key in digest_keys,
        }

    _save_cache(cache)
    metadata["ranked_count"] = len(scored)
    metadata["digest_count"] = len(digest_pairs)
    metadata["enabled"] = bool(scored)
    metadata["status"] = "active" if scored else "ai_unavailable"
    metadata["profile_hash"] = profile_hash
    return _finish_metadata(metadata, ai_config)
