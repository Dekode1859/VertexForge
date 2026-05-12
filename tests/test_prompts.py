from phoenix.client.types import PromptVersion

from vertexforge.prompts import PromptRef, StaticPromptProvider, _extract_system_prompt_text


def test_static_prompt_provider_resolves_prompt_ref_identifier() -> None:
    provider = StaticPromptProvider({"vertexforge.test": "System instructions"})

    prompt = provider.get_system_prompt(PromptRef(identifier="vertexforge.test", tag="development"))

    assert prompt == "System instructions"


def test_extract_system_prompt_text_from_phoenix_prompt_version() -> None:
    prompt = PromptVersion(
        [
            {"role": "system", "content": "System instructions"},
            {"role": "user", "content": "User template"},
        ],
        model_name="gpt-4o-mini",
    )

    assert _extract_system_prompt_text(prompt) == "System instructions"


def test_extract_system_prompt_text_falls_back_to_first_message() -> None:
    prompt = PromptVersion(
        [{"role": "user", "content": "Only user template"}],
        model_name="gpt-4o-mini",
    )

    assert _extract_system_prompt_text(prompt) == "Only user template"

