from argparse import Namespace

from scripts.run_pipeline import load_user_input


def test_load_user_input_accepts_repeated_state_fields() -> None:
    args = Namespace(
        input=None,
        input_json=None,
        input_json_file=None,
        state=["pros_text=Fast scaling", "cons_text=Cold starts"],
    )

    assert load_user_input(args) == {
        "pros_text": "Fast scaling",
        "cons_text": "Cold starts",
    }

