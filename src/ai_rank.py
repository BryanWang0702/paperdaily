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
PROMPT_VERSION = "paperdaily-v0.3-inline-digest-2026-08"
_RUN_USAGE: dict[str, int] = empty_usage()


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
        "prompt_version": PROMPT_VERSION,
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
                        "summary": {"type": "string"},
                    },
                    "required": ["id", "score", "topic", "reason", "summary"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["items"],
        "additionalProperties": False,
    }


def _rank_batch(api_key: str, ai_config: dict, profile: str, papers: list[Paper]) -> dict[str, dict[str, Any]]:
    records = [
        {
            "id": paper_key(p),
            "title": p.title,
            "journal": p.journal,
            "source": p.source,
            "abstract": (p.abstract or "")[:3000],
        }
        for p in papers
    ]
    prompt = f"""You are the ranking and digest layer of a personal scientific literature radar.

RESEARCHER INTEREST PROFILE:
{profile}

For EVERY candidate, do two things in the same pass:
1. Score relevance to this specific researcher from 0-100.
2. Write a compact 1-2 sentence scientific summary based only on the supplied title/abstract. State what was done and the most important result or contribution. Do not invent details.

Relevance scale:
- 90-100: directly addresses a current core question/project or a highly transferable method.
- 70-89: strongly relevant background, mechanism, dataset, or method.
- 40-69: adjacent and occasionally useful.
- 0-39: weakly related, keyword collision, broad clinical/general content, or outside likely needs.

Also return a short topic label and one concise reason for the score. Keep the summary compact because it will be shown directly in a daily reading list. Process every supplied id exactly once.

CANDIDATES:
{json.dumps(records, ensure_ascii=False)}"""
    result = _provider_json(api_key, ai_config, prompt, "paper_ranking_digest", _ranking_schema())
    output: dict[str, dict[str, Any]] = {}
    for item in result.get("items", []):
        item_id = str(item.get("id", ""))
        if not item_id:
            continue
        output[item_id] = {
            "score": max(0, min(100, int(item.get("score", 0)))),
            "topic": str(item.get("topic", ""))[:120],
            "reason": str(item.get("reason", ""))[:500],
            "summary": str(item.get("summary", ""))[:700],
        }
    return output


def apply_ai_ranking(papers: list[Paper], config: dict) -> dict[str, Any]:
    _reset_run_usage()
    ai_config = config.get("ai", {}) or {}
    requested = bool(ai_config.get("enabled", True))
    provider = _provider_name(ai_config)
    model = str(ai_config.get("model", "deepseek-v4-flash"))
    rank_batch_size = max(1, int(ai_config.get("rank_batch_size", 20)))
    digest_min = max(1, int(ai_config.get("digest_min", 20)))
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

    missing_rank = [p for p in papers if not cached_papers.get(paper_key(p), {}).get("rank")]
    for batch in _chunks(missing_rank, rank_batch_size):
        try:
            ranked = _rank_batch(api_key, ai_config, profile, batch)
            for p in batch:
                key = paper_key(p)
                if key in ranked:
                    cached_papers.setdefault(key, {})["rank"] = ranked[key]
                    metadata["newly_ranked"] += 1
                    if ranked[key].get("summary"):
                        metadata["newly_summarized"] += 1
        except Exception as exc:
            metadata["errors"].append(f"ranking batch: {type(exc).__name__}: {exc}")

    scored: list[tuple[Paper, int]] = []
    for p in papers:
        rank = cached_papers.get(paper_key(p), {}).get("rank")
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

    for p in papers:
        key = paper_key(p)
        rank = cached_papers.get(key, {}).get("rank")
        if not rank:
            continue
        p.extra["ai"] = {
            "score": int(rank.get("score", 0)),
            "topic": rank.get("topic", ""),
            "reason": rank.get("reason", ""),
            "summary": rank.get("summary", ""),
            "digest_pick": key in digest_keys,
        }

    _save_cache(cache)
    metadata["ranked_count"] = len(scored)
    metadata["digest_count"] = len(digest_pairs)
    metadata["enabled"] = bool(scored)
    metadata["status"] = "active" if scored else "ai_unavailable"
    metadata["profile_hash"] = profile_hash
    return _finish_metadata(metadata, ai_config)
