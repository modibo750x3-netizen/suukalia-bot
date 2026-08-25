"""Contrat commun a tous les fournisseurs de donnees."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Protocol, runtime_checkable

from ..models import Match, MatchResult


@runtime_checkable
class OddsProvider(Protocol):
    """Fournit les cotes des matchs a venir."""

    name: str

    def fetch_matches(self, league: str) -> list[Match]: ...


@runtime_checkable
class ResultsProvider(Protocol):
    """Fournit l'historique des resultats, pour entrainer et backtester."""

    name: str

    def fetch_results(self, league: str) -> list[MatchResult]: ...


class ProviderError(RuntimeError):
    """Erreur remontee par un fournisseur (reseau, quota, format)."""


def http_get_json(
    url: str,
    params: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 20.0,
) -> Any:
    """GET JSON minimaliste, sur la stdlib.

    Volontairement sans `requests` : le projet reste installable partout sans
    resoudre de dependances, ce qui compte pour un bot qui tourne en cron sur
    une petite machine.
    """
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        if exc.code == 401:
            raise ProviderError("cle API refusee (401) : verifier le fichier .env") from exc
        if exc.code == 429:
            raise ProviderError("quota API depasse (429) : espacer les appels") from exc
        raise ProviderError(f"erreur HTTP {exc.code} : {detail}") from exc
    except urllib.error.URLError as exc:
        raise ProviderError(f"reseau indisponible : {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise ProviderError(f"reponse non-JSON du fournisseur : {exc}") from exc
