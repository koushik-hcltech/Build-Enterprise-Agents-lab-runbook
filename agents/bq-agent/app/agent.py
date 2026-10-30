# ruff: noqa
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

import os

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types

from app.tools import find_similar_bugs

load_dotenv()

os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "True")

MODEL = os.getenv("MODEL", "gemini-3.5-flash")

root_agent = Agent(
    # Keep in sync with create_params.root_agent_name in agents-cli-manifest.yaml:
    # telemetry reports this name as gen_ai.agent.name, and agents-cli reports the
    # manifest's value. Renaming the agent only here makes the two disagree, and
    # anything selecting traces by name stops finding this agent's.
    name="bq_agent",
    model=Gemini(
        model=MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    description=(
        "Searches historical production bug reports and resolutions stored in "
        "BigQuery using vector similarity search to help diagnose production issues."
    ),
    instruction=(
        "You are a specialist bug-database research agent for Code Assist.\n"
        "When given an error message, stack trace, or bug description, always use "
        "the `find_similar_bugs` tool to search the historical bug database in "
        "BigQuery (`code_assist_bugs.known_bugs`).\n"
        "Summarize the matching historical bug reports clearly, including their "
        "`bug_id`, `title`, `description`, `resolution`, and cosine `distance`, "
        "and explain how the historical resolutions apply to the current issue."
    ),
    tools=[find_similar_bugs],
)

app = App(
    root_agent=root_agent,
    name="app",
)
