"""Core runtime entrypoints for executing VertexForge DSL workflows."""

from vertexforge.runtime.executor import ExecutionResult, execute_config, execute_file

__all__ = ["ExecutionResult", "execute_config", "execute_file"]

