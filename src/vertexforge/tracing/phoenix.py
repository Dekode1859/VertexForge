"""Phoenix tracing setup for core runtime execution."""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv


def setup_phoenix_tracing(
    endpoint: str | None = None,
    project_name: str | None = None,
) -> Any | None:
    """Register Phoenix/OpenInference tracing for LangChain/LangGraph calls."""
    load_dotenv()

    phoenix_endpoint = endpoint or os.getenv("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006")
    if not phoenix_endpoint:
        return None

    try:
        from openinference.instrumentation.langchain import LangChainInstrumentor
        from phoenix.otel import register

        tracer_provider = register(
            endpoint=f"{phoenix_endpoint}/v1/traces",
            project_name=project_name or os.getenv("PHOENIX_PROJECT_NAME", "vertexforge"),
        )
        LangChainInstrumentor().instrument(tracer_provider=tracer_provider)
        print(f"[OK] Phoenix tracing enabled: {phoenix_endpoint}")
        return tracer_provider
    except Exception as exc:
        print(f"[WARN] Phoenix tracing not enabled: {exc}")
        return None

