# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""BigQuery vector-search tool for searching historical bug reports."""

from __future__ import annotations

import logging
import os

from google import genai
from google.cloud import bigquery

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-004")
BQ_DATASET = os.getenv("BQ_DATASET", "code_assist_bugs")
BQ_TABLE = os.getenv("BQ_TABLE", "known_bugs")


def find_similar_bugs(query: str) -> str:
    """Searches historical production bug reports and resolutions in BigQuery.

    Embeds the natural-language query using Vertex AI text-embedding-004 and
    performs a BigQuery VECTOR_SEARCH over code_assist_bugs.known_bugs to find
    the top 3 most similar historical bugs and their resolutions.

    Args:
        query: The error message, stack trace, or bug description to search for.

    Returns:
        A formatted summary of the top 3 matching bug reports (including
        bug_id, title, description, resolution, and cosine distance),
        "No similar bugs found." if no rows match, or an unavailable message
        if BigQuery or the embedding API fails.
    """
    if not query or not query.strip():
        return "No similar bugs found."

    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    embedding_location = os.getenv("EMBEDDING_LOCATION", "us-central1")

    try:
        genai_client = genai.Client(
            vertexai=True,
            project=project_id,
            location=embedding_location,
        )
        embed_response = genai_client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=query,
        )
        if not embed_response.embeddings or not embed_response.embeddings[0].values:
            return "Bug search service is currently unavailable: failed to generate query embedding."
        embedding_values = list(embed_response.embeddings[0].values)
    except Exception as exc:
        logger.exception("Failed to generate embedding for bug search query.")
        return f"Bug search service is currently unavailable (embedding error: {exc})."

    try:
        bq_client = bigquery.Client(project=project_id)
        resolved_project = project_id or bq_client.project
        table_ref = f"`{resolved_project}.{BQ_DATASET}.{BQ_TABLE}`"

        sql = f"""
        SELECT
          base.bug_id AS bug_id,
          base.title AS title,
          base.description AS description,
          base.resolution AS resolution,
          distance
        FROM VECTOR_SEARCH(
          TABLE {table_ref},
          'description_embedding',
          (SELECT @query_embedding AS embedding),
          query_column_to_search => 'embedding',
          distance_type => 'COSINE',
          top_k => 3
        )
        ORDER BY distance ASC
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ArrayQueryParameter(
                    "query_embedding", "FLOAT64", embedding_values
                )
            ]
        )
        rows = list(bq_client.query(sql, job_config=job_config).result())
    except Exception as exc:
        logger.exception("BigQuery VECTOR_SEARCH query failed.")
        return f"Bug search service is currently unavailable (BigQuery error: {exc})."

    if not rows:
        return "No similar bugs found."

    formatted_results: list[str] = []
    for idx, row in enumerate(rows, start=1):
        bug_id = getattr(row, "bug_id", None) or row.get("bug_id", "Unknown")
        title = getattr(row, "title", None) or row.get("title", "Untitled")
        description = getattr(row, "description", None) or row.get("description", "")
        resolution = getattr(row, "resolution", None) or row.get("resolution", "")
        distance = getattr(row, "distance", None)
        if distance is None and hasattr(row, "get"):
            distance = row.get("distance")
        distance_str = f"{float(distance):.4f}" if distance is not None else "N/A"

        formatted_results.append(
            f"{idx}. [{bug_id}] {title} (cosine distance: {distance_str})\n"
            f"   Description: {description}\n"
            f"   Resolution: {resolution}"
        )

    return "\n\n".join(formatted_results)
