"""openFDA client: success and every failure scenario (mocked HTTP session)."""
import pytest
import requests

from botika.api_client import (ApiConnectionError, ApiHTTPError, ApiNoResultsError,
                               ApiRateLimitError, ApiResponseError, ApiTimeoutError,
                               DrugInfoClient)

SAMPLE = {"results": [{
    "openfda": {"brand_name": ["ADVIL"], "generic_name": ["IBUPROFEN"]},
    "indications_and_usage": ["Temporarily relieves minor aches\n and pains."],
    "warnings": ["Allergy alert: do not use if you have ever had an allergic reaction."],
    "dosage_and_administration": ["Adults: 1 tablet every 4 to 6 hours."],
}]}


class FakeResponse:
    def __init__(self, status=200, payload=None, bad_json=False):
        self.status_code, self._payload, self._bad = status, payload, bad_json

    def json(self):
        if self._bad:
            raise ValueError("not json")
        return self._payload


class FakeSession:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.calls = response, error, []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params, timeout))
        if self.error:
            raise self.error
        return self.response


def client(**kw):
    return DrugInfoClient(session=FakeSession(**kw))


def test_success_parses_json():
    c = client(response=FakeResponse(200, SAMPLE))
    info = c.fetch("ibuprofen")
    assert info.brand_names == ["ADVIL"]
    assert "aches and pains" in info.indications      # whitespace cleaned
    assert "WARNINGS" in info.to_text() and "not medical advice" in info.to_text()
    url, params, timeout = c.session.calls[0]
    assert params["search"] == 'openfda.generic_name:"ibuprofen"' and timeout == 10


def test_404_means_no_results():
    with pytest.raises(ApiNoResultsError):
        client(response=FakeResponse(404, {"error": {"code": "NOT_FOUND"}})).fetch("paracetamol")


def test_empty_results_list():
    with pytest.raises(ApiNoResultsError):
        client(response=FakeResponse(200, {"results": []})).fetch("x")


def test_rate_limit():
    with pytest.raises(ApiRateLimitError):
        client(response=FakeResponse(429, {})).fetch("x")


def test_server_error():
    with pytest.raises(ApiHTTPError) as err:
        client(response=FakeResponse(500, {})).fetch("x")
    assert "500" in str(err.value)


def test_timeout():
    with pytest.raises(ApiTimeoutError):
        client(error=requests.exceptions.Timeout()).fetch("x")


def test_connect_timeout_counts_as_timeout():
    with pytest.raises(ApiTimeoutError):
        client(error=requests.exceptions.ConnectTimeout()).fetch("x")


def test_no_internet():
    with pytest.raises(ApiConnectionError):
        client(error=requests.exceptions.ConnectionError()).fetch("x")


def test_invalid_json():
    with pytest.raises(ApiResponseError):
        client(response=FakeResponse(200, bad_json=True)).fetch("x")


def test_label_without_text():
    with pytest.raises(ApiResponseError):
        client(response=FakeResponse(200, {"results": [{"openfda": {}}]})).fetch("x")


def test_blank_name_does_not_call_api():
    c = client(response=FakeResponse(200, SAMPLE))
    with pytest.raises(ApiNoResultsError):
        c.fetch("   ")
    assert c.session.calls == []
