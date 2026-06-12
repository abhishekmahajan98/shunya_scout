import json
import os
import re

from openai import OpenAI


def _get_client() -> OpenAI:
    api_key = os.environ.get("PERPLEXITY_API_KEY")
    if not api_key:
        raise ValueError("PERPLEXITY_API_KEY environment variable is not set")
    # max_retries=1 → at most 2 HTTP attempts per call (no SDK retry storms).
    return OpenAI(api_key=api_key, base_url="https://api.perplexity.ai", max_retries=1)


def _extract_json(text: str) -> str:
    text = text.strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence_match:
        return fence_match.group(1).strip()
    bracket_match = re.search(r"(\[[\s\S]*\]|\{[\s\S]*\})", text)
    if bracket_match:
        return bracket_match.group(1).strip()
    return text


def query_perplexity(system_prompt: str, user_prompt: str) -> str:
    client = _get_client()
    response = client.chat.completions.create(
        model="sonar-pro",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    content = response.choices[0].message.content
    if not content:
        raise ValueError("Perplexity returned an empty response")
    return content


def query_perplexity_json(system_prompt: str, user_prompt: str) -> list[dict]:
    raw = query_perplexity(system_prompt, user_prompt)
    cleaned = _extract_json(raw)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Perplexity returned invalid JSON: {exc}. Raw output: {raw[:500]}"
        ) from exc

    if isinstance(parsed, dict):
        for key in ("matches", "games", "fixtures", "data"):
            if key in parsed and isinstance(parsed[key], list):
                return parsed[key]
        raise ValueError(f"Unexpected JSON object keys from Perplexity: {parsed.keys()}")

    if isinstance(parsed, list):
        return parsed

    raise ValueError(f"Unexpected JSON structure from Perplexity: {type(parsed)}")
