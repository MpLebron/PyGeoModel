"""Jupyter widget interfaces built on top of the core API."""

from __future__ import annotations

import html
import io
import json
from collections import defaultdict
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any


class NotebookInterface:
    """Notebook-facing UI that preserves the original PyGeoModel visual style."""

    def __init__(self, modeler):
        self.modeler = modeler
        self.widgets: dict[str, Any] = {}
        self.browser_widgets: dict[str, Any] = {}
        self.param_widgets: dict[str, Any] = {}
        self.current_page = 1
        self.page_size = 10
        self.current_query = ""

    def show_models(self):
        """Display the searchable, paginated model browser."""
        import ipywidgets as widgets

        self.widgets = {}
        self.browser_widgets = {}
        self.current_page = 1
        self.current_query = ""

        style = self._style_widget(widgets)
        main_widget = widgets.HBox(
            layout=widgets.Layout(width="100%", align_items="stretch")
        )
        main_widget.add_class("pygeomodel-browser")

        left_panel = widgets.VBox(
            layout=widgets.Layout(
                width="320px",
                min_width="300px",
                margin="10px",
                padding="12px",
                border="1px solid #e2e8f0",
            )
        )
        left_panel.add_class("pygeomodel-side-panel")

        search_box = widgets.Text(
            placeholder="Search...",
            description="Search:",
            layout=widgets.Layout(width="100%", margin="0 0 8px 0"),
            style={"description_width": "56px"},
        )
        search_box.add_class("pygeomodel-search")

        nav_box = widgets.HBox(
            layout=widgets.Layout(
                width="100%",
                margin="6px 0 8px 0",
                justify_content="space-between",
                align_items="center",
            )
        )
        model_list = widgets.VBox(layout=widgets.Layout(width="100%"))

        right_panel = widgets.VBox(
            layout=widgets.Layout(flex="1", margin="10px", min_width="0", padding="0")
        )
        right_panel.add_class("pygeomodel-detail-panel")
        right_panel.children = (self._empty_detail(widgets),)

        self.browser_widgets["search_box"] = search_box
        self.browser_widgets["nav_box"] = nav_box
        self.browser_widgets["model_list"] = model_list
        self.browser_widgets["model_detail_area"] = right_panel
        self.widgets.update(self.browser_widgets)

        def on_search(change):
            self.current_query = change["new"]
            self.current_page = 1
            self._refresh_model_browser()

        search_box.observe(on_search, names="value")
        left_panel.children = (search_box, nav_box, model_list)
        main_widget.children = (left_panel, right_panel)
        self._refresh_model_browser()
        return widgets.VBox((style, main_widget), layout=widgets.Layout(width="100%"))

    def invoke_model(self, model_name: str):
        """Display the interactive model invocation form."""
        import ipywidgets as widgets

        model = self.modeler.get_model(model_name)
        self.widgets = {}
        self.param_widgets = {}

        style = self._style_widget(widgets)
        model_info = self._model_info_header(widgets, model, include_qa_button=True)
        qa_toggle_button = model_info.children[1]

        form_items = [model_info]
        form_items.extend(self._state_form_widgets(widgets, model))

        output = widgets.Output(
            layout=widgets.Layout(
                width="100%",
                margin="14px 0 0 0",
                padding="10px",
            )
        )
        output.add_class("pygeomodel-output")
        self.widgets["output_area"] = output

        run_button = widgets.Button(
            description="Run model",
            icon="play",
            style=widgets.ButtonStyle(button_color="#4CAF50", text_color="white", font_weight="600"),
            layout=widgets.Layout(width="140px", height="36px"),
        )
        run_button.add_class("pygeomodel-run-button")

        def set_output_html(html_value: str):
            output.outputs = (
                {
                    "output_type": "display_data",
                    "data": {"text/html": html_value},
                    "metadata": {},
                },
            )

        def on_run(_):
            original_desc = run_button.description
            original_icon = run_button.icon
            run_button.disabled = True
            run_button.description = "Running..."
            run_button.icon = "spinner"
            set_output_html(self._render_running_html(model_name))
            log_stream = io.StringIO()
            try:
                with redirect_stdout(log_stream):
                    result = self.modeler.invoke(model_name, params=self.collect_params())
                log_text = log_stream.getvalue()
                set_output_html(self._render_task_result_html(result, log_text))
            except Exception as exc:
                log_text = log_stream.getvalue()
                set_output_html(self._render_task_error_html(exc, log_text))
            finally:
                run_button.disabled = False
                run_button.description = original_desc
                run_button.icon = original_icon

        run_button.on_click(on_run)
        button_row = widgets.HBox(
            (run_button,),
            layout=widgets.Layout(justify_content="flex-end", margin="12px 0 0 0"),
        )
        button_row.add_class("pygeomodel-button-row")
        form_items.extend([button_row, output])

        main_form = widgets.VBox(form_items, layout=widgets.Layout(width="100%"))
        main_form.add_class("pygeomodel-form")

        left_panel = widgets.VBox(
            (main_form,),
            layout=widgets.Layout(width="60%", padding="10px", min_width="0"),
        )
        qa_panel = self._qa_panel(widgets, model)
        split_container = widgets.HBox(
            (left_panel, qa_panel),
            layout=widgets.Layout(width="100%", display="flex", align_items="stretch"),
        )
        split_container.add_class("pygeomodel-invoke-shell")

        qa_visible = [True]

        def toggle_qa(_):
            if qa_visible[0]:
                split_container.children = (left_panel,)
                left_panel.layout.width = "100%"
                qa_visible[0] = False
                qa_toggle_button.description = "?"
                qa_toggle_button.tooltip = "Show QA Assistant"
            else:
                split_container.children = (left_panel, qa_panel)
                left_panel.layout.width = "60%"
                qa_visible[0] = True
                qa_toggle_button.description = "?"
                qa_toggle_button.tooltip = "Hide QA Assistant"

        qa_toggle_button.on_click(toggle_qa)
        return widgets.VBox((style, split_container), layout=widgets.Layout(width="100%"))

    def collect_params(self) -> dict[str, Any]:
        params: dict[str, Any] = {}
        for key, widget in self.param_widgets.items():
            value = self._widget_value(widget)
            if value not in ("", None):
                params[key] = value
        return params

    def export_params(self, path: str | Path) -> str:
        import json

        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(self.collect_params(), ensure_ascii=False, indent=2), encoding="utf-8")
        return str(output_path)

    def _render_running_html(self, model_name: str) -> str:
        return f"""
        <div class="pygeomodel-result-card running">
            <div class="pygeomodel-result-head">
                <span class="pygeomodel-status-pill running">Running</span>
                <div>
                    <h4>Submitting model service</h4>
                    <p>{self._e(model_name)}</p>
                </div>
            </div>
        </div>
        """

    def _render_task_result_html(self, result, log_text: str) -> str:
        status = self._e(result.status or "completed")
        status_class = "success" if str(result.status).lower() == "completed" else "neutral"
        task_id = self._e(result.task_id or "Not returned")
        runtime = f"{result.execution_time:.2f} s" if result.execution_time is not None else "Not recorded"
        output_count = len(result.outputs or [])
        outputs_html = self._render_outputs_html(result.outputs or [])
        params_html = self._render_compact_json(result.params)
        raw_html = self._render_compact_json(result.outputs or [])
        safe_log = self._e(self._sanitize_text(log_text.strip()) or "No SDK log was emitted.")

        return f"""
        <div class="pygeomodel-result-card">
            <div class="pygeomodel-result-head">
                <span class="pygeomodel-status-pill {status_class}">{status}</span>
                <div>
                    <h4>Model run completed</h4>
                    <p>{output_count} output resource{'s' if output_count != 1 else ''} returned by OpenGMS</p>
                </div>
            </div>
            <div class="pygeomodel-result-grid">
                <div><b>Task ID</b><span>{task_id}</span></div>
                <div><b>Runtime</b><span>{self._e(runtime)}</span></div>
            </div>
            {outputs_html}
            <details class="pygeomodel-details">
                <summary>Execution details</summary>
                <div class="pygeomodel-detail-block">
                    <b>Input parameters</b>
                    <pre>{params_html}</pre>
                </div>
                <div class="pygeomodel-detail-block">
                    <b>Raw output metadata</b>
                    <pre>{raw_html}</pre>
                </div>
                <div class="pygeomodel-detail-block">
                    <b>SDK log</b>
                    <pre>{safe_log}</pre>
                </div>
            </details>
        </div>
        """

    def _render_task_error_html(self, exc: Exception, log_text: str) -> str:
        message = self._sanitize_text(str(exc))
        safe_log = self._e(self._sanitize_text(log_text.strip()) or "No SDK log was emitted.")
        return f"""
        <div class="pygeomodel-result-card error">
            <div class="pygeomodel-result-head">
                <span class="pygeomodel-status-pill error">Failed</span>
                <div>
                    <h4>Model run failed</h4>
                    <p>{self._e(message)}</p>
                </div>
            </div>
            <details class="pygeomodel-details">
                <summary>Execution log</summary>
                <div class="pygeomodel-detail-block">
                    <pre>{safe_log}</pre>
                </div>
            </details>
        </div>
        """

    def _render_outputs_html(self, outputs: list[dict[str, Any]]) -> str:
        if not outputs:
            return """
            <div class="pygeomodel-output-empty">
                OpenGMS reported completion, but no output metadata was returned.
            </div>
            """
        rows = []
        has_url = False
        for index, item in enumerate(outputs, start=1):
            url = item.get("url") or ""
            has_url = has_url or bool(url)
            label = self._e(item.get("tag") or item.get("event") or f"Output {index}")
            state = self._e(item.get("statename") or "")
            event = self._e(item.get("event") or "")
            suffix = self._e(item.get("suffix") or "resource")
            link = (
                f'<a class="pygeomodel-output-link" href="{self._e(url)}" target="_blank" rel="noopener noreferrer">Open output</a>'
                if url
                else '<span class="pygeomodel-output-muted">No downloadable file</span>'
            )
            rows.append(
                f"""
                <tr>
                    <td>{label}</td>
                    <td>{state}</td>
                    <td>{event}</td>
                    <td>{suffix}</td>
                    <td>{link}</td>
                </tr>
                """
            )
        notice = ""
        if not has_url:
            notice = """
            <div class="pygeomodel-output-empty">
                The task completed, but this model service did not return downloadable output files through the SDK endpoint.
            </div>
            """
        return f"""
        <div class="pygeomodel-output-section">
            <h5>Output resources</h5>
            {notice}
            <table class="pygeomodel-output-table">
                <colgroup>
                    <col class="pygeomodel-output-col-name">
                    <col class="pygeomodel-output-col-state">
                    <col class="pygeomodel-output-col-event">
                    <col class="pygeomodel-output-col-format">
                    <col class="pygeomodel-output-col-action">
                </colgroup>
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>State</th>
                        <th>Event</th>
                        <th>Format</th>
                        <th>Action</th>
                    </tr>
                </thead>
                <tbody>{''.join(rows)}</tbody>
            </table>
        </div>
        """

    def _render_params_html(self, params: dict[str, Any]) -> str:
        return f"""
        <div class="pygeomodel-result-card">
            <div class="pygeomodel-result-head">
                <span class="pygeomodel-status-pill neutral">Params</span>
                <div>
                    <h4>Collected parameters</h4>
                    <p>These values will be used for the next model invocation.</p>
                </div>
            </div>
            <pre class="pygeomodel-json-preview">{self._render_compact_json(params)}</pre>
        </div>
        """

    def _render_compact_json(self, payload: Any) -> str:
        return self._e(json.dumps(payload, ensure_ascii=False, indent=2))

    def _sanitize_text(self, value: str) -> str:
        sanitizer = getattr(self.modeler, "_sanitize_error_message", None)
        if sanitizer:
            return sanitizer(value)
        return value

    def _refresh_model_browser(self):
        import ipywidgets as widgets

        summaries = self.modeler.search_models(self.current_query, limit=len(self.modeler.model_names))
        total_models = len(summaries)
        total_pages = max(1, (total_models + self.page_size - 1) // self.page_size)
        self.current_page = min(max(1, self.current_page), total_pages)
        start_idx = (self.current_page - 1) * self.page_size
        end_idx = min(start_idx + self.page_size, total_models)

        prev_button = widgets.Button(
            description="Previous",
            disabled=self.current_page == 1,
            layout=widgets.Layout(width="86px", height="32px"),
            style=widgets.ButtonStyle(button_color="#e2e8f0", text_color="#334155"),
        )
        next_button = widgets.Button(
            description="Next",
            disabled=self.current_page == total_pages,
            layout=widgets.Layout(width="86px", height="32px"),
            style=widgets.ButtonStyle(button_color="#e2e8f0", text_color="#334155"),
        )
        prev_button.add_class("pygeomodel-page-button")
        next_button.add_class("pygeomodel-page-button")

        prev_button.on_click(lambda _: self._go_to_page(self.current_page - 1))
        next_button.on_click(lambda _: self._go_to_page(self.current_page + 1))

        page_info = widgets.HTML(
            value=(
                f'<div class="pygeomodel-page-info">Page {self.current_page}/{total_pages}'
                f'<br><span>{total_models} models</span></div>'
            )
        )
        nav_box = self.browser_widgets.get("nav_box")
        model_list = self.browser_widgets.get("model_list")
        if nav_box is None or model_list is None:
            return

        nav_box.children = (prev_button, page_info, next_button)

        buttons = []
        for summary in summaries[start_idx:end_idx]:
            label = summary.display_name or summary.name
            tooltip = summary.description or summary.name
            if label != summary.name:
                tooltip = f"{summary.name}\n{tooltip}"
            button = widgets.Button(
                description=label,
                tooltip=tooltip,
                layout=widgets.Layout(width="100%", margin="3px 0", min_height="36px"),
                style=widgets.ButtonStyle(button_color="white", text_color="#1e293b", font_weight="normal"),
            )
            button.add_class("pygeomodel-model-button")
            button.on_click(lambda _, name=summary.name: self._render_model_detail(name))
            buttons.append(button)
        if not buttons:
            buttons = [widgets.HTML('<div class="pygeomodel-empty">No models found.</div>')]
        model_list.children = tuple(buttons)

    def _go_to_page(self, page: int):
        self.current_page = page
        self._refresh_model_browser()

    def _render_model_detail(self, model_name: str):
        import ipywidgets as widgets

        model = self.modeler.get_model(model_name)
        detail_area = self.browser_widgets.get("model_detail_area")
        if detail_area is None:
            raise RuntimeError("Model browser detail area is not available. Call show_models() before selecting a model.")
        header = self._model_detail_card(widgets, model)
        invoke_button = widgets.Button(
            description="Open invocation form",
            icon="sliders",
            style=widgets.ButtonStyle(button_color="#3b82f6", text_color="white", font_weight="600"),
            layout=widgets.Layout(width="190px", height="36px"),
        )
        invoke_button.add_class("pygeomodel-open-button")
        invoke_button.on_click(lambda _: setattr(detail_area, "children", (self.invoke_model(model_name),)))
        detail_area.children = (header, invoke_button)

    def _empty_detail(self, widgets):
        return widgets.HTML(
            value="""
            <div class="pygeomodel-empty-detail">
                <div class="pygeomodel-empty-title">Select a model service</div>
                <div class="pygeomodel-empty-body">Search or browse the OpenGMS catalog, then open a model to inspect its metadata and invocation form.</div>
            </div>
            """
        )

    def _model_info_header(self, widgets, model, include_qa_button: bool):
        original_name = ""
        if (model.display_name or model.name) != model.name:
            original_name = f'<div class="pygeomodel-original-name"><b>OpenGMS Name:</b> {self._e(model.name)}</div>'
        info = widgets.HTML(
            value=f"""
            <div class="pygeomodel-model-card">
                <h3>{self._e(model.display_name or model.name)}</h3>
                {original_name}
                <p>{self._e(model.description or "No description available.")}</p>
                <div class="pygeomodel-meta">
                    <span><b>Authors' Emails:</b> {self._e(model.author or "Unknown")}</span>
                    <span><b>Tags:</b> {self._e(", ".join(model.tags) or "None")}</span>
                </div>
            </div>
            """,
            layout=widgets.Layout(flex="1"),
        )
        if not include_qa_button:
            return info
        qa_button = widgets.Button(
            description="?",
            tooltip="Hide QA Assistant",
            layout=widgets.Layout(width="30px", height="30px", margin="6px 0 0 10px"),
            style=widgets.ButtonStyle(button_color="#f8fafc", text_color="#64748b", font_weight="bold"),
        )
        qa_button.add_class("pygeomodel-qa-toggle")
        box = widgets.HBox(
            (info, qa_button),
            layout=widgets.Layout(
                padding="0",
                margin="0 0 14px 0",
                align_items="flex-start",
            ),
        )
        box.add_class("pygeomodel-model-info-row")
        return box

    def _model_detail_card(self, widgets, model):
        required = sum(1 for item in model.inputs if item.required)
        optional = len(model.inputs) - required
        original_name = ""
        if (model.display_name or model.name) != model.name:
            original_name = f'<div class="pygeomodel-original-name"><b>OpenGMS Name:</b> {self._e(model.name)}</div>'
        return widgets.HTML(
            value=f"""
            <div class="pygeomodel-detail-card">
                <h3>{self._e(model.display_name or model.name)}</h3>
                {original_name}
                <p>{self._e(model.description or "No description available.")}</p>
                <div class="pygeomodel-detail-grid">
                    <div><b>Inputs</b><span>{len(model.inputs)} total, {required} required, {optional} optional</span></div>
                    <div><b>Outputs</b><span>{len(model.outputs)} service outputs</span></div>
                    <div><b>Author</b><span>{self._e(model.author or "Unknown")}</span></div>
                    <div><b>MD5</b><span>{self._e(model.md5 or "Not listed")}</span></div>
                </div>
            </div>
            """
        )

    def _state_form_widgets(self, widgets, model) -> list[Any]:
        state_desc = {state.get("name", ""): state.get("desc", "") for state in model.states}
        grouped: dict[str, list[Any]] = defaultdict(list)
        for item in model.inputs:
            grouped[item.state].append(item)

        form_widgets: list[Any] = []
        for index, (state_name, inputs) in enumerate(grouped.items()):
            state_box = widgets.VBox(layout=widgets.Layout(margin="0 0 10px 0"))
            state_header = widgets.HTML(
                value=f"""
                <div class="pygeomodel-state-card">
                    <h3>{self._e(state_name or "Model state")}</h3>
                    <p>{self._e(state_desc.get(state_name, "") or "Configure the parameters required by this model state.")}</p>
                </div>
                """
            )
            rows = [state_header, self._parameter_header(widgets)]
            for item in inputs:
                rows.append(self._parameter_row(widgets, item))
            state_box.children = tuple(rows)
            form_widgets.append(state_box)
            if index < len(grouped) - 1:
                form_widgets.append(widgets.HTML('<div class="pygeomodel-divider"></div>'))
        if not form_widgets:
            form_widgets.append(
                widgets.HTML(
                    '<div class="pygeomodel-no-input">This model does not require user input.</div>'
                )
            )
        return form_widgets

    def _parameter_header(self, widgets):
        return widgets.HTML(
            value="""
            <div class="pygeomodel-param-grid pygeomodel-param-header">
                <div>Parameter Name</div>
                <div>Description</div>
                <div>Value</div>
            </div>
            """
        )

    def _parameter_row(self, widgets, item):
        required_label = "Required" if item.required else "Optional"
        required_class = "required" if item.required else "optional"
        name_html = widgets.HTML(
            value=f"""
            <div class="pygeomodel-param-name">
                <span>{self._e(item.name)}</span>
                <em class="{required_class}">{required_label}</em>
            </div>
            """,
            layout=widgets.Layout(width="30%"),
        )
        desc_html = widgets.HTML(
            value=f'<div class="pygeomodel-param-desc">{self._e(item.description or item.data_type)}</div>',
            layout=widgets.Layout(width="42%"),
        )
        value_widget = self._value_widget(widgets, item)
        value_container = widgets.Box((value_widget,), layout=widgets.Layout(width="28%"))
        row = widgets.HBox(
            (name_html, desc_html, value_container),
            layout=widgets.Layout(width="100%", align_items="center"),
        )
        row.add_class("pygeomodel-param-row")
        return row

    def _value_widget(self, widgets, item):
        if item.is_file:
            try:
                from ipyfilechooser import FileChooser

                chooser = FileChooser(path="./", layout=widgets.Layout(width="100%"))
                chooser.add_class("pygeomodel-file-chooser")
                self.param_widgets[item.name] = chooser
                self.widgets[f"param_{item.name}"] = chooser
                return chooser
            except Exception:
                pass
        widget = widgets.Text(
            placeholder="Please input value" if not item.is_file else "Path to input file",
            layout=widgets.Layout(width="100%"),
        )
        widget.add_class("pygeomodel-input")
        self.param_widgets[item.name] = widget
        self.widgets[f"param_{item.name}"] = widget
        return widget

    def _qa_panel(self, widgets, model):
        title = widgets.HTML('<h3 class="pygeomodel-qa-title">Model QA Assistant</h3>')
        question_box = widgets.Text(
            placeholder="Please input your question about this model...",
            description="Question:",
            layout=widgets.Layout(flex="1 1 auto", min_width="0"),
            style={"description_width": "74px"},
        )
        question_box.add_class("pygeomodel-search")
        ask_button = widgets.Button(
            description="Ask",
            style=widgets.ButtonStyle(button_color="#3b82f6", text_color="white", font_weight="600"),
            layout=widgets.Layout(width="78px", height="32px", margin="0 0 0 8px"),
        )
        controls = widgets.HBox(
            (question_box, ask_button),
            layout=widgets.Layout(width="100%", align_items="center", margin="8px 0 12px 0"),
        )
        result_area = widgets.Output(
            layout=widgets.Layout(width="100%", max_height="520px", padding="0", overflow="hidden auto")
        )
        result_area.add_class("pygeomodel-qa-result")

        def ask(_):
            from IPython.display import HTML, display

            question = question_box.value.strip()
            if not question:
                return
            with result_area:
                result_area.clear_output()
                display(HTML(self._render_qa_running_html()))
            try:
                answer = self.modeler.ask_model(model.name, question)
                html_answer = self._render_qa_result_html(answer)
            except Exception as exc:
                html_answer = self._render_qa_error_html(str(exc))
            with result_area:
                result_area.clear_output()
                display(HTML(html_answer))

        ask_button.on_click(ask)
        panel = widgets.VBox(
            (title, controls, result_area),
            layout=widgets.Layout(width="40%", padding="14px 16px", border_left="1px solid #cbd5e1"),
        )
        panel.add_class("pygeomodel-qa-panel")
        return panel

    def _render_qa_result_html(self, answer) -> str:
        return f'<div class="pygeomodel-qa-panel-result">{answer._repr_html_()}</div>'

    def _render_qa_running_html(self) -> str:
        return """
        <div class="pygeomodel-result-card running pygeomodel-qa-status-card">
            <div class="pygeomodel-result-head">
                <span class="pygeomodel-status-pill running">Running</span>
                <div>
                    <h4>Answering question</h4>
                    <p>Searching model knowledge and scientific sources.</p>
                </div>
            </div>
        </div>
        """

    def _render_qa_error_html(self, message: str) -> str:
        return f"""
        <div class="pygeomodel-result-card error pygeomodel-qa-status-card">
            <div class="pygeomodel-result-head">
                <span class="pygeomodel-status-pill error">Failed</span>
                <div>
                    <h4>Q&A request failed</h4>
                    <p>{self._e(message)}</p>
                </div>
            </div>
        </div>
        """

    def _widget_value(self, widget):
        selected = getattr(widget, "selected", None)
        if selected:
            return selected
        return getattr(widget, "value", "")

    def _style_widget(self, widgets):
        return widgets.HTML(
            value="""
            <style>
            .pygeomodel-browser, .pygeomodel-invoke-shell {
                font-family: PingFang SC, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                color: #1e293b;
            }
            .pygeomodel-invoke-shell {
                background: #ffffff;
                border: 1px solid #dbe3ef;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
            }
            .pygeomodel-side-panel {
                background: #f8fafc;
                border-radius: 8px;
                box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05);
            }
            .pygeomodel-detail-panel {
                background: transparent;
                border: none;
                border-radius: 0;
                padding: 0;
                min-height: 420px;
            }
            .pygeomodel-form {
                background: #ffffff;
                border: none;
                border-radius: 0;
                padding: 0;
            }
            .pygeomodel-model-info-row {
                background: transparent;
                border-radius: 0;
            }
            .pygeomodel-qa-panel {
                background: #ffffff;
                min-height: 620px;
                overflow-x: hidden;
            }
            .pygeomodel-qa-panel .widget-hbox {
                max-width: 100%;
            }
            .pygeomodel-qa-result {
                overflow-x: hidden !important;
                overflow-y: auto !important;
                border-radius: 8px;
            }
            .pygeomodel-qa-result .output,
            .pygeomodel-qa-result .output_area,
            .pygeomodel-qa-result .jp-OutputArea-output,
            .pygeomodel-qa-result .vscode-cell-output,
            .pygeomodel-qa-result > div {
                max-width: 100% !important;
                overflow-x: hidden !important;
            }
            .pygeomodel-qa-panel-result {
                max-width: 100%;
                overflow-x: hidden;
            }
            .pygeomodel-qa-status-card {
                margin: 0;
            }
            .pygeomodel-model-button button {
                text-align: left !important;
                justify-content: flex-start !important;
                white-space: normal !important;
                line-height: 1.25 !important;
                border: 1px solid #e2e8f0 !important;
                border-radius: 6px !important;
                box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04) !important;
                transition: all 0.18s ease !important;
            }
            .pygeomodel-model-button button:hover {
                border-color: #93c5fd !important;
                background: #eff6ff !important;
                color: #1d4ed8 !important;
            }
            .pygeomodel-page-button button {
                border-radius: 6px !important;
                border: 1px solid #cbd5e1 !important;
            }
            .pygeomodel-page-info {
                text-align: center;
                font-size: 13px;
                color: #334155;
                line-height: 1.2;
            }
            .pygeomodel-page-info span {
                color: #64748b;
                font-size: 12px;
            }
            .pygeomodel-empty,
            .pygeomodel-empty-detail,
            .pygeomodel-no-input {
                background: #f8fafc;
                border: 1px dashed #cbd5e1;
                border-radius: 8px;
                color: #64748b;
                padding: 16px;
            }
            .pygeomodel-empty-title {
                color: #1e293b;
                font-weight: 600;
                margin-bottom: 6px;
            }
            .pygeomodel-model-card,
            .pygeomodel-detail-card,
            .pygeomodel-state-card {
                background: transparent;
                border: none;
                border-radius: 0;
                padding: 0;
                margin-bottom: 0;
            }
            .pygeomodel-model-card {
                border-bottom: 1px solid #e5edf6;
                padding: 2px 0 14px 0;
            }
            .pygeomodel-state-card {
                padding: 12px 0 10px 0;
            }
            .pygeomodel-model-card h3,
            .pygeomodel-detail-card h3,
            .pygeomodel-state-card h3 {
                margin: 0 0 6px 0;
                color: #1e293b;
                font-size: 16px;
                font-weight: 650;
            }
            .pygeomodel-detail-card h3 {
                font-size: 18px;
            }
            .pygeomodel-model-card p,
            .pygeomodel-detail-card p,
            .pygeomodel-state-card p {
                margin: 0;
                color: #64748b;
                font-size: 14px;
                line-height: 1.5;
            }
            .pygeomodel-original-name {
                color: #64748b;
                font-size: 12px;
                margin: -2px 0 8px 0;
            }
            .pygeomodel-meta {
                display: flex;
                flex-wrap: wrap;
                gap: 12px;
                color: #334155;
                font-size: 13px;
            }
            .pygeomodel-detail-grid {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 10px;
                margin-top: 10px;
            }
            .pygeomodel-detail-grid div {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                padding: 10px;
            }
            .pygeomodel-detail-grid b {
                display: block;
                color: #1e293b;
                margin-bottom: 4px;
            }
            .pygeomodel-detail-grid span {
                color: #64748b;
                font-size: 13px;
            }
            .pygeomodel-param-grid {
                display: grid;
                grid-template-columns: 30% 42% 28%;
                gap: 8px;
                padding: 10px 12px;
                background: #f8fafc;
                border-top: 1px solid #dbe3ef;
                border-bottom: 1px solid #dbe3ef;
                color: #1e293b;
                font-size: 13px;
            }
            .pygeomodel-param-header {
                font-weight: 600;
                border-radius: 0;
            }
            .pygeomodel-param-row {
                border-left: none;
                border-right: none;
                border-bottom: 1px solid #edf2f7;
                padding: 10px 12px;
                background: #ffffff;
            }
            .pygeomodel-param-row:last-child {
                border-radius: 0;
            }
            .pygeomodel-param-name span {
                display: block;
                color: #1e293b;
                font-weight: 500;
                margin-bottom: 4px;
            }
            .pygeomodel-param-name em {
                display: inline-block;
                font-style: normal;
                color: #dc2626;
                background: #fff1f2;
                border: 1px solid #fecaca;
                padding: 1px 7px;
                border-radius: 999px;
                font-size: 11px;
                line-height: 1.5;
            }
            .pygeomodel-param-name em.required { color: #dc2626; background: #fff1f2; border-color: #fecaca; }
            .pygeomodel-param-name em.optional { color: #64748b; background: #f8fafc; border-color: #cbd5e1; }
            .pygeomodel-param-desc {
                color: #64748b;
                font-size: 13px;
                line-height: 1.45;
                padding-right: 8px;
            }
            .pygeomodel-divider {
                border-top: 2px solid #1e293b;
                margin: 12px 16px;
            }
            .pygeomodel-qa-toggle button {
                border-radius: 50% !important;
                border: 1px solid #e2e8f0 !important;
                box-shadow: 0 1px 2px rgba(15, 23, 42, 0.1) !important;
                padding: 0 !important;
                min-width: 28px !important;
            }
            .pygeomodel-qa-toggle button:hover {
                transform: scale(1.05);
                background: #ffffff !important;
            }
            .pygeomodel-qa-title {
                margin: 0 0 2px 0;
                color: #1e293b;
                font-size: 17px;
            }
            .pygeomodel-output {
                background: #fbfdff;
                border-top: 1px solid #e5edf6;
                border-radius: 6px;
            }
            .pygeomodel-result-card {
                background: #ffffff;
                border: 1px solid #dbe3ef;
                border-radius: 8px;
                padding: 14px;
                box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
                color: #1e293b;
            }
            .pygeomodel-result-card.error {
                border-color: #fecaca;
                background: #fffafa;
            }
            .pygeomodel-result-card.running {
                border-color: #bfdbfe;
                background: #f8fbff;
            }
            .pygeomodel-result-head {
                display: flex;
                align-items: flex-start;
                gap: 10px;
                margin-bottom: 12px;
            }
            .pygeomodel-result-head h4 {
                margin: 0 0 3px 0;
                font-size: 15px;
                font-weight: 650;
                color: #0f172a;
            }
            .pygeomodel-result-head p {
                margin: 0;
                font-size: 13px;
                color: #64748b;
                line-height: 1.45;
            }
            .pygeomodel-status-pill {
                display: inline-flex;
                align-items: center;
                min-width: 76px;
                justify-content: center;
                padding: 3px 9px;
                border-radius: 999px;
                font-size: 12px;
                font-weight: 650;
                line-height: 1.5;
                text-transform: capitalize;
            }
            .pygeomodel-status-pill.success {
                color: #166534;
                background: #dcfce7;
                border: 1px solid #bbf7d0;
            }
            .pygeomodel-status-pill.error {
                color: #b91c1c;
                background: #fee2e2;
                border: 1px solid #fecaca;
            }
            .pygeomodel-status-pill.running {
                color: #1d4ed8;
                background: #dbeafe;
                border: 1px solid #bfdbfe;
            }
            .pygeomodel-status-pill.neutral {
                color: #475569;
                background: #f1f5f9;
                border: 1px solid #cbd5e1;
            }
            .pygeomodel-result-grid {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 8px;
                margin: 6px 0 14px 0;
            }
            .pygeomodel-result-grid div {
                background: #f8fafc;
                border: 1px solid #e5edf6;
                border-radius: 6px;
                padding: 8px 10px;
                min-width: 0;
            }
            .pygeomodel-result-grid b {
                display: block;
                margin-bottom: 3px;
                font-size: 12px;
                color: #64748b;
                font-weight: 600;
            }
            .pygeomodel-result-grid span {
                display: block;
                color: #1e293b;
                font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
                font-size: 12px;
                overflow-wrap: anywhere;
            }
            .pygeomodel-output-section h5 {
                margin: 0 0 8px 0;
                color: #0f172a;
                font-size: 13px;
                font-weight: 650;
            }
            .pygeomodel-output-table {
                width: 100%;
                border-collapse: collapse;
                table-layout: fixed;
                border: 1px solid #dbe3ef;
                border-radius: 6px;
                overflow: hidden;
                font-size: 12px;
            }
            .pygeomodel-output-col-name { width: 34%; }
            .pygeomodel-output-col-state { width: 22%; }
            .pygeomodel-output-col-event { width: 14%; }
            .pygeomodel-output-col-format { width: 13%; }
            .pygeomodel-output-col-action { width: 17%; }
            .pygeomodel-output-table th {
                background: #f8fafc;
                color: #475569;
                font-weight: 650;
                text-align: left !important;
                padding: 8px;
                border-bottom: 1px solid #dbe3ef;
            }
            .pygeomodel-output-table td {
                padding: 8px;
                border-bottom: 1px solid #edf2f7;
                color: #1e293b;
                text-align: left !important;
                vertical-align: top;
                overflow-wrap: anywhere;
            }
            .pygeomodel-output-table tr:last-child td {
                border-bottom: none;
            }
            .pygeomodel-output-link {
                display: inline-flex;
                align-items: center;
                color: #1d4ed8;
                font-weight: 650;
                text-decoration: none;
            }
            .pygeomodel-output-link:hover {
                text-decoration: underline;
            }
            .pygeomodel-output-muted,
            .pygeomodel-output-empty {
                color: #64748b;
                font-size: 12px;
            }
            .pygeomodel-output-empty {
                background: #f8fafc;
                border: 1px dashed #cbd5e1;
                border-radius: 6px;
                padding: 9px 10px;
                margin-bottom: 8px;
            }
            .pygeomodel-details {
                margin-top: 12px;
                border-top: 1px solid #e5edf6;
                padding-top: 9px;
                color: #475569;
                font-size: 12px;
            }
            .pygeomodel-details summary {
                cursor: pointer;
                font-weight: 650;
                color: #334155;
                user-select: none;
            }
            .pygeomodel-detail-block {
                margin-top: 9px;
            }
            .pygeomodel-detail-block b {
                display: block;
                margin-bottom: 4px;
                color: #475569;
            }
            .pygeomodel-detail-block pre,
            .pygeomodel-json-preview {
                margin: 0;
                white-space: pre-wrap;
                word-break: break-word;
                background: #0f172a;
                color: #e2e8f0;
                border-radius: 6px;
                padding: 10px;
                font-size: 12px;
                line-height: 1.45;
                max-height: 240px;
                overflow: auto;
            }
            .pygeomodel-input input,
            .pygeomodel-search input {
                border: 1px solid #cbd5e1 !important;
                border-radius: 4px !important;
                box-shadow: none !important;
            }
            .pygeomodel-input input:focus,
            .pygeomodel-search input:focus {
                border-color: #3b82f6 !important;
                box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.14) !important;
            }
            .pygeomodel-button-row {
                gap: 10px;
            }
            .pygeomodel-spinner-text {
                color: #64748b;
                font-size: 13px;
            }
            </style>
            """
        )

    def _e(self, value: Any) -> str:
        return html.escape(str(value))
