"""API layer: talks to the openFDA Drug Label REST API and parses its JSON."""
import re
from dataclasses import dataclass, field

import requests

from botika import config


class ApiError(Exception):
    """Base class. The message is written for the end user."""


class ApiConnectionError(ApiError):
    pass


class ApiTimeoutError(ApiError):
    pass


class ApiRateLimitError(ApiError):
    pass


class ApiHTTPError(ApiError):
    pass


class ApiNoResultsError(ApiError):
    pass


class ApiResponseError(ApiError):
    pass


@dataclass
class DrugInfo:
    generic_name: str
    brand_names: list = field(default_factory=list)
    purpose: str = ""
    indications: str = ""
    warnings: str = ""
    dosage: str = ""

    def to_text(self) -> str:
        parts = [f"Generic name: {self.generic_name}"]
        if self.brand_names:
            parts.append("FDA brand names: " + ", ".join(self.brand_names[:5]))
        for title, body in (("PURPOSE", self.purpose),
                            ("INDICATIONS AND USAGE", self.indications),
                            ("WARNINGS", self.warnings),
                            ("DOSAGE AND ADMINISTRATION", self.dosage)):
            if body:
                parts.append(f"\n{title}\n{body}")
        parts.append("\nSource: openFDA drug label data (U.S. labeling). "
                     "For reference only; not medical advice.")
        return "\n".join(parts)


def _clean(value, limit=config.API_TEXT_LIMIT) -> str:
    """openFDA returns a list of strings (or a string); flatten and shorten it."""
    if isinstance(value, list):
        value = " ".join(str(v) for v in value)
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0] + " ..."
    return text


def parse_label(payload: dict, generic_name: str) -> DrugInfo:
    """Turn the openFDA JSON into a DrugInfo object."""
    results = payload.get("results") if isinstance(payload, dict) else None
    if not results or not isinstance(results, list) or not isinstance(results[0], dict):
        raise ApiNoResultsError(f"No drug label was found for '{generic_name}'.")
    label = results[0]
    openfda = label.get("openfda", {}) if isinstance(label.get("openfda"), dict) else {}
    info = DrugInfo(
        generic_name=generic_name,
        brand_names=[str(b) for b in openfda.get("brand_name", [])],
        purpose=_clean(label.get("purpose")),
        indications=_clean(label.get("indications_and_usage")),
        warnings=_clean(label.get("warnings") or label.get("warnings_and_cautions")),
        dosage=_clean(label.get("dosage_and_administration")),
    )
    if not (info.purpose or info.indications or info.warnings or info.dosage):
        raise ApiResponseError("The drug label was found but it has no readable text.")
    return info


class DrugInfoClient:
    """Small wrapper around requests so the rest of the app never sees HTTP."""

    def __init__(self, session=None, url=config.OPENFDA_URL,
                 timeout=config.API_TIMEOUT_SECONDS):
        self.session = session or requests.Session()
        self.url = url
        self.timeout = timeout

    def fetch(self, generic_name: str) -> DrugInfo:
        name = (generic_name or "").strip()
        if not name:
            raise ApiNoResultsError("Enter a generic name before searching.")
        params = {"search": f'openfda.generic_name:"{name}"', "limit": 1}
        try:
            response = self.session.get(self.url, params=params, timeout=self.timeout)
        except requests.exceptions.Timeout as exc:
            raise ApiTimeoutError(
                "The drug information service took too long to respond. "
                "Please try again.") from exc
        except requests.exceptions.ConnectionError as exc:
            raise ApiConnectionError(
                "Could not connect to the drug information service. "
                "Please check your internet connection.") from exc
        except requests.exceptions.RequestException as exc:
            raise ApiError(f"The request could not be completed: {exc}") from exc

        status = response.status_code
        if status == 404:
            raise ApiNoResultsError(
                f"No drug label was found for '{name}'. openFDA uses U.S. generic "
                "names (for example, 'acetaminophen' instead of 'paracetamol').")
        if status == 429:
            raise ApiRateLimitError(
                "Too many requests were sent to the service. "
                "Please wait a moment and try again.")
        if status >= 400:
            raise ApiHTTPError(f"The service returned an error (HTTP {status}).")

        try:
            payload = response.json()
        except ValueError as exc:
            raise ApiResponseError("The service sent a response that could not "
                                   "be read.") from exc
        return parse_label(payload, name)
