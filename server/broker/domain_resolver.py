"""
Time Series Commons — Domain Resolver

Loads data/domain-config.json (the same config used by the front-end) and
maps an arbitrary raw domain string to one of the 15 canonical domain buckets,
along with the associated image path and brand colour.

Matching strategy (in priority order):
  1. Exact case-insensitive match on a canonical domain name (e.g. "energy" → "Energy")
  2. Substring keyword match — each canonical domain declares a list of keywords;
     the first domain whose *any* keyword appears in the lowercased input wins.
     Keywords are tried longest-first so that "electricity consumption" beats
     the shorter "electricity" and avoids accidental short-string collisions.
  3. Fallback → "Synthetic" (covers cross-domain, unknown, and empty inputs)

Usage:
    from domain_resolver import DomainResolver

    resolver = DomainResolver("/path/to/data/domain-config.json")
    result   = resolver.resolve("Device (Energy Consumption)")
    # → {"canonical": "Energy", "image": "pics/domains/energy.jpg", "color": "#f39c12"}
"""

import json
import os
import logging
from typing import TypedDict

log = logging.getLogger(__name__)

FALLBACK_DOMAIN = "Synthetic"


class DomainResult(TypedDict):
    canonical: str
    image: str
    color: str


class DomainResolver:
    """
    Thread-safe, single-load domain resolver.
    Instantiate once at application startup and call resolve() freely from any thread.
    """

    def __init__(self, config_path: str) -> None:
        """
        Load and pre-process domain-config.json.

        config_path — absolute path to data/domain-config.json
        """
        if not os.path.isfile(config_path):
            raise FileNotFoundError(
                f"DomainResolver: config not found at {config_path!r}. "
                "Set DOMAIN_CONFIG_PATH in your .env file."
            )

        with open(config_path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        self._domains: dict[str, dict] = raw.get("domains", {})

        # Build a sorted keyword index: [(keyword_lower, canonical_name), ...]
        # Sorted longest-first so longer phrases match before shorter substrings.
        self._keyword_index: list[tuple[str, str]] = []
        for canonical, cfg in self._domains.items():
            for kw in cfg.get("keywords", []):
                self._keyword_index.append((kw.lower(), canonical))

        self._keyword_index.sort(key=lambda t: len(t[0]), reverse=True)

        # Build exact-match lookup: lowercased canonical name → canonical name
        self._exact_lookup: dict[str, str] = {
            name.lower(): name for name in self._domains
        }

        log.info(
            "DomainResolver loaded: %d canonical domains, %d keywords",
            len(self._domains),
            len(self._keyword_index),
        )

    def resolve(self, domain_text: str) -> DomainResult:
        """
        Resolve a raw domain string to a canonical domain bucket.

        Parameters
        ----------
        domain_text : str
            The raw domain label from DeepCollector or another producer,
            e.g. "Device (Energy Consumption)", "ECG", "Air Quality", "".

        Returns
        -------
        DomainResult
            {"canonical": str, "image": str, "color": str}
        """
        normalized = (domain_text or "").strip().lower()

        # 1. Exact match on canonical name
        if normalized in self._exact_lookup:
            canonical = self._exact_lookup[normalized]
            return self._make_result(canonical)

        # 2. Keyword substring match (longest keyword first)
        if normalized:
            for keyword, canonical in self._keyword_index:
                if keyword in normalized:
                    return self._make_result(canonical)

        # 3. Fallback
        log.debug(
            "DomainResolver: no match for %r — falling back to %r",
            domain_text,
            FALLBACK_DOMAIN,
        )
        return self._make_result(FALLBACK_DOMAIN)

    def _make_result(self, canonical: str) -> DomainResult:
        cfg = self._domains.get(canonical, {})
        return DomainResult(
            canonical=canonical,
            image=cfg.get("image", f"pics/domains/{canonical.lower()}.jpg"),
            color=cfg.get("color", "#888888"),
        )

    def canonical_names(self) -> list[str]:
        """Return all canonical domain names in config order."""
        return list(self._domains.keys())
