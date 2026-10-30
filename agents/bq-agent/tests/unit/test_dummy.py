# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Unit tests for bq-agent."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.agent import root_agent
from app.tools import find_similar_bugs


def test_root_agent_config() -> None:
    """Verify root_agent configuration and registered tools."""
    assert root_agent.name == "bq_agent"
    assert find_similar_bugs in root_agent.tools


@patch("app.tools.bigquery.Client")
@patch("app.tools.genai.Client")
def test_find_similar_bugs_success(
    mock_genai_client_cls: MagicMock, mock_bq_client_cls: MagicMock
) -> None:
    """Verify find_similar_bugs formats matching bug rows."""
    mock_genai = mock_genai_client_cls.return_value
    mock_genai.models.embed_content.return_value = SimpleNamespace(
        embeddings=[SimpleNamespace(values=[0.1, 0.2, 0.3])]
    )

    fake_row = SimpleNamespace(
        bug_id="BUG-1051",
        title="Memory leak: unbounded in-memory cache grows until OOM",
        description="Memory climbs steadily over hours until the container is OOMKilled.",
        resolution="Bound the cache (LRU with a max size and TTL).",
        distance=0.3913,
    )
    mock_bq = mock_bq_client_cls.return_value
    mock_bq.project = "test-project"
    mock_bq.query.return_value.result.return_value = [fake_row]

    output = find_similar_bugs("memory leak in background worker")

    assert "BUG-1051" in output
    assert "Memory leak: unbounded in-memory cache grows until OOM" in output
    assert "0.3913" in output
    assert "Bound the cache" in output


@patch("app.tools.bigquery.Client")
@patch("app.tools.genai.Client")
def test_find_similar_bugs_empty(
    mock_genai_client_cls: MagicMock, mock_bq_client_cls: MagicMock
) -> None:
    """Verify find_similar_bugs returns 'No similar bugs found.' when query returns no rows."""
    mock_genai = mock_genai_client_cls.return_value
    mock_genai.models.embed_content.return_value = SimpleNamespace(
        embeddings=[SimpleNamespace(values=[0.1, 0.2, 0.3])]
    )

    mock_bq = mock_bq_client_cls.return_value
    mock_bq.project = "test-project"
    mock_bq.query.return_value.result.return_value = []

    assert find_similar_bugs("nonexistent bug") == "No similar bugs found."
    assert find_similar_bugs("   ") == "No similar bugs found."


@patch("app.tools.bigquery.Client")
@patch("app.tools.genai.Client")
def test_find_similar_bugs_error_handling(
    mock_genai_client_cls: MagicMock, mock_bq_client_cls: MagicMock
) -> None:
    """Verify find_similar_bugs catches exceptions and returns an unavailable message."""
    mock_genai = mock_genai_client_cls.return_value
    mock_genai.models.embed_content.side_effect = RuntimeError("API quota exceeded")

    output = find_similar_bugs("test query")
    assert "unavailable" in output.lower()
