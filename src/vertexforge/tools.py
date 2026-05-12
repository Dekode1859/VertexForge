"""
Real Tool Definitions for LangGraph Agents
These are actual functional tools, not stubs.
"""

import json
import os
import re
from datetime import datetime
from typing import Annotated, List, Optional
from pathlib import Path

import requests

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from vertexforge.ingestion.repository import ArtifactRepository


# ============================================================================
# SEARCH TOOLS
# ============================================================================

@tool
def web_search(
    query: Annotated[str, "The search query to execute"],
    max_results: Annotated[int, "Maximum number of results to return (default 5)"] = 5
) -> str:
    """Search the web using Ollama's web search API and return results as formatted text."""
    try:
        api_key = os.getenv("OLLAMA_API_KEY")
        if not api_key:
            return "Error: OLLAMA_API_KEY environment variable not set"
        
        response = requests.post(
            "https://ollama.com/api/web_search",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"query": query, "max_results": min(max_results, 10)},
            timeout=30
        )
        
        if response.status_code != 200:
            return f"Search error: HTTP {response.status_code} - {response.text}"
        
        data = response.json()
        results = data.get("results", [])
        
        if not results:
            return "No results found for the query."
        
        formatted = []
        for i, result in enumerate(results, 1):
            formatted.append(
                f"{i}. {result.get('title', 'Untitled')}\n"
                f"   URL: {result.get('url', 'N/A')}\n"
                f"   Snippet: {result.get('content', 'No content')[:200]}..."
            )
        
        return "\n\n".join(formatted)
    
    except Exception as e:
        return f"Search error: {str(e)}"


@tool
def get_current_date() -> str:
    """Get the current date and time."""
    now = datetime.now()
    return f"Current date and time: {now.strftime('%Y-%m-%d %H:%M:%S')} (Local time)"


# ============================================================================
# CALCULATION TOOLS
# ============================================================================

@tool
def calculate(
    expression: Annotated[str, "Mathematical expression to evaluate (e.g., '2 + 2 * 3')"]
) -> str:
    """Evaluate a mathematical expression safely."""
    try:
        # Security: Only allow safe characters
        allowed = re.compile(r'^[\d\+\-\*\/\.\(\)\s\%\^]+$')
        if not allowed.match(expression):
            return "Error: Invalid characters in expression. Only numbers and + - * / ( ) % ^ allowed."
        
        # Replace ^ with ** for exponentiation
        safe_expr = expression.replace('^', '**')
        
        # Evaluate in restricted environment
        result = eval(safe_expr, {"__builtins__": {}}, {})
        return f"Result: {result}"
    
    except Exception as e:
        return f"Error calculating: {str(e)}"


@tool
def calculate_statistics(
    numbers: Annotated[str, "Comma-separated list of numbers (e.g., '1, 2, 3, 4, 5')"]
) -> str:
    """Calculate mean, median, min, max of a number list."""
    try:
        nums = [float(n.strip()) for n in numbers.split(",")]
        nums_sorted = sorted(nums)
        
        mean = sum(nums) / len(nums)
        median = nums_sorted[len(nums) // 2] if len(nums) % 2 else (nums_sorted[len(nums)//2 - 1] + nums_sorted[len(nums)//2]) / 2
        
        return (
            f"Count: {len(nums)}\n"
            f"Mean: {mean:.4f}\n"
            f"Median: {median:.4f}\n"
            f"Min: {min(nums)}\n"
            f"Max: {max(nums)}\n"
            f"Sum: {sum(nums)}"
        )
    
    except Exception as e:
        return f"Error: {str(e)}"


# ============================================================================
# FILE SYSTEM TOOLS
# ============================================================================

@tool
def read_file(
    path: Annotated[str, "Path to the file to read"],
    limit: Annotated[int, "Maximum lines to read (default 100)"] = 100
) -> str:
    """Read the contents of a file."""
    try:
        file_path = Path(path).resolve()
        
        # Security: Prevent directory traversal
        cwd = Path.cwd()
        if not str(file_path).startswith(str(cwd)):
            return "Error: Can only read files within the project directory."
        
        if not file_path.exists():
            return f"Error: File not found: {path}"
        
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()[:limit]
            content = ''.join(lines)
        
        total_lines = sum(1 for _ in open(file_path, 'r', encoding='utf-8'))
        
        return f"File: {path}\nLines: {len(lines)} of {total_lines}\n\n{content}"
    
    except Exception as e:
        return f"Error reading file: {str(e)}"


@tool
def list_directory(
    path: Annotated[str, "Directory path (default: current directory)"] = "."
) -> str:
    """List files and directories at the specified path."""
    try:
        dir_path = Path(path).resolve()
        
        # Security: Prevent directory traversal
        cwd = Path.cwd()
        if not str(dir_path).startswith(str(cwd)):
            return "Error: Can only list directories within the project."
        
        if not dir_path.exists():
            return f"Error: Directory not found: {path}"
        
        items = []
        for item in sorted(dir_path.iterdir()):
            item_type = "ðŸ“" if item.is_dir() else "ðŸ“„"
            size = item.stat().st_size if item.is_file() else "-"
            items.append(f"{item_type} {item.name:<40} {size}")
        
        return f"Directory: {path}\n\n" + "\n".join(items)
    
    except Exception as e:
        return f"Error listing directory: {str(e)}"


@tool
def write_file(
    path: Annotated[str, "Path to write to"],
    content: Annotated[str, "Content to write"],
    append: Annotated[bool, "Append instead of overwrite (default False)"] = False
) -> str:
    """Write content to a file."""
    try:
        file_path = Path(path).resolve()
        
        # Security: Prevent directory traversal
        cwd = Path.cwd()
        if not str(file_path).startswith(str(cwd)):
            return "Error: Can only write files within the project directory."
        
        mode = 'a' if append else 'w'
        with open(file_path, mode, encoding='utf-8') as f:
            f.write(content)
        
        action = "Appended to" if append else "Wrote"
        return f"{action} file: {path}"
    
    except Exception as e:
        return f"Error writing file: {str(e)}"


# ============================================================================
# TEXT PROCESSING TOOLS
# ============================================================================

@tool
def count_words(text: Annotated[str, "Text to count words in"]) -> str:
    """Count words, characters, and lines in text."""
    words = len(text.split())
    chars = len(text)
    chars_no_spaces = len(text.replace(' ', ''))
    lines = len(text.split('\n'))
    
    return (
        f"Word count: {words}\n"
        f"Character count: {chars}\n"
        f"Characters (no spaces): {chars_no_spaces}\n"
        f"Line count: {lines}"
    )


@tool
def extract_urls(text: Annotated[str, "Text to extract URLs from"]) -> str:
    """Extract all URLs from the given text."""
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    urls = re.findall(url_pattern, text)
    
    if not urls:
        return "No URLs found."
    
    return "Found URLs:\n" + "\n".join(f"  - {url}" for url in urls)


# ============================================================================
# SOURCE ACCESS TOOLS
# ============================================================================

SOURCE_TOOL_NAMES = [
    "list_sources",
    "get_source_metadata",
    "list_source_artifacts",
    "read_text_artifact",
    "read_table_artifact",
    "search_artifacts",
]


def create_source_tools(
    repository: ArtifactRepository,
    allowed_source_ids: List[str],
    allowed_artifact_types: Optional[List[str]] = None,
):
    """Create source-aware tools scoped to the allowed sources for a node."""
    allowed_source_set = set(allowed_source_ids)
    allowed_artifact_set = set(allowed_artifact_types or [])

    def source_is_allowed(source_id: str) -> bool:
        return source_id in allowed_source_set

    def artifact_is_allowed(artifact_type: str) -> bool:
        return not allowed_artifact_set or artifact_type in allowed_artifact_set

    def get_accessible_artifact(artifact_id: str):
        for source_id in allowed_source_set:
            for artifact in repository.list_artifacts(source_id):
                if artifact.artifact_id == artifact_id and artifact_is_allowed(artifact.artifact_type):
                    return artifact
        return None

    @tool("list_sources")
    def list_sources_tool() -> str:
        """List uploaded sources accessible to this node."""
        sources = [source for source in repository.list_sources() if source_is_allowed(source.source_id)]
        if not sources:
            return "No accessible sources are attached to this node."
        lines = [
            f"- {source.source_id}: {source.filename} ({source.detected_type}, {source.size_bytes} bytes)"
            for source in sources
        ]
        return "Accessible sources:\n" + "\n".join(lines)

    @tool("get_source_metadata")
    def get_source_metadata_tool(
        source_id: Annotated[str, "The source ID to inspect"]
    ) -> str:
        """Get metadata for an attached source."""
        if not source_is_allowed(source_id):
            return f"Source '{source_id}' is not accessible to this node."
        source = repository.get_source(source_id)
        if source is None:
            return f"Source '{source_id}' was not found."
        return json.dumps(source.model_dump(), indent=2)

    @tool("list_source_artifacts")
    def list_source_artifacts_tool(
        source_id: Annotated[str, "The source ID whose artifacts should be listed"]
    ) -> str:
        """List accessible artifacts for an attached source."""
        if not source_is_allowed(source_id):
            return f"Source '{source_id}' is not accessible to this node."
        artifacts = [
            artifact
            for artifact in repository.list_artifacts(source_id)
            if artifact_is_allowed(artifact.artifact_type)
        ]
        if not artifacts:
            return "No accessible artifacts found for this source."
        lines = [
            f"- {artifact.artifact_id}: {artifact.artifact_type} ({artifact.subtype})"
            for artifact in artifacts
        ]
        return "Accessible artifacts:\n" + "\n".join(lines)

    @tool("read_text_artifact")
    def read_text_artifact_tool(
        artifact_id: Annotated[str, "The text-bearing artifact ID to read"]
    ) -> str:
        """Read the text content of an accessible text or page artifact."""
        artifact = get_accessible_artifact(artifact_id)
        if artifact is None:
            return f"Artifact '{artifact_id}' is not accessible to this node."
        if artifact.artifact_type not in {"text_block", "page"}:
            return f"Artifact '{artifact_id}' does not contain readable text."
        text = artifact.payload.get("text", "")
        return text if text else f"Artifact '{artifact_id}' contains no extracted text."

    @tool("read_table_artifact")
    def read_table_artifact_tool(
        artifact_id: Annotated[str, "The table artifact ID to read"]
    ) -> str:
        """Read a structured table artifact from an attached source."""
        artifact = get_accessible_artifact(artifact_id)
        if artifact is None:
            return f"Artifact '{artifact_id}' is not accessible to this node."
        if artifact.artifact_type != "table":
            return f"Artifact '{artifact_id}' is not a table artifact."
        return json.dumps(artifact.payload, indent=2)

    @tool("search_artifacts")
    def search_artifacts_tool(
        query: Annotated[str, "Text to search for across accessible artifacts"]
    ) -> str:
        """Search accessible artifacts for a text match."""
        needle = query.lower()
        matches = []
        for source_id in allowed_source_set:
            source = repository.get_source(source_id)
            for artifact in repository.list_artifacts(source_id):
                if not artifact_is_allowed(artifact.artifact_type):
                    continue
                haystacks = [artifact.preview_text or "", json.dumps(artifact.payload)]
                matched_text = next(
                    (haystack for haystack in haystacks if needle in haystack.lower()),
                    None,
                )
                if matched_text is not None:
                    lowered = matched_text.lower()
                    start = max(lowered.find(needle) - 40, 0)
                    end = min(start + 120, len(matched_text))
                    snippet = matched_text[start:end].replace("\n", " ")
                    matches.append(
                        f"- {source.filename if source else source_id} :: {artifact.artifact_id} :: "
                        f"{artifact.artifact_type} :: {snippet}"
                    )
        if not matches:
            return f"No accessible artifacts matched '{query}'."
        return "Matching artifacts:\n" + "\n".join(matches)

    return [
        list_sources_tool,
        get_source_metadata_tool,
        list_source_artifacts_tool,
        read_text_artifact_tool,
        read_table_artifact_tool,
        search_artifacts_tool,
    ]


# ============================================================================
# TOOL COLLECTIONS FOR AGENTS
# ============================================================================

RESEARCH_TOOLS = [web_search, get_current_date, extract_urls]
MATH_TOOLS = [calculate, calculate_statistics]
FILE_TOOLS = [read_file, list_directory, write_file]
TEXT_TOOLS = [count_words]

ALL_TOOLS = RESEARCH_TOOLS + MATH_TOOLS + FILE_TOOLS + TEXT_TOOLS


if __name__ == "__main__":
    # Test tools
    print("Testing web_search...")
    print(web_search.invoke({"query": "LangGraph multi-agent patterns", "max_results": 3}))
    
    print("\nTesting calculate...")
    print(calculate.invoke({"expression": "2 + 2 * 3"}))
    
    print("\nTesting get_current_date...")
    print(get_current_date.invoke({}))

