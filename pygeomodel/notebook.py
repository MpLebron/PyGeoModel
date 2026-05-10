"""Jupyter widget interfaces built on top of the core API."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class NotebookInterface:
    def __init__(self, modeler):
        self.modeler = modeler
        self.widgets: dict[str, Any] = {}

    def show_models(self):
        import ipywidgets as widgets

        search_box = widgets.Text(placeholder="Search model services", description="Search:")
        result_box = widgets.VBox()

        def render(query: str = ""):
            summaries = self.modeler.search_models(query, limit=20)
            buttons = []
            for summary in summaries:
                button = widgets.Button(description=summary.name, layout=widgets.Layout(width="100%"))
                button.on_click(lambda _, name=summary.name: self._render_model_detail(name, result_box))
                buttons.append(button)
            result_box.children = tuple(buttons) or (widgets.HTML("<em>No models found.</em>"),)

        search_box.observe(lambda change: render(change["new"]), names="value")
        render("")
        return widgets.VBox([search_box, result_box])

    def invoke_model(self, model_name: str):
        import ipywidgets as widgets

        model = self.modeler.get_model(model_name)
        form_items = []
        self.widgets = {}
        header = widgets.HTML(f"<h3>{model.name}</h3><p>{model.description}</p>")
        form_items.append(header)
        for item in model.inputs:
            widget = widgets.Text(description=item.name, placeholder=item.description[:80])
            self.widgets[item.name] = widget
            form_items.append(widget)
        output = widgets.Output()
        run_button = widgets.Button(description="Run", button_style="success")
        export_button = widgets.Button(description="Export params")

        def on_run(_):
            params = self.collect_params()
            with output:
                output.clear_output()
                try:
                    result = self.modeler.invoke(model_name, params=params)
                    print(f"Status: {result.status}")
                    for model_output in result.outputs:
                        print(model_output)
                except Exception as exc:
                    print(f"Model run failed: {exc}")

        def on_export(_):
            with output:
                output.clear_output()
                print(self.collect_params())

        run_button.on_click(on_run)
        export_button.on_click(on_export)
        form_items.extend([widgets.HBox([run_button, export_button]), output])
        return widgets.VBox(form_items)

    def collect_params(self) -> dict[str, Any]:
        return {key: widget.value for key, widget in self.widgets.items() if getattr(widget, "value", "") != ""}

    def export_params(self, path: str | Path) -> str:
        import json

        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(self.collect_params(), ensure_ascii=False, indent=2), encoding="utf-8")
        return str(output_path)

    def _render_model_detail(self, model_name: str, result_box):
        import ipywidgets as widgets

        model = self.modeler.get_model(model_name)
        html = f"<h3>{model.name}</h3><p>{model.description}</p><p>Inputs: {len(model.inputs)}; Outputs: {len(model.outputs)}</p>"
        invoke_button = widgets.Button(description="Open invocation form", button_style="info")
        invoke_button.on_click(lambda _: setattr(result_box, "children", (self.invoke_model(model_name),)))
        result_box.children = (widgets.HTML(html), invoke_button)
