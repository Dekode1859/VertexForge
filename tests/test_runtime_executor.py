from pathlib import Path

import vertexforge.compiler as compiler
from langchain_core.messages import AIMessage

from vertexforge.prompts import StaticPromptProvider
from vertexforge.runtime import execute_file


class FakeLLM:
    def invoke(self, messages):
        user_text = messages[-1].content
        return AIMessage(content=f"processed::{user_text}")


AWS_DECISION_PROMPTS = StaticPromptProvider(
    {
        "pros_advisor": "Create five bullets for when to use the service.",
        "cons_advisor": "Create five bullets for when not to use the service.",
        "decision_critic": (
            "Critique contradictions and synthesize when and when not to use the service."
        ),
    }
)


def test_execute_file_runs_state_backed_json_without_web_app(monkeypatch) -> None:
    monkeypatch.setattr(compiler, "_create_llm", lambda *args, **kwargs: FakeLLM())

    result = execute_file(
        Path("examples/state_rewrite_pipeline.json"),
        "A product team is moving from UI-first development to a DSL-first runtime.",
        prompt_provider=StaticPromptProvider(
            {
                "vertexforge.brief_writer": "Write a brief.",
                "vertexforge.newsletter_writer": "Write a newsletter intro.",
                "vertexforge.executive_summarizer": "Write an executive summary.",
            }
        ),
    )

    assert result.graph_name == "state_rewrite_pipeline"
    assert result.nodes_executed == 3
    assert result.final_output_key == "executive_summary"
    assert result.final_state["source_text"].startswith("A product team")
    assert result.final_state["brief"].startswith("processed::")
    assert result.final_state["newsletter_intro"].startswith("processed::")
    assert result.final_output.startswith("processed::")


def test_execute_file_runs_structured_two_input_decision_pipeline(monkeypatch) -> None:
    monkeypatch.setattr(compiler, "_create_llm", lambda *args, **kwargs: FakeLLM())

    result = execute_file(
        Path("examples/aws_service_decision_pipeline.json"),
        {
            "pros_text": "AWS Lambda scales automatically and reduces server operations.",
            "cons_text": "AWS Lambda can have cold starts and limited execution duration.",
        },
        prompt_provider=AWS_DECISION_PROMPTS,
    )

    assert result.graph_name == "aws_service_decision_pipeline"
    assert result.nodes_executed == 3
    assert result.final_output_key == "decision_guidance"
    assert result.final_state["when_to_use"].startswith("processed::AWS Lambda scales")
    assert result.final_state["when_not_to_use"].startswith("processed::AWS Lambda can")
    assert "[when_to_use]" in result.final_output
    assert "[when_not_to_use]" in result.final_output

