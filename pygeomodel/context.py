"""Notebook and workspace context collection."""

from __future__ import annotations

import os
from pathlib import Path


class NotebookContext:
    """Collect lightweight context from notebooks and nearby data files."""

    def __init__(self, root: str | Path | None = None):
        self.root = Path(root or os.getcwd())
        self.data_context = self._get_data_context()
        self.history_context = self._get_modeling_history_context()

    def to_dict(self) -> dict[str, str]:
        return {
            "data_context": self.data_context,
            "modeling_history": self.history_context,
        }

    def _get_data_context(self) -> str:
        excluded_dirs = {".git", "__pycache__", ".ipynb_checkpoints", "node_modules"}
        excluded_ext = {".py", ".pyc", ".pyo", ".txt", ".md", ".c", ".so", ".pyd"}
        lines: list[str] = []
        for root, dirs, files in os.walk(self.root):
            dirs[:] = [d for d in dirs if d not in excluded_dirs]
            for filename in files:
                path = Path(root) / filename
                if path.name.startswith(".") or path.suffix in excluded_ext:
                    continue
                rel = path.relative_to(self.root)
                lines.append(f"- A {path.suffix.lstrip('.') or 'file'} file named '{path.name}' located at '{rel}'")
        if not lines:
            return "No relevant data files found in the current working directory."
        return "The following data files are available in the current working directory:\n" + "\n".join(lines)

    def _get_modeling_history_context(self) -> str:
        parts: list[str] = []
        try:
            import nbformat

            notebooks = sorted(self.root.rglob("*.ipynb"), key=lambda p: p.stat().st_mtime, reverse=True)
            for notebook_path in notebooks[:1]:
                if notebook_path.name.endswith("-checkpoint.ipynb"):
                    continue
                notebook = nbformat.read(notebook_path, as_version=4)
                for cell in notebook.cells:
                    if cell.source.strip():
                        parts.append(f"{cell.cell_type.title()} Cell:\n{cell.source}")
        except Exception:
            pass
        try:
            from IPython import get_ipython

            ip = get_ipython()
            if ip is not None:
                for _, line_number, code in ip.history_manager.get_range(output=False):
                    if code.strip():
                        parts.append(f"In [{line_number}]: {code}")
        except Exception:
            pass
        return "\n\n".join(parts) if parts else "No notebook modeling history was detected."
