"""Run a VertexForge JSON workflow without the FastAPI app."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vertexforge.tracing import setup_phoenix_tracing


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Execute a VertexForge DSL JSON pipeline.")
    parser.add_argument("config", type=Path, help="Path to a VertexForge JSON workflow file.")
    parser.add_argument("--input", help="User input to store in the workflow input key.")
    parser.add_argument(
        "--input-json",
        help="Structured initial inputs as a JSON object string.",
    )
    parser.add_argument(
        "--input-json-file",
        type=Path,
        help="Path to a JSON object file containing structured initial inputs.",
    )
    parser.add_argument(
        "--state",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Structured initial input field. Repeat for multiple fields.",
    )
    parser.add_argument(
        "--phoenix-endpoint",
        default=None,
        help="Phoenix collector endpoint. Defaults to PHOENIX_COLLECTOR_ENDPOINT or http://localhost:6006.",
    )
    parser.add_argument(
        "--no-tracing",
        action="store_true",
        help="Disable Phoenix tracing for this run.",
    )
    parser.add_argument(
        "--show-state",
        action="store_true",
        help="Print the full final state after printing the final output.",
    )
    return parser.parse_args()


def load_user_input(args: argparse.Namespace) -> str | dict:
    """Resolve CLI input into either a text string or structured state inputs."""
    provided = [
        args.input is not None,
        args.input_json is not None,
        args.input_json_file is not None,
        bool(args.state),
    ]
    if sum(provided) != 1:
        raise SystemExit("Provide exactly one of --input, --input-json, --input-json-file, or --state.")

    if args.input is not None:
        return args.input

    if args.state:
        parsed_state = {}
        for item in args.state:
            if "=" not in item:
                raise SystemExit(f"Invalid --state value '{item}'. Expected KEY=VALUE.")
            key, value = item.split("=", 1)
            if not key:
                raise SystemExit(f"Invalid --state value '{item}'. KEY cannot be empty.")
            parsed_state[key] = value
        return parsed_state

    raw_json = (
        args.input_json_file.read_text(encoding="utf-8")
        if args.input_json_file is not None
        else args.input_json
    )
    parsed = json.loads(raw_json)
    if not isinstance(parsed, dict):
        raise SystemExit("Structured input must be a JSON object.")
    return parsed


def main() -> int:
    args = parse_args()
    if not args.no_tracing:
        setup_phoenix_tracing(endpoint=args.phoenix_endpoint)

    from vertexforge.runtime import execute_file

    result = execute_file(args.config, load_user_input(args))

    print(f"Graph: {result.graph_name}")
    print(f"Nodes executed: {result.nodes_executed}")
    if result.final_output_key:
        print(f"Final output key: {result.final_output_key}")
    print("\nFinal output:")
    print(result.final_output)

    if args.show_state:
        print("\nFinal state:")
        print(json.dumps(result.final_state, indent=2, default=str))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

