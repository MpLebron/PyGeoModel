import asyncio
import time
import json
import os
import gc
import weakref
import sys
from typing import Dict, List, Optional

# Lazy import modules that may not be installed


def _lazy_import_ipywidgets():
    """Lazy import ipywidgets."""
    global widgets
    if 'widgets' not in globals():
        import ipywidgets as widgets
    return widgets


def _lazy_import_ipython_display():
    """Lazy import IPython display."""
    global display, HTML, clear_output
    if 'display' not in globals():
        from IPython.display import display, HTML, clear_output
    return display, HTML, clear_output


# Basic modules


def _lazy_import_ipython():
    """Lazy import IPython."""
    global get_ipython
    if 'get_ipython' not in globals():
        from IPython import get_ipython
    return get_ipython

# Lazy imports - only import when needed


def _lazy_import_openmodel():
    """Lazy import openModel module."""
    global openModel
    if 'openModel' not in globals():
        import ogmsServer2.openModel as openModel
    return openModel


def _lazy_import_config():
    """Lazy import config module."""
    global config
    if 'config' not in globals():
        import config
    return config


def _lazy_import_requests():
    """Lazy import requests."""
    global requests
    if 'requests' not in globals():
        import requests
    return requests


def _lazy_import_academic_service():
    """Lazy import academic query service."""
    global AcademicQueryService
    if 'AcademicQueryService' not in globals():
        from scripts import AcademicQueryService
    return AcademicQueryService


def _lazy_import_openai():
    """Lazy import OpenAI."""
    global OpenAI
    if 'OpenAI' not in globals():
        from openai import OpenAI
    return OpenAI


def _lazy_import_filechooser():
    """Lazy import FileChooser."""
    global FileChooser
    if 'FileChooser' not in globals():
        from ipyfilechooser import FileChooser
    return FileChooser


def _lazy_import_markdown():
    """Lazy import markdown."""
    global markdown, Markdown
    if 'markdown' not in globals():
        from markdown import markdown
        from IPython.display import Markdown
    return markdown, Markdown


def _lazy_import_nest_asyncio():
    """Lazy import nest_asyncio."""
    global nest_asyncio
    if 'nest_asyncio' not in globals():
        import nest_asyncio
    return nest_asyncio


# Apply nest_asyncio at file start (if available)
try:
    _lazy_import_nest_asyncio().apply()
except ImportError:
    # Skip if nest_asyncio is not available
    pass

# Utility functions


def cleanup_memory():
    """Utility function to clean up memory."""
    gc.collect()
    # Clean weak references - use safer approach
    try:
        # Try to clean weak references, skip if failed
        if hasattr(weakref, '_weakrefs'):
            for obj in list(weakref._weakrefs):
                if obj() is None:
                    weakref._weakrefs.remove(obj)
    except (AttributeError, RuntimeError):
        # Skip if weakref._weakrefs doesn't exist or access failed
        pass


def safe_import(module_name):
    """Safely import a module."""
    try:
        return __import__(module_name)
    except ImportError:
        return None


class Model:
    """Model base class for handling model properties and operations."""

    def __init__(self, model_name, model_data):
        mdl_json = model_data.get("mdlJson", {})
        mdl = mdl_json.get("mdl", {})

        self.id = model_data.get("_id", "")
        self.name = model_name  # Use key name as model name
        self.description = model_data.get("description", "")
        self.author = model_data.get("author", "")
        self.tags = model_data.get("normalTags", [])
        self.tags_en = model_data.get("normalTagsEn", [])

        self.states = mdl.get("states", [])


class GeoModeler:
    """Intelligent geographic modeling assistant for model management, recommendation and UI."""

    def __init__(self):
        # Memory management
        self._instances = weakref.WeakSet()  # Track instances
        self._instances.add(self)

        # Model data - lightweight management
        self.models = {}  # Store loaded models (loaded on demand)
        self.model_names = []  # Store all model names
        self._model_cache = {}  # Model data cache
        self._max_cache_size = 10  # Maximum cache size

        # UI state
        self.current_model = None
        self.widgets = {}  # Store UI components
        self.page_size = 20
        self.current_page = 1
        self.filtered_models = []

        # Context data - lazy loading
        self._context_cache = {}
        self._context_cache_timeout = 300  # 5-minute cache

        # Initialize
        self._load_model_names()

        # Register cleanup function
        import atexit
        atexit.register(self._cleanup)

    def _cleanup(self):
        """Clean up resources."""
        try:
            # Clean UI components
            for widget_key in list(self.widgets.keys()):
                if widget_key in self.widgets:
                    widget = self.widgets[widget_key]
                    if hasattr(widget, 'close'):
                        widget.close()
                    del self.widgets[widget_key]

            # Clean model cache
            self.models.clear()
            self._model_cache.clear()
            self._context_cache.clear()

            # Clean weak references
            cleanup_memory()

        except Exception as e:
            print(f"Error during cleanup: {e}")

    def __del__(self):
        """Destructor."""
        if hasattr(self, '_instances'):
            self._instances.discard(self)
        self._cleanup()

    def _load_model_names(self):
        """Lightweight load - only load model names, not full data."""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(current_dir, "data", "computeModel.json")

        try:
            with open(json_path, encoding='utf-8') as f:
                models_data = json.load(f)
                self.model_names = list(models_data.keys())
        except Exception as e:
            print(f"Failed to load model names: {str(e)}")
            self.model_names = []

    def _load_models(self):
        """Load full data for all models (kept for backward compatibility)."""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(current_dir, "data", "computeModel.json")

        try:
            with open(json_path, encoding='utf-8') as f:
                models_data = json.load(f)
                for model_name, model_data in models_data.items():
                    self.models[model_name] = Model(model_name, model_data)
        except Exception as e:
            print(f"Failed to load model configuration file: {str(e)}")
            self.models = {}

    def load_model_on_demand(self, model_name):
        """Load specific model on demand (with cache and memory management)."""
        # Check if already loaded
        if model_name in self.models:
            return self.models[model_name]

        # Check cache
        if model_name in self._model_cache:
            model_data = self._model_cache[model_name]
            self.models[model_name] = Model(model_name, model_data)
            return self.models[model_name]

        if model_name not in self.model_names:
            print(f"Model '{model_name}' not found")
            return None

        # Load specific model data from file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(current_dir, "data", "computeModel.json")

        try:
            with open(json_path, encoding='utf-8') as f:
                models_data = json.load(f)
                if model_name in models_data:
                    model_data = models_data[model_name]

                    # Add to cache
                    if len(self._model_cache) >= self._max_cache_size:
                        # Remove oldest cache entry
                        oldest_key = next(iter(self._model_cache))
                        del self._model_cache[oldest_key]

                    self._model_cache[model_name] = model_data
                    self.models[model_name] = Model(model_name, model_data)

                    # Periodically clean up memory
                    if len(self.models) % 5 == 0:
                        cleanup_memory()

                    return self.models[model_name]
        except Exception as e:
            print(f"Failed to load model '{model_name}': {str(e)}")
            return None

    def show_models(self):
        """Display model list interface."""
        widgets = _lazy_import_ipywidgets()
        main_widget = widgets.HBox(layout=widgets.Layout(width='100%'))

        # Create left panel
        left_panel = widgets.VBox(
            layout=widgets.Layout(width='300px', margin='10px'))

        # Create search box
        search_box = widgets.Text(
            placeholder='Search...',
            description='Search:',
            layout=widgets.Layout(width='100%', margin='5px 0')
        )
        search_box.observe(self._on_search, 'value')

        # Create pagination navigation container
        self.widgets['nav_box'] = widgets.HBox(layout=widgets.Layout(
            width='100%',
            margin='5px 0',
            justify_content='space-between'
        ))

        # Create model list container
        self.widgets['model_list'] = widgets.VBox(
            layout=widgets.Layout(width='100%'))

        # Assemble left panel
        left_panel.children = [
            search_box,
            self.widgets['nav_box'],
            self.widgets['model_list']
        ]

        # Create right panel for model details
        right_panel = widgets.VBox(
            layout=widgets.Layout(flex='1', margin='10px'))
        self.widgets['model_detail_area'] = right_panel

        main_widget.children = [left_panel, right_panel]

        # Initial display
        self._update_model_list()

        return main_widget

    def suggest_model(self):
        """Display model recommendation context data (optimized memory usage)."""
        # Periodically clean up memory
        cleanup_memory()

        # Create NotebookContext instance (using cache)
        import time
        cache_key = "notebook_context"
        current_time = time.time()

        if (cache_key in self._context_cache and
                current_time - self._context_cache[cache_key]['time'] < self._context_cache_timeout):
            # Use cached context
            context_data = self._context_cache[cache_key]['data']
        else:
            # Create new context and cache it
            notebook_context = NotebookContext()
            context_data = {
                "modeling_history": notebook_context.history_context,
                "data_context": notebook_context.data_context
            }

            # Update cache
            self._context_cache[cache_key] = {
                'data': context_data,
                'time': current_time
            }

            # Clean up notebook_context object
            del notebook_context
            cleanup_memory()

        # Display loading state
        loading_html = """
        <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 20px 0;">
            <div class="loading-spinner"></div>
            <p style="margin-top: 10px; color: #6b7280;">Getting model recommendations, please wait...</p>
            <style>
            .loading-spinner {
                width: 40px;
                height: 40px;
                border: 4px solid rgba(79, 70, 229, 0.2);
                border-radius: 50%;
                border-top-color: #4f46e5;
                animation: spin 1s linear infinite;
            }
            @keyframes spin {
                to { transform: rotate(360deg); }
            }
            </style>
        </div>
        """
        display, HTML, _ = _lazy_import_ipython_display()
        loading_display = display(HTML(loading_html), display_id='loading')

        try:
            # Call API to get model recommendations
            requests = _lazy_import_requests()
            import json

            # API configuration
            cfg = _lazy_import_config()
            dify_api_key, dify_base_url = cfg.get_dify_config()
            api_url = f'{dify_base_url}/workflows/run'
            api_key = dify_api_key

            # Prepare request data
            payload = {
                "inputs": {
                    "modeling_history": context_data["modeling_history"],
                    "data_context": context_data["data_context"]
                },
                "response_mode": "blocking",  # Use blocking mode
                "user": "jupyter_user"  # User identifier
            }

            # Set request headers
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }

            # Send POST request
            response = requests.post(api_url, headers=headers, json=payload)

            # Clear loading state
            loading_display.update(HTML(''))

            # Process response
            if response.status_code == 200:
                result = response.json()

                # Parse result based on API response - correct parsing path
                if 'data' in result and 'outputs' in result['data']:
                    # Get API returned object directly, this is a complete JSON object, not text
                    recommendation_data = result['data']['outputs']

                    # Check if model_recommendation field is directly included
                    if 'model_recommendation' in recommendation_data:
                        model_rec = recommendation_data['model_recommendation']
                        recommended_data = recommendation_data.get(
                            'recommended_data', {})
                    else:
                        # If not directly included, may be nested text, need to parse
                        try:
                            # Try to parse JSON in text field
                            text_content = recommendation_data.get(
                                'text', '{}')
                            if isinstance(text_content, str):
                                parsed_content = json.loads(text_content)
                                model_rec = parsed_content.get(
                                    'model_recommendation', {})
                                recommended_data = parsed_content.get(
                                    'recommended_data', {})
                            else:
                                model_rec = {}
                                recommended_data = {}
                        except:
                            model_rec = {}
                            recommended_data = {}

                    # Extract info from model_rec
                    model_name = model_rec.get('name', 'Unknown Model')
                    model_desc = model_rec.get('description', 'No Description')
                    key_strengths = model_rec.get('key_strengths', [])
                    rec_reason = model_rec.get('recommendation_reason', '')
                    app_scenario = model_rec.get('application_scenario', '')

                    # Extract info from recommended_data
                    local_data = recommended_data.get('local_data', [])
                    kb_data = recommended_data.get('knowledge_base_data', [])

                    if model_name != 'Unknown Model':  # Ensure we have at least a model name
                        # Build elegant HTML display
                        html_output = f"""
                        <style>
                            .model-rec-container {{
                                font-family: 'PingFang SC', -apple-system, BlinkMacSystemFont, sans-serif;
                                width: 100%;
                                margin: 0;
                            }}
                            .model-rec-header {{
                                background: #f8fafc;
                                color: #1e293b;
                                padding: 16px 20px;
                                border: 1px solid #e2e8f0;
                                border-radius: 8px 8px 0 0;
                                font-size: 20px;
                                font-weight: 600;
                            }}
                            .model-rec-body {{
                                background: #f8fafc;
                                border: 1px solid #e2e8f0;
                                border-top: none;
                                border-radius: 0 0 8px 8px;
                                padding: 20px;
                                display: grid;
                                grid-template-columns: 1fr 1fr;
                                gap: 20px;
                            }}
                            .model-rec-section {{
                                margin-bottom: 18px;
                            }}
                            .model-rec-title {{
                                font-size: 16px;
                                font-weight: 600;
                                color: #1e293b;
                                margin-bottom: 8px;
                                border-bottom: 1px solid #e2e8f0;
                                padding-bottom: 6px;
                            }}
                            .model-rec-name {{
                                font-size: 20px;
                                font-weight: 600;
                                color: #1e293b;
                                margin-bottom: 10px;
                            }}
                            .model-rec-desc {{
                                color: #64748b;
                                line-height: 1.6;
                                margin-bottom: 15px;
                                font-size: 14px;
                            }}
                            .model-rec-strengths {{
                                list-style-type: none;
                                padding-left: 0;
                                margin-top: 0;
                            }}
                            .model-rec-strengths li {{
                                margin-bottom: 6px;
                                padding-left: 20px;
                                position: relative;
                                color: #64748b;
                                font-size: 14px;
                            }}
                            .model-rec-strengths li:before {{
                                content: "✓";
                                position: absolute;
                                left: 0;
                                color: #059669;
                                font-weight: bold;
                            }}
                            .model-rec-data-item {{
                                background: #ffffff;
                                border: 1px solid #e2e8f0;
                                border-radius: 6px;
                                padding: 12px 15px;
                                margin-bottom: 8px;
                            }}
                            .model-rec-data-name {{
                                font-weight: 500;
                                color: #1e293b;
                                font-size: 14px;
                            }}
                            .model-rec-data-location {{
                                color: #64748b;
                                font-size: 13px;
                                margin-top: 4px;
                            }}
                            .model-rec-kb-link {{
                                color: #1e293b;
                                text-decoration: none;
                            }}
                            .model-rec-kb-link:hover {{
                                text-decoration: underline;
                            }}
                            .model-rec-tag {{
                                display: inline-block;
                                background: #e2e8f0;
                                color: #64748b;
                                border-radius: 4px;
                                padding: 3px 8px;
                                font-size: 12px;
                                margin-right: 6px;
                                margin-bottom: 4px;
                            }}
                        </style>
                        
                        <div class="model-rec-container">
                            <div class="model-rec-header">Model Recommendation</div>
                            <div class="model-rec-body">
                                <div class="model-rec-section">
                                    <div class="model-rec-name">{model_name}</div>
                                    <div class="model-rec-desc">{model_desc}</div>
                                </div>
                                
                                <div class="model-rec-section">
                                    <div class="model-rec-title">Core Advantages</div>
                                    <ul class="model-rec-strengths">
                                        {"".join([f'<li>{strength}</li>' for strength in key_strengths])}
                                    </ul>
                                </div>
                                
                                <div class="model-rec-section">
                                    <div class="model-rec-title">Recommendation Reason</div>
                                    <div class="model-rec-desc">{rec_reason}</div>
                                </div>
                                
                                <div class="model-rec-section">
                                    <div class="model-rec-title">Application Scenarios</div>
                                    <div class="model-rec-desc">{app_scenario}</div>
                                </div>
                        """

                        # Add recommended data section
                        if local_data or kb_data:
                            html_output += """
                                <div class="model-rec-section" style="grid-column: 1 / -1;">
                                    <div class="model-rec-title">Recommended Data Resources</div>
                                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                            """

                            # Add local data column
                            html_output += """
                                <div>
                                    <div style="font-weight: 500; color: #1e293b; margin-bottom: 8px; font-size: 14px;">Local Data:</div>
                            """
                            if local_data:
                                for data_item in local_data:
                                    html_output += f"""
                                        <div class="model-rec-data-item">
                                            <div class="model-rec-data-name">{data_item.get('name', 'Unnamed Data')}</div>
                                            <div class="model-rec-data-location">📁 {data_item.get('location', 'Unknown Location')}</div>
                                        </div>
                                    """
                            else:
                                html_output += """
                                    <div class="model-rec-data-item">
                                        <div class="model-rec-data-name">No local data available</div>
                                    </div>
                                """
                            html_output += "</div>"

                            # Add knowledge base data column
                            html_output += """
                                <div>
                                    <div style="font-weight: 500; color: #1e293b; margin-bottom: 8px; font-size: 14px;">Data Center Data:</div>
                            """
                            if kb_data:
                                for kb_item in kb_data:
                                    kb_name = kb_item.get(
                                        'name', 'Unnamed Dataset')
                                    kb_url = kb_item.get('url', '#')
                                    html_output += f"""
                                        <div class="model-rec-data-item">
                                            <div class="model-rec-data-name">{kb_name}</div>
                                            <div class="model-rec-data-location">
                                                <a href="{kb_url}" class="model-rec-kb-link" target="_blank">🔗 View Data</a>
                                            </div>
                                        </div>
                                    """
                            else:
                                html_output += """
                                    <div class="model-rec-data-item">
                                        <div class="model-rec-data-name">No data center data available</div>
                                    </div>
                                """
                            html_output += "</div>"

                            # Close grid container for data resources
                            html_output += """
                                    </div>
                                </div>
                            """

                        # Close container div
                        html_output += """
                            </div>
                        </div>
                        """

                        # Display result
                        display(HTML(html_output))
                    else:
                        # Handle case with no model recommendation
                        error_msg = "No valid model recommendation information found in API response"
                        self._display_error_message(error_msg)

                        # Show raw data for debugging
                        debug_html = f"""
                        <details>
                            <summary style="cursor: pointer; color: #6b7280; margin: 10px 0;">Show Raw API Response Data</summary>
                            <pre style="background: #f1f5f9; padding: 10px; border-radius: 4px; overflow: auto; max-height: 400px;">
                            {json.dumps(result, indent=2, ensure_ascii=False)}
                            </pre>
                        </details>
                        """
                        display(HTML(debug_html))
                else:
                    # Handle API response format not meeting expectations
                    error_msg = "API response data format does not meet expectations"
                    self._display_error_message(error_msg)

                    # Show raw data for debugging
                    debug_html = f"""
                    <details>
                                                    <summary style="cursor: pointer; color: #6b7280; margin: 10px 0;">Show Raw API Response Data</summary>
                        <pre style="background: #f1f5f9; padding: 10px; border-radius: 4px; overflow: auto; max-height: 400px;">
                        {json.dumps(result, indent=2, ensure_ascii=False)}
                        </pre>
                    </details>
                    """
                    display(HTML(debug_html))
            else:
                error_msg = f"API request failed: HTTP {response.status_code} - {response.text}"
                self._display_error_message(error_msg)

        except Exception as e:
            # Clear loading state

            # Display error message
            self._display_error_message(
                f"Model recommendation service call failed: {str(e)}")

        # Don't return any value to avoid unnecessary debug info in Jupyter
        return None

    def _display_error_message(self, message):
        """Display error message."""
        from IPython.display import HTML, display
        error_html = f"""
        <div style="background: #fee2e2; border-left: 4px solid #ef4444; padding: 12px 15px; margin: 10px 0; border-radius: 4px; color: #b91c1c;">
            <div style="font-weight: 500; margin-bottom: 5px;">Error</div>
            <div>{message}</div>
        </div>
        """
        display(HTML(error_html))

    def _show_running_spinner(self):
        """Display running animation at top of right panel."""
        display, HTML, _ = _lazy_import_ipython_display()
        spinner_html = (
            "<div id=\"ogms-running\" style=\"display:flex;align-items:center;gap:10px;margin:6px 0;\">"
            "<div style=\"width:16px;height:16px;border:2px solid rgba(79,70,229,.2);"
            "border-top-color:#4f46e5;border-radius:50%;animation:ogms-spin 1s linear infinite;\"></div>"
            "<span style=\"font-size:13px;color:#6b7280;\">Model calculating...</span>"
            "<style>@keyframes ogms-spin{to{transform:rotate(360deg);}}</style>"
            "</div>"
        )
        display(HTML(spinner_html))

    def _hide_running_spinner(self):
        """Remove running animation (if env supports DOM update, Notebook refresh will clear it)."""
        # Simple implementation: do nothing, new output will overwrite old content
        pass

    def _update_model_list(self, filter_text=''):
        """Update model list."""
        # Update filtered model list (lightweight search, based on model names only)
        if filter_text.strip() == "":
            # Show all models when no search condition
            self.filtered_models = sorted(self.model_names)
        else:
            # Filter based on model name when search condition exists
            self.filtered_models = [
                model_name for model_name in sorted(self.model_names)
                if filter_text.lower() in model_name.lower()
            ]

        # Reset page number
        self.current_page = 1

        # Update display
        self._refresh_display()

    def _refresh_display(self):
        """Refresh current page display."""
        # Calculate page info
        total_models = len(self.filtered_models)
        total_pages = max(
            1, (total_models + self.page_size - 1) // self.page_size)
        start_idx = (self.current_page - 1) * self.page_size
        end_idx = min(start_idx + self.page_size, total_models)

        # Update navigation buttons and page info
        prev_button = widgets.Button(
            description='Previous',
            disabled=self.current_page == 1,
            layout=widgets.Layout(width='80px'),
            style=widgets.ButtonStyle(button_color='#e2e8f0')  # Add soft background color
        )
        prev_button.on_click(self._prev_page)

        next_button = widgets.Button(
            description='Next',
            disabled=self.current_page == total_pages,
            layout=widgets.Layout(width='80px'),
            style=widgets.ButtonStyle(button_color='#e2e8f0')  # Add soft background color
        )
        next_button.on_click(self._next_page)

        page_info = widgets.HTML(
            value=f'<div style="text-align: center;">Page {self.current_page}/{total_pages}</div>'
        )

        self.widgets['nav_box'].children = [
            prev_button, page_info, next_button]

        # Update model list
        model_buttons = []
        for model_name in self.filtered_models[start_idx:end_idx]:
            button = widgets.Button(
                description=model_name,
                layout=widgets.Layout(
                    width='100%',
                    margin='3px 0',  # Increase button spacing
                    padding='6px 10px'  # Increase button padding
                ),
                style=widgets.ButtonStyle(
                    button_color='white',  # Button background color
                    font_weight='normal'  # Font weight
                )
            )
            button.on_click(self._on_model_button_clicked)
            model_buttons.append(button)

        self.widgets['model_list'].children = tuple(model_buttons)

    def _prev_page(self, b):
        """Go to previous page."""
        if self.current_page > 1:
            self.current_page -= 1
            self._refresh_display()

    def _next_page(self, b):
        """Go to next page."""
        total_pages = (len(self.filtered_models) +
                       self.page_size - 1) // self.page_size
        if self.current_page < total_pages:
            self.current_page += 1
            self._refresh_display()

    def _on_search(self, change):
        """Handle search event."""
        search_text = change['new']
        self._update_model_list(search_text)

    def _on_model_button_clicked(self, button):
        """Handle model button click event."""
        model_name = button.description
        # print(f"Clicked model: {model_name}")  # Debug info

        # Display model interface in right panel
        self._show_model_in_panel(model_name)

    def _show_model_in_panel(self, model_name):
        """Display model interface in side panel."""
        if model_name not in self.model_names:
            print(f"Error: Model '{model_name}' does not exist")
            return

        # Load model on demand
        model = self.load_model_on_demand(model_name)
        if model is None:
            print(f"Error: Failed to load model '{model_name}'")
            return

        self.current_model = model

        # Create main container
        main_container = widgets.VBox()
        widgets_list = []

        # Add model basic info
        model_info = widgets.HTML(value=f"""
            <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px; margin-bottom: 10px;">
                <h3 style="margin-top: 0;">{self.current_model.name}</h3>
                <p style="color: #666; margin-bottom: 8px;">{self.current_model.description}</p>
                <div style="display: flex; gap: 10px;">
                    <div>
                        <span style="color: #666;">Authors' Emails: </span>
                        <span>{self.current_model.author}</span>
                    </div>
                    <div>
                        <span style="color: #666;">Tags: </span>
                        <span>{', '.join(self.current_model.tags)}</span>
                    </div>
                </div>
            </div>
        """)
        widgets_list.append(model_info)

        # Hidden trigger button (pure widgets, for reliable Python callback triggering)
        hidden_trigger_btn = widgets.Button(
            description='',
            layout=widgets.Layout(width='0px', height='0px',
                                  padding='0', margin='0', border='0'),
            style=widgets.ButtonStyle(button_color='#ffffff')
        )
        hidden_trigger_btn._dom_classes = ['qa-hidden-trigger']
        # Put in minimal container to avoid affecting layout
        widgets_list.append(widgets.Box(
            [hidden_trigger_btn], layout=widgets.Layout(width='0px', height='0px')))
        # Save reference for later callback binding
        self.widgets['qa_hidden_btn'] = hidden_trigger_btn

        # Iterate through states
        for i, state in enumerate(self.current_model.states):
            state_container = widgets.VBox(
                layout=widgets.Layout(margin='0 0 8px 0')
            )
            state_widgets = []

            # Add state info
            state_info = widgets.HTML(value=f"""
                <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px; margin-bottom: 8px;">
                    <h3 style="color: #1e293b; margin: 0 0 4px 0; font-size: 16px; font-weight: 600;">{state.get('name', '')}</h3>
                    <p style="color: #64748b; margin: 0; font-size: 14px;">{state.get('desc', '')}</p>
                </div>
            """)
            state_widgets.append(state_info)

            # Check if this state has events requiring user input
            has_input_events = False
            for event in state.get('event', []):
                if event.get('eventType') == 'response':
                    has_input_events = True
                    event_container = widgets.VBox(
                        layout=widgets.Layout(margin='3px 0'))
                    event_widgets = []

                    event_name = event.get('eventName', '')
                    optional_text = "Required" if not event.get(
                        'optional', False) else "Optional"
                    event_desc = event.get('eventDesc', '')

                    # Add event title and description
                    event_header = widgets.HTML(value=f"""
                        <div style="margin: 2px 0;">
                            <span style="font-weight: 500;">{event_name}</span>
                            <span style="background: {('#ef4444' if optional_text == 'Required' else '#94a3b8')}; 
                                     color: white; 
                                     padding: 1px 8px; 
                                     border-radius: 12px; 
                                     font-size: 12px; 
                                     margin-left: 8px;">
                                {optional_text}
                            </span>
                            <div style="color: #666; margin: 1px 0 2px 0;">{event_desc}</div>
                        </div>
                    """)
                    event_widgets.append(event_header)

                    # Check if contains nodes data
                    has_nodes = False
                    nodes_data = []
                    for data_item in event.get('data', []):
                        if 'nodes' in data_item:
                            has_nodes = True
                            nodes_data = data_item['nodes']

                    if has_nodes:
                        # Create table container
                        table_container = widgets.VBox()
                        table_widgets = []

                        # Add table header
                        header = widgets.HTML(value="""
                            <div style="display: grid; grid-template-columns: 1fr 2fr 1fr; gap: 8px; padding: 8px; background: #f8fafc; border: 1px solid #e2e8f0;">
                                <div style="font-weight: 500;">Parameter Name</div>
                                <div style="font-weight: 500;">Description</div>
                                <div style="font-weight: 500;">Value</div>
                            </div>
                        """)
                        table_widgets.append(header)

                        # Create a row for each parameter
                        for node in nodes_data:
                            # Create row container
                            row = widgets.HBox([
                                widgets.HTML(value=f"""
                                    <div style="padding: 8px; min-width: 150px;">{node.get('text', '')}</div>
                                """),
                                widgets.HTML(value=f"""
                                    <div style="padding: 8px; min-width: 200px;">{node.get('desc', '')}</div>
                                """),
                                widgets.Text(
                                    placeholder='Please input value',
                                    layout=widgets.Layout(width='150px')
                                )
                            ])
                            # Store Text widget reference
                            self.widgets[f'node-{event_name}-{node.get("text")}'] = row.children[-1]
                            table_widgets.append(row)

                        table_container.children = table_widgets
                        event_widgets.append(table_container)
                    else:
                        # Create file chooser
                        FileChooser = _lazy_import_filechooser()
                        fc = FileChooser(
                            path='./',
                            layout=widgets.Layout(width='100%')
                        )
                        self.widgets[f'file_chooser_{event_name}'] = fc
                        event_widgets.append(fc)

                    event_container.children = event_widgets
                    state_widgets.append(event_container)

            # If no input events, add prompt info
            if not has_input_events:
                no_input_msg = widgets.HTML(value="""
                    <div style="padding: 8px 12px; 
                                background: #f8fafc; 
                                border: 1px dashed #e2e8f0; 
                                border-radius: 4px; 
                                color: #64748b; 
                                font-size: 14px; 
                                margin: 4px 0;">
                        This state does not require user input
                    </div>
                """)
                state_widgets.append(no_input_msg)

            state_container.children = state_widgets
            widgets_list.append(state_container)

            if i < len(self.current_model.states) - 1:
                divider = widgets.HTML(value="""
                    <div style="padding: 0 16px;">
                        <hr style="border: none; border-top: 2px solid #1e293b; margin: 12px 0;">
                    </div>
                """)
                widgets_list.append(divider)

        # Create output area
        self.widgets['output_area'] = widgets.Output()
        # Add output area to widgets_list
        widgets_list.append(self.widgets['output_area'])

        # Create button container (horizontal layout, right aligned)
        button_container = widgets.HBox(
            layout=widgets.Layout(
                display='flex',
                justify_content='flex-end',
                gap='10px'
            )
        )

        # Create Run button (disabled during execution)
        run_button = widgets.Button(
            description='Run',
            style=widgets.ButtonStyle(
                button_color='#4CAF50', text_color='white')
        )

        # Running animation (placed to the right of button, hidden by default)
        spinner_widget = widgets.HTML(
            value='', layout=widgets.Layout(margin='0 6px'))
        self.widgets['running_spinner'] = spinner_widget

        def on_run_click(b):
            # Disable button, switch text and icon to running state
            run_button.disabled = True
            original_desc = run_button.description
            original_icon = getattr(run_button, 'icon', '')
            run_button.description = 'Model calculating...'
            # Use fontawesome spinner icon in button and inject rotation CSS
            try:
                run_button.icon = 'spinner'
                display, HTML, _ = _lazy_import_ipython_display()
                if not getattr(self, '_spinner_css_injected', False):
                    display(HTML(
                        '<style>@keyframes fa-spin{0%{transform:rotate(0)}100%{transform:rotate(360deg)}} .fa-spinner{animation:fa-spin 1s linear infinite!important;}</style>'))
                    self._spinner_css_injected = True
            except Exception:
                pass
            # Silent run, suppress underlying print logs
            import contextlib
            import io
            _buf_out, _buf_err = io.StringIO(), io.StringIO()
            try:
                with contextlib.redirect_stdout(_buf_out), contextlib.redirect_stderr(_buf_err):
                    self._on_run_button_clicked(b)
            finally:
                # Restore button state
                run_button.disabled = False
                run_button.description = original_desc
                try:
                    run_button.icon = original_icon
                except Exception:
                    pass
                spinner_widget.value = ''

        run_button.on_click(on_run_click)

        # Add button to button container (removed Close button)
        button_container.children = [run_button, spinner_widget]

        # Add button container to widgets_list
        widgets_list.append(button_container)

        # Set main container children
        main_container.children = widgets_list

        # Update right panel content
        self.widgets['model_detail_area'].children = [main_container]

    def invoke_model(self, model_name):
        """Invoke the interactive interface for specified model."""
        if model_name not in self.model_names:
            raise ValueError(f"Model '{model_name}' does not exist")

        # Load model on demand
        model = self.load_model_on_demand(model_name)
        if model is None:
            raise ValueError(f"Failed to load model '{model_name}'")

        self.current_model = model

        # Import widgets
        widgets = _lazy_import_ipywidgets()

        # Create main container
        main_container = widgets.VBox()
        widgets_list = []

        # Use HBox layout to place model info and question button
        model_info_hbox = widgets.HBox(
            layout=widgets.Layout(
                background='#f8fafc',
                border='1px solid #e2e8f0',
                border_radius='8px',
                padding='10px',
                margin='0 0 10px 0',
                align_items='flex-start'
            )
        )

        # Add model basic info HTML
        model_info = widgets.HTML(
            value=f"""
                <div>
                    <h3 style="margin-top: 0; margin-bottom: 8px;">{self.current_model.name}</h3>
                    <p style="color: #666; margin-bottom: 8px;">{self.current_model.description}</p>
                    <div style="display: flex; gap: 10px;">
                        <div>
                            <span style="color: #666;">Authors' Emails: </span>
                            <span>{self.current_model.author}</span>
                        </div>
                        <div>
                            <span style="color: #666;">Tags: </span>
                            <span>{', '.join(self.current_model.tags)}</span>
                        </div>
                    </div>
                </div>
            """,
            layout=widgets.Layout(flex='1')
        )

        # Create question button - use original color scheme
        qa_toggle_button = widgets.Button(
            description='?',
            tooltip='Toggle QA Assistant',
            layout=widgets.Layout(
                width='28px',
                height='28px',
                margin='0 0 0 10px'
            ),
            style=widgets.ButtonStyle(
                button_color='#f8fafc',
                text_color='#64748b',
                font_weight='bold'
            )
        )

        # Put info and button into HBox
        model_info_hbox.children = [model_info, qa_toggle_button]
        widgets_list.append(model_info_hbox)

        # Iterate through states
        for i, state in enumerate(self.current_model.states):
            state_container = widgets.VBox(
                layout=widgets.Layout(margin='0 0 8px 0')
            )
            state_widgets = []

            # Add state info
            state_info = widgets.HTML(value=f"""
                <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px; margin-bottom: 8px;">
                    <h3 style="color: #1e293b; margin: 0 0 4px 0; font-size: 16px; font-weight: 600;">{state.get('name', '')}</h3>
                    <p style="color: #64748b; margin: 0; font-size: 14px;">{state.get('desc', '')}</p>
                </div>
            """)
            state_widgets.append(state_info)

            # Check if this state has events requiring user input
            has_input_events = False
            for event in state.get('event', []):
                if event.get('eventType') == 'response':
                    has_input_events = True
                    event_container = widgets.VBox(
                        layout=widgets.Layout(margin='3px 0'))
                    event_widgets = []

                    event_name = event.get('eventName', '')
                    optional_text = "Required" if not event.get(
                        'optional', False) else "Optional"
                    event_desc = event.get('eventDesc', '')

                    # Add event title and description
                    event_header = widgets.HTML(value=f"""
                        <div style="margin: 2px 0;">
                            <span style="font-weight: 500;">{event_name}</span>
                            <span style="background: {('#ef4444' if optional_text == 'Required' else '#94a3b8')}; 
                                     color: white; 
                                     padding: 1px 8px; 
                                     border-radius: 12px; 
                                     font-size: 12px; 
                                     margin-left: 8px;">
                                {optional_text}
                            </span>
                            <div style="color: #666; margin: 1px 0 2px 0;">{event_desc}</div>
                        </div>
                    """)
                    event_widgets.append(event_header)

                    # Check if contains nodes type data
                    has_nodes = False
                    nodes_data = []
                    for data_item in event.get('data', []):
                        if 'nodes' in data_item:
                            has_nodes = True
                            nodes_data = data_item['nodes']

                    if has_nodes:
                        # Create table container
                        table_container = widgets.VBox()
                        table_widgets = []

                        # Add table header
                        header = widgets.HTML(value="""
                            <div style="display: grid; grid-template-columns: 1fr 2fr 1fr; gap: 8px; padding: 8px; background: #f8fafc; border: 1px solid #e2e8f0;">
                                <div style="font-weight: 500;">Parameter Name</div>
                                <div style="font-weight: 500;">Description</div>
                                <div style="font-weight: 500;">Value</div>
                            </div>
                        """)
                        table_widgets.append(header)

                        # Create a row for each parameter
                        for node in nodes_data:
                            # Create row container
                            row = widgets.HBox([
                                widgets.HTML(value=f"""
                                    <div style="padding: 8px; min-width: 150px;">{node.get('text', '')}</div>
                                """),
                                widgets.HTML(value=f"""
                                    <div style="padding: 8px; min-width: 200px;">{node.get('desc', '')}</div>
                                """),
                                widgets.Text(
                                    placeholder='Please input value',
                                    layout=widgets.Layout(width='150px')
                                )
                            ])
                            # Store Text widget reference
                            self.widgets[f'node-{event_name}-{node.get("text")}'] = row.children[-1]
                            table_widgets.append(row)

                        table_container.children = table_widgets
                        event_widgets.append(table_container)
                    else:
                        # Create file chooser
                        FileChooser = _lazy_import_filechooser()
                        fc = FileChooser(
                            path='./',
                            layout=widgets.Layout(width='100%')
                        )
                        self.widgets[f'file_chooser_{event_name}'] = fc
                        event_widgets.append(fc)

                    event_container.children = event_widgets
                    state_widgets.append(event_container)

            # If no input events, add prompt info
            if not has_input_events:
                no_input_msg = widgets.HTML(value="""
                    <div style="padding: 8px 12px; 
                                background: #f8fafc; 
                                border: 1px dashed #e2e8f0; 
                                border-radius: 4px; 
                                color: #64748b; 
                                font-size: 14px; 
                                margin: 4px 0;">
                        This state does not require user input
                    </div>
                """)
                state_widgets.append(no_input_msg)

            state_container.children = state_widgets
            widgets_list.append(state_container)

            if i < len(self.current_model.states) - 1:
                divider = widgets.HTML(value="""
                    <div style="padding: 0 16px;">
                        <hr style="border: none; border-top: 2px solid #1e293b; margin: 12px 0;">
                    </div>
                """)
                widgets_list.append(divider)

        # Create output area
        self.widgets['output_area'] = widgets.Output()
        # Add output area to widgets_list
        widgets_list.append(self.widgets['output_area'])

        # Create button container (horizontal layout)
        button_container = widgets.HBox(
            layout=widgets.Layout(
                display='flex',
                justify_content='flex-end',
                gap='10px'
            )
        )

        # Create Run button (disabled during execution)
        run_button = widgets.Button(
            description='Run',
            style=widgets.ButtonStyle(
                button_color='#4CAF50', text_color='white')
        )

        # Running animation (placed to the right of button, hidden by default)
        spinner_widget = widgets.HTML(
            value='', layout=widgets.Layout(margin='0 6px'))
        self.widgets['running_spinner'] = spinner_widget

        def on_run_click(b):
            # Disable button, switch text and icon to running state
            run_button.disabled = True
            original_desc = run_button.description
            original_icon = getattr(run_button, 'icon', '')
            run_button.description = 'Model calculating...'
            # Use fontawesome spinner icon in button and inject rotation CSS
            try:
                run_button.icon = 'spinner'
                display, HTML, _ = _lazy_import_ipython_display()
                if not getattr(self, '_spinner_css_injected', False):
                    display(HTML(
                        '<style>@keyframes fa-spin{0%{transform:rotate(0)}100%{transform:rotate(360deg)}} .fa-spinner{animation:fa-spin 1s linear infinite!important;}</style>'))
                    self._spinner_css_injected = True
            except Exception:
                pass
            # Silent run, suppress underlying print logs
            import contextlib
            import io
            _buf_out, _buf_err = io.StringIO(), io.StringIO()
            try:
                with contextlib.redirect_stdout(_buf_out), contextlib.redirect_stderr(_buf_err):
                    self._on_run_button_clicked(b)
            finally:
                # Restore button state
                run_button.disabled = False
                run_button.description = original_desc
                try:
                    run_button.icon = original_icon
                except Exception:
                    pass
                spinner_widget.value = ''

        run_button.on_click(on_run_click)

        # Add button to button container
        button_container.children = [run_button, spinner_widget]

        # Add button container to widgets_list
        widgets_list.append(button_container)

        # Set main container children
        main_container.children = widgets_list

        # Create horizontal split container
        split_container = widgets.HBox(
            layout=widgets.Layout(
                width='100%',
                display='flex'
            )
        )

        # Create left container (65%)
        left_panel = widgets.VBox(
            layout=widgets.Layout(
                width='60%',
                padding='10px'
            )
        )

        # Create right container (35%)
        right_panel = widgets.VBox(
            layout=widgets.Layout(
                width='40%',
                padding='10px',  # Increase padding
                border_left='1px solid #ccc'
            )
        )

        # Create search box
        search_box = widgets.Text(
            placeholder='Please input your question about this model...',
            description='Search:',
            description_width='50px',
            style={
                'description_width': 'initial',
                'font_family': 'PingFang SC, -apple-system, BlinkMacSystemFont, sans-serif'
            },
            layout=widgets.Layout(
                width='100%',
                margin='8px 0',
                padding='10px 16px',
                border='1px solid #d1d5db',
                border_radius='12px',
                font_size='15px',
                background_color='white',
                transition='all 0.3s ease',
                box_shadow='0 1px 2px rgba(0, 0, 0, 0.05)'
            )
        )
        # Add hover and focus effects
        search_box._dom_classes = ['hover:border-indigo-500',
                                   'focus:ring-2', 'focus:ring-indigo-500', 'focus:border-indigo-500']

        # Create result display area with fixed height and scrollbar
        result_area = widgets.Output(
            layout=widgets.Layout(
                width='100%',
                height='500px',  # Fixed height
                # border='1px solid #ddd',
                padding='5px',
                overflow_y='auto'  # Add vertical scrollbar
            )
        )

        # Save to instance variables
        self.widgets['result_area'] = result_area

        # Bind event handler
        search_box.on_submit(self.on_search_submit)

        # Create title
        title = widgets.HTML(
            value='<h3 style="margin:0 0 2px 0;">Model QA Assistant</h3>'
        )

        # Assemble right panel
        right_panel.children = [
            title,
            search_box,
            result_area
        ]

        # Put original main_container into left panel
        left_panel.children = [main_container]

        # Assemble split container
        split_container.children = [left_panel, right_panel]

        # Define toggle QA Panel function
        qa_panel_visible = [True]  # Initial state is visible

        def toggle_qa_panel(button=None):
            if qa_panel_visible[0]:
                # Hide QA Panel
                split_container.children = [left_panel]
                left_panel.layout.width = '100%'
                qa_panel_visible[0] = False
                # print("QA Panel hidden")  # Debug info
            else:
                # Show QA Panel
                split_container.children = [left_panel, right_panel]
                left_panel.layout.width = '60%'
                qa_panel_visible[0] = True
                # print("QA Panel shown")  # Debug info

        # Directly bind question button click event
        qa_toggle_button.on_click(toggle_qa_panel)

        # Add CSS styles to beautify button
        display, HTML, _ = _lazy_import_ipython_display()
        button_css = HTML("""
            <style>
                /* Beautify question button - use original color scheme */
                .widget-hbox .widget-button .btn {
                    border-radius: 50% !important;
                    border: 1px solid #e2e8f0 !important;
                    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1) !important;
                    transition: all 0.2s ease !important;
                    font-size: 16px !important;
                    font-weight: bold !important;
                    min-width: 28px !important;
                    padding: 0 !important;
                }
                .widget-hbox .widget-button .btn:hover {
                    transform: scale(1.05) !important;
                    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.15) !important;
                    border-color: #cbd5e1 !important;
                    background-color: #ffffff !important;
                }
                .widget-hbox .widget-button .btn:active {
                    transform: scale(0.95) !important;
                }
            </style>
        """)
        display(button_css)

        return split_container

    def show_model(self, model_name):
        """Display interactive interface for specified model (alias for invoke_model, for backward compatibility)."""
        return self.invoke_model(model_name)

    def _on_run_button_clicked(self, b):
        """Handle run button click event."""
        # Import requests module
        requests = _lazy_import_requests()

        # Check if in silent mode
        silent_mode = getattr(self, '_silent_mode', False)

        # Define output context
        if not silent_mode:
            output_context = self.widgets['output_area']
        else:
            # Use empty context manager in silent mode
            import contextlib
            output_context = contextlib.nullcontext()

        with output_context:
            if not silent_mode:
                self.widgets['output_area'].clear_output()

            missing_required_fields = []
            input_files = {}

            for state in self.current_model.states:
                state_name = state.get('name')
                input_files[state_name] = {}

                for event in state.get('event', []):
                    if event.get('eventType') == 'response':
                        event_name = event.get('eventName', '')
                        is_required = not event.get('optional', False)

                        # Check if has nodes data
                        has_nodes = False
                        nodes_data = []
                        for data_item in event.get('data', []):
                            if 'nodes' in data_item:
                                has_nodes = True
                                nodes_data = data_item['nodes']

                        if has_nodes:
                            # Directly collect node parameter values, no XML conversion
                            for node in nodes_data:
                                widget = self.widgets.get(
                                    f'node-{event_name}-{node.get("text")}')
                                if widget:
                                    value = widget.value
                                    if value:
                                        kernel_type = node.get(
                                            'kernelType', 'string')
                                        node_name = node.get("text")

                                        # Convert data type based on kernelType
                                        try:
                                            if kernel_type == 'int':
                                                converted_value = int(value)
                                            elif kernel_type in ['double', 'float']:
                                                converted_value = float(value)
                                            elif kernel_type == 'boolean':
                                                converted_value = str(value).lower() in [
                                                    'true', '1', 'yes']
                                            else:  # string or default
                                                converted_value = str(value)

                                            # Store directly to input_files
                                            input_files[state_name][node_name] = converted_value

                                        except (ValueError, TypeError) as e:
                                            print(
                                                f"❌ Error: Invalid value for {node_name}: {value}")
                                            return
                                    elif is_required:
                                        missing_required_fields.append(
                                            f"'{node.get('text')}'")
                                elif is_required:
                                    missing_required_fields.append(
                                        f"'{node.get('text')}'")
                        else:
                            # Handle file input
                            file_chooser = self.widgets.get(
                                f'file_chooser_{event_name}')
                            if file_chooser:
                                if file_chooser.selected:
                                    input_files[state_name][event_name] = file_chooser.selected
                                elif is_required:
                                    missing_required_fields.append(
                                        f"'{event_name}'")

            if missing_required_fields:
                print(
                    f"❌ Error: The following required fields are missing: {', '.join(missing_required_fields)}")
                return

            # Display progress indicator
            display, HTML, _ = _lazy_import_ipython_display()
            progress_display = None
            if not silent_mode:
                progress_html = """
                <div id="model-progress" style="padding:15px;background:#f0f9ff;border:1px solid #bae6fd;border-radius:8px;margin:10px 0;">
                    <div style="display:flex;align-items:center;gap:10px;">
                        <div class="spinner" style="width:20px;height:20px;border:3px solid #e0e0e0;border-top:3px solid #3b82f6;border-radius:50%;animation:spin 1s linear infinite;"></div>
                        <span style="color:#0369a1;font-weight:500;">🚀 Model is running... This may take a few minutes.</span>
                    </div>
                    <style>@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }</style>
                </div>
                """
                progress_display = display(HTML(progress_html), display_id='model_progress')

            try:
                # Only print debug info in non-silent mode
                if not silent_mode:
                    print("📋 Input parameters:", input_files)

                # Continue executing model
                # Import openModel module
                openModel = _lazy_import_openmodel()
                taskServer = openModel.OGMSAccess(
                    modelName=self.current_model.name,
                    token="6U3O1Sy5696I5ryJFaYCYVjcIV7rhd1MKK0QGX9A7zafogi8xTdvejl6ISUP1lEs"
                )

                # Execute model (no longer silent, let user see progress)
                result = taskServer.createTask(params=input_files)

                # Update progress indicator to success state
                if not silent_mode and progress_display:
                    progress_display.update(HTML('<div style="color:#16a34a;padding:10px;background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;">✅ Model execution completed!</div>'))
                # print(result)

                # Display download links in UI (no auto download to local)
                if not silent_mode:
                    display, HTML, _ = _lazy_import_ipython_display()
                    rows = []
                    for output in result:
                        url = output.get('url')
                        tag = output.get('tag', '')
                        suffix = output.get('suffix', '')
                        statename = output.get('statename', '')
                        event = output.get('event', '')
                        filename = f"{tag}.{suffix}" if tag and suffix else (
                            tag or '')
                        if url:
                            rows.append(f"""
                                <tr>
                                    <td style=\"padding:8px;border-bottom:1px solid #e5e7eb;text-align:left;\">{statename}</td>
                                    <td style=\"padding:8px;border-bottom:1px solid #e5e7eb;text-align:left;\">{event}</td>
                                    <td style=\"padding:8px;border-bottom:1px solid #e5e7eb;text-align:left;\">{filename}</td>
                                    <td style=\"padding:8px;border-bottom:1px solid #e5e7eb;text-align:left;\"><a href=\"{url}\" target=\"_blank\">Download</a></td>
                                </tr>
                            """)

                    # Pre-generate table row HTML to avoid backslash in f-string
                    rows_html = ''.join(
                        rows) if rows else '<tr><td colspan="4" style="padding:8px;color:#64748b;">No outputs</td></tr>'

                    table_html = f"""
                    <div style=\"margin:10px 0;\">
                      <div style=\"font-weight:600;margin-bottom:6px;\">Model outputs</div>
                      <table style=\"width:100%;border-collapse:collapse;font-size:14px;\">
                        <thead>
                          <tr style=\"background:#f8fafc;\">
                            <th style=\"text-align:left;padding:8px;border-bottom:1px solid #e5e7eb;\">State</th>
                            <th style=\"text-align:left;padding:8px;border-bottom:1px solid #e5e7eb;\">Event</th>
                            <th style=\"text-align:left;padding:8px;border-bottom:1px solid #e5e7eb;\">File</th>
                            <th style=\"text-align:left;padding:8px;border-bottom:1px solid #e5e7eb;\">Link</th>
                          </tr>
                        </thead>
                        <tbody>
                          {rows_html}
                        </tbody>
                      </table>
                    </div>
                    """
                    display(HTML(table_html))

            except Exception as e:
                import traceback
                error_traceback = traceback.format_exc()

                # Update progress indicator to error state
                if not silent_mode and progress_display:
                    # Escape HTML special characters
                    safe_traceback = error_traceback.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br>')
                    error_html = f'''
                    <div style="color:#dc2626;padding:15px;background:#fef2f2;border:1px solid #fecaca;border-radius:8px;">
                        <div style="font-weight:600;margin-bottom:10px;">❌ Model run failed: {str(e)}</div>
                        <details style="margin-top:10px;">
                            <summary style="cursor:pointer;color:#991b1b;font-weight:500;">Show error details</summary>
                            <pre style="background:#fee2e2;padding:10px;border-radius:4px;margin-top:8px;font-size:12px;overflow-x:auto;white-space:pre-wrap;">{safe_traceback}</pre>
                        </details>
                    </div>
                    '''
                    progress_display.update(HTML(error_html))

                # Print full error info to console
                print(f"❌ Error: Model run failed - {str(e)}")
                print("Error traceback:")
                print(error_traceback)

    def _upload_to_server(self, xml_content, event_name):
        """Upload XML data to transfer server and get download link."""
        # Import requests module
        requests = _lazy_import_requests()
        from io import StringIO

        try:
            # Server address
            upload_url = 'http://221.224.35.86:38083/data'

            # Use event_name as filename
            filename = f"{event_name}"

            # Create form data
            files = {
                'datafile': (filename, StringIO(xml_content), 'application/xml')
            }
            data = {
                'name': filename  # Use same filename
            }

            # Send POST request
            response = requests.post(upload_url, files=files, data=data)

            # Check response status
            if response.status_code == 200:
                response_data = response.json()
                # Construct download link
                download_url = f"{upload_url}/{response_data['data']['id']}"
                return download_url
            else:
                raise Exception(
                    f"Server returned error status code: {response.status_code}")

        except Exception as e:
            raise Exception(f"Failed to upload data to server: {str(e)}")

    async def _rewrite_user_query(self, original_query: str) -> str:
        """
        Use LLM to rewrite user query based on current model context and user modeling history.
        """
        # Import IPython module
        get_ipython = _lazy_import_ipython()

        # Import OpenAI module
        OpenAI = _lazy_import_openai()

        # Only collect model name and description
        model_info = {
            "name": self.current_model.name,
            "description": self.current_model.description
        }

        # Get Jupyter history context
        ip = get_ipython()
        history_context = ""
        if ip is not None:
            history = []
            for session, line_num, input in ip.history_manager.get_range():
                history.append(input)
            history_context = "\n".join(history[-10:])  # Only take last 10 commands

        # Build context-enhanced prompt
        prompt = f"""
You are a professional geographic modeling system assistant. Your task is to understand user questions about the model and intelligently rewrite them to be more specific and comprehensive, in order to better address the user's actual needs.

### Current Context:
1. User is working with a geographic model named "{model_info['name']}"
2. Model description: {model_info['description']}
3. User's recent Jupyter code history:
```
{history_context}
```

### Original User Query:
"{original_query}"

### Your Task:
1. Analyze the original user query and consider whether it is specific and clear
2. If the user query is too broad or vague, make it more specific and clear based on the context
3. If the user query is about model parameters, ensure the rewritten query includes the parameter's specific role, function, and recommended value ranges
4. If the user query is about the model as a whole, consider expanding the query to include theoretical foundations, application scenarios, and practical examples
5. If the user query is about comparing this model with others, specify the aspects of comparison (such as accuracy, speed, applicable scenarios, etc.)

### Output Format:
Only output the rewritten query without any explanations or prefixes. Return the rewritten query text directly. If the original query is already sufficiently clear and comprehensive, keep it unchanged or make minor adjustments. The rewritten question should be concise and not redundant. Limit the question to within 200 English characters.
"""

        # Call OpenAI API for query rewriting
        cfg = _lazy_import_config()
        openai_api_key, openai_base_url = cfg.get_openai_config()
        client = OpenAI(api_key=openai_api_key, base_url=openai_base_url)
        try:
            response = client.chat.completions.create(
                model="gpt-4.1-nano",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": original_query}
                ],
                temperature=0.3,  # Use lower temperature for more deterministic output
                max_tokens=15000
            )
            rewritten_query = response.choices[0].message.content.strip()
            return rewritten_query
        except Exception as e:
            print(f"Query rewriting error: {str(e)}")
            return original_query  # Return original query if error

    async def _get_search_result(self, query: str) -> str:
        """
        Call academic query service and local knowledge base to get results.
        """
        # Import IPython module
        get_ipython = _lazy_import_ipython()

        # First perform query rewriting
        rewritten_query = await self._rewrite_user_query(query)

        # Get history context
        ip = get_ipython()
        history_context = ""
        if ip is not None:
            history = []
            for session, line_num, input in ip.history_manager.get_range():
                history.append(input)
            history_context = "\n".join(history)

        # Build modeling context
        modeling_context = f"""
                            Current model: {self.current_model.name}
                            Model description: {self.current_model.description}
                            History:
                            {history_context}
                            """

        try:
            # Query two data sources in parallel
            tasks = []

            # Task 1: Query academic paper API
            academic_task = asyncio.create_task(
                self._query_academic_api(rewritten_query))
            tasks.append(academic_task)

            # Task 2: Query local knowledge base
            # Query local model data directly, no external ID needed
            kb_task = asyncio.create_task(
                self._query_knowledge_base(rewritten_query))
            tasks.append(kb_task)

            # Wait for all queries to complete
            results = await asyncio.gather(*tasks)

            # Collect results
            academic_result = results[0] if results else {}
            kb_records = results[1] if len(results) > 1 else []

            # If local knowledge base has results, merge into final results
            if kb_records:
                # Process knowledge base results
                kb_contents = []
                for record in kb_records:
                    segment = record.get("segment", {})
                    kb_contents.append(segment.get("content", ""))

                # Use OpenAI to synthesize final answer
                final_answer = await self._synthesize_final_answer(
                    academic_result.get("answer", ""),
                    kb_contents,
                    rewritten_query
                )

                # Build new result containing local knowledge base
                enhanced_result = {
                    "question": academic_result.get("question", rewritten_query),
                    "answer": final_answer,
                    "paperList": academic_result.get("paperList", []),
                    "knowledgeBase": kb_records
                }

                return enhanced_result
            else:
                # If no knowledge base results, return academic results directly
                return academic_result

        except Exception as e:
            print(f"Error getting search results: {str(e)}")
            return {"answer": "Network error, please try again later", "paperList": []}

    async def _query_academic_api(self, query: str) -> dict:
        """
        Query academic API to get papers and answers.
        """
        # Import academic query service
        AcademicQueryService = _lazy_import_academic_service()

        try:
            service = AcademicQueryService()
            full_query = f"Tell me about {self.current_model.name} model's {query}"
            result = await service.get_academic_question_answer(full_query)
            return result
        except Exception as e:
            print(f"Error querying academic API: {str(e)}")
            return {"answer": "Academic query service temporarily unavailable", "paperList": []}

    async def _synthesize_final_answer(self, academic_answer: str, kb_contents: list, query: str) -> str:
        """
        Use OpenAI to synthesize final answer, integrating academic answers and knowledge base content.
        """
        # Import OpenAI module
        OpenAI = _lazy_import_openai()

        try:
            # Prepare knowledge base content
            kb_content_text = "\n---\n".join(kb_contents)

            # Build prompt
            prompt = f"""
As an expert assistant in the field of geographic modeling, your task is to provide the most comprehensive and accurate answer to the user based on the following two sources of information:

1. Answer from academic papers:
{academic_answer}

2. Content from model knowledge base:
{kb_content_text}

The user's question is: "{query}"

Please analyze the information from these two sources and provide a complete answer that meets the following requirements:
1. Merge key information from both sources while avoiding repetition
2. If there are conflicts between academic sources and knowledge base sources, explain these differences
3. Prioritize citing specific parameter values, configuration suggestions, and usage methods from the knowledge base
4. Organize the answer with a clear structure, using subheadings and lists where necessary
5. If the knowledge base content contains specific model parameters or configuration guidelines, emphasize this practical information

Your answer should satisfy both scientific rigor and practical guidance value. Please provide your answer directly without explaining or summarizing your analysis process.
"""

            # Call OpenAI API
            cfg = _lazy_import_config()
            openai_api_key, openai_base_url = cfg.get_openai_config()
            client = OpenAI(api_key=openai_api_key, base_url=openai_base_url)
            response = client.chat.completions.create(
                model="gpt-4.1-nano",
                messages=[
                    {"role": "system", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1500
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            print(f"Error synthesizing final answer: {str(e)}")
            return f"{academic_answer}\n\n[Note: Knowledge base integration failed]"

    async def _get_knowledge_base_model_id(self, model_name: str) -> str:
        """
        Query MongoDB to get model ID.
        """
        try:
            # Model ID mapping - in production, query from MongoDB
            # Below is sample mapping, replace with actual database query in production
            model_id_mapping = {
                "SWAT_Model": "67eaa67e713cad3b0e31b438",
                # Other model mappings...
            }

            # Find current model ID
            model_id = model_id_mapping.get(model_name)
            if not model_id:
                print(f"Warning: Knowledge base ID not found for model '{model_name}'")
                return None

            return model_id
        except Exception as e:
            print(f"Error getting model knowledge base ID: {str(e)}")
            return None

    async def _query_knowledge_base(self, query: str, top_k: int = 3) -> list:
        """
        Query local model knowledge base (based on computeModel.json).
        """
        try:
            import json
            import os

            # Load local model data
            model_data_path = os.path.join(os.path.dirname(
                __file__), 'data', 'computeModel.json')

            if not os.path.exists(model_data_path):
                return []

            with open(model_data_path, 'r', encoding='utf-8') as f:
                all_models = json.load(f)

            # Get current model info
            current_model_name = self.current_model.name
            if current_model_name not in all_models:
                return []

            model_info = all_models[current_model_name]

            # Build knowledge base content
            kb_contents = []

            # 1. Model description
            if 'description' in model_info:
                kb_contents.append({
                    "type": "model_description",
                    "content": f"Model description: {model_info['description']}",
                    "relevance": 0.9
                })

            # 2. Model tags
            if 'normalTags' in model_info:
                tags = model_info['normalTags']
                kb_contents.append({
                    "type": "model_tags",
                    "content": f"Application domain: {', '.join(tags)}",
                    "relevance": 0.7
                })

            # 3. Parameter information
            if 'mdlJson' in model_info and 'mdl' in model_info['mdlJson']:
                mdl = model_info['mdlJson']['mdl']

                # Extract events and parameter information
                if 'events' in mdl:
                    for event in mdl['events']:
                        event_desc = event.get('eventDesc', '')
                        if event_desc and any(keyword in event_desc.lower() for keyword in query.lower().split()):
                            kb_contents.append({
                                "type": "event_description",
                                "content": f"Operation step: {event_desc}",
                                "relevance": 0.8
                            })

                        # Extract parameter information
                        if 'data' in event:
                            for param in event['data']:
                                param_text = param.get('text', '')
                                param_desc = param.get('desc', '')
                                param_type = param.get('dataType', '')

                                if param_text and any(keyword in param_text.lower() for keyword in query.lower().split()):
                                    kb_contents.append({
                                        "type": "parameter_info",
                                        "content": f"Parameter '{param_text}': {param_desc} (type: {param_type})",
                                        "relevance": 0.9
                                    })

            # 4. Sort by relevance and return top_k results
            kb_contents.sort(key=lambda x: x['relevance'], reverse=True)

            # Convert to format compatible with original structure
            formatted_results = []
            for item in kb_contents[:top_k]:
                formatted_results.append({
                    "segment": {
                        "content": item["content"],
                        "type": item["type"],
                        "relevance": item["relevance"]
                    }
                })

            return formatted_results

        except Exception as e:
            return []

    def on_search_submit(self, widget):
        """Handle search submission"""
        # Import IPython display module
        _lazy_import_ipython_display()

        query = widget.value.strip()
        with self.widgets['result_area']:
            self.widgets['result_area'].clear_output()
            if query:
                # Display loading animation
                loading_html = """
                <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 40px 0;">
                    <div class="loading-spinner"></div>
                    <p style="margin-top: 16px; color: #6b7280; font-size: 14px;">Please wait while we process your request...</p>
                    <style>
                    .loading-spinner {
                        width: 50px;
                        height: 50px;
                        border: 5px solid rgba(79, 70, 229, 0.2);
                        border-radius: 50%;
                        border-top-color: #4f46e5;
                        animation: spin 1s linear infinite;
                    }
                    @keyframes spin {
                        to { transform: rotate(360deg); }
                    }
                    </style>
                </div>
                """
                display(HTML(loading_html))

                # Get current running event loop
                loop = asyncio.get_event_loop()
                try:
                    # Clear previous output, including loading animation
                    self.widgets['result_area'].clear_output(wait=True)

                    # Execute query
                    result = loop.run_until_complete(
                        self._get_search_result(query))
                    if isinstance(result, dict):
                        # Convert answer to markdown format
                        markdown_func, _ = _lazy_import_markdown()
                        answer_html = markdown_func(
                            result['answer'], extensions=['extra'])
                        # Wrap in div for display
                        answer_wrapper = f"""
                        <style>
                            .answer-box {{
                                margin: 0;
                                padding: 0;
                                font-family: 'PingFang SC', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                            }}
                            .answer-box h1 {{
                                font-size: 1.5rem;
                                font-weight: 600;
                                margin: 1.2rem 0 0.8rem 0;
                                border-bottom: 2px solid #dbeafe;
                                padding-bottom: 0.3rem;
                            }}
                            .answer-box h2 {{
                                font-size: 1.3rem;
                                font-weight: 600;
                                margin: 1.1rem 0 0.7rem 0;
                            }}
                            .answer-box h3 {{
                                font-size: 1.15rem;
                                font-weight: 600;
                                margin: 1rem 0 0.6rem 0;
                            }}
                            .answer-box p {{
                                margin: 0.8rem 0;
                                line-height: 1.6;
                                text-align: justify;
                            }}
                            .answer-box ul, .answer-box ol {{
                                margin: 0.8rem 0;
                                padding-left: 1.5rem;
                            }}
                            .answer-box li {{
                                margin: 0.4rem 0;
                                line-height: 1.6;
                            }}
                            .answer-box strong {{
                                font-weight: 600;
                            }}
                            .answer-box code {{
                                background-color: #f1f5f9;
                                color: #ef4444;
                                padding: 0.1rem 0.3rem;
                                border-radius: 0.2rem;
                                font-family: Menlo, Monaco, Consolas, monospace;
                                font-size: 0.9em;
                            }}
                        </style>
                        <div style="background: linear-gradient(to bottom, #ffffff, #f8fafc); border-radius: 0.75rem; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06); margin: 0.5rem 0; overflow: hidden;">
                            <div style="height: 0.3rem; background: linear-gradient(90deg, #3b82f6, #2563eb);"></div>
                            <div class="answer-box" style="padding: 1.25rem; font-size: 15px; line-height: 1.6; color: #374151;">
                                {answer_html}
                            </div>
                        </div>
                        """
                        display(HTML(answer_wrapper))

                        # Create tab HTML content
                        has_kb = 'knowledgeBase' in result and result['knowledgeBase']
                        has_papers = 'paperList' in result and result['paperList']

                        if has_papers:
                            # Only show Related Resources tab
                            tab_buttons = []
                            active_tab = "papers"

                            papers_active = 'active'
                            tab_buttons.append(
                                f"""<button class="tab-button {papers_active}" onclick="switchTab(event, 'papers-content')">Related Resources ({len(result['paperList'])})</button>""")

                            # Build paper content
                            papers_content = ""
                            if has_papers:
                                papers_display = "block"
                                paper_items = []
                                for paper in result['paperList']:
                                    authors = paper.get('authors', [])
                                    if len(authors) > 3:
                                        author_text = f"{authors[0]} et al."
                                    else:
                                        author_text = " · ".join(authors)

                                    markdown_func, _ = _lazy_import_markdown()
                                    title_html = markdown_func(
                                        paper['title'], extensions=['extra'])
                                    display_text_html = markdown_func(
                                        paper.get('display_text', ''), extensions=['extra'])

                                    paper_item = f"""
                                    <div style="margin: 8px 0; padding: 12px; background: white; border: 1px solid #e5e7eb; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                                        <h4 style="margin: 0 0 8px 0; padding: 0; font-size: 14px; font-weight: 600; color: #111827; line-height: 1.4; text-align: justify;">{title_html}</h4>
                                        <p style="margin: 0 0 8px 0; padding: 0; color: #4b5563; font-size: 13px; line-height: 1.5; text-align: justify;">{display_text_html}</p>
                                        <div style="display: flex; gap: 10px; align-items: center; font-size: 11px; color: #6b7280;">
                                            <span style="padding: 2px 8px; background: #f3f4f6; border-radius: 9999px;">{paper.get('year', 'N/A')}</span>
                                            <span>{paper.get('citation_count', 0)} Citations</span>
                                            <span>{author_text}</span>
                                            <span style="color: #9ca3af;">{paper.get('journal', 'N/A')}</span>
                                        </div>
                                    </div>
                                    """
                                    paper_items.append(paper_item)

                                papers_content = f"""<div id="papers-content" class="tab-content" style="display: {papers_display};">{''.join(paper_items)}</div>"""

                            # Combine tabs
                            tab_style = """
                            <style>
                            .tab-container {
                                margin-top: 16px;
                                border-radius: 8px;
                                overflow: hidden;
                                border: 1px solid #e5e7eb;
                            }
                            .tab-buttons {
                                display: flex;
                                background: #f3f4f6;
                                border-bottom: 1px solid #e5e7eb;
                            }
                            .tab-button {
                                padding: 10px 16px;
                                border: none;
                                background: none;
                                cursor: pointer;
                                font-size: 14px;
                                font-weight: 500;
                                color: #6b7280;
                                transition: all 0.2s;
                            }
                            .tab-button:hover {
                                background: rgba(255, 255, 255, 0.5);
                            }
                            .tab-button.active {
                                color: #4f46e5;
                                background: white;
                                border-bottom: 2px solid #4f46e5;
                            }
                            .tab-content {
                                padding: 16px;
                                background: white;
                                max-height: 500px;
                                overflow-y: auto;
                            }
                            </style>
                            """

                            tab_script = """
                            <script>
                            function switchTab(evt, tabName) {
                                var i, tabContent, tabButtons;
                                
                                // Hide all tab content
                                tabContent = document.getElementsByClassName("tab-content");
                                for (i = 0; i < tabContent.length; i++) {
                                    tabContent[i].style.display = "none";
                                }
                                
                                // Remove active state from all buttons
                                tabButtons = document.getElementsByClassName("tab-button");
                                for (i = 0; i < tabButtons.length; i++) {
                                    tabButtons[i].className = tabButtons[i].className.replace(" active", "");
                                }
                                
                                // Show current tab and add active state
                                document.getElementById(tabName).style.display = "block";
                                evt.currentTarget.className += " active";
                            }
                            </script>
                            """

                            tabs_html = f"""
                            {tab_style}
                            <div class="tab-container">
                                <div class="tab-buttons">
                                    {''.join(tab_buttons)}
                                </div>
                                {papers_content}
                            </div>
                            {tab_script}
                            """

                            display(HTML(tabs_html))
                    else:
                        print(result)
                except Exception as e:
                    print(f"Error occurred: {str(e)}")


class NotebookContext:
    """Collects and processes Notebook context information"""

    def __init__(self):
        self.data_context = self._get_data_context()
        self.model_context = self._get_model_context()
        self.history_context = self._get_modeling_history_context()

    def to_dict(self):
        """Convert context information to dictionary format"""
        return {
            "data_context": self.data_context,
            "model_context": self.model_context,
            "history_context": self.history_context
        }

    def _get_data_context(self):
        """Get data repository context information"""
        try:
            # Get IPython shell instance
            get_ipython = _lazy_import_ipython()
            ipython = get_ipython()
            if ipython is None:
                raise RuntimeError(
                    "This function must be run in an IPython environment")

            # Get current working directory
            notebook_dir = os.getcwd()

            # Define directories and file patterns to exclude
            exclude_dirs = {
                '.git',
                '__pycache__',
                '.ipynb_checkpoints',
                'node_modules',
                '.idea',
                '.vscode'
            }

            # Define extensions to exclude
            exclude_extensions = {
                '.pyc',
                '.pyo',
                '.pyd',
                '.so',
                '.git',
                '.DS_Store',
                '.gitignore',
                '.py',
                '.c',
                '.md',
                '.txt'
            }

            # Create data file list
            data_files = []

            # Traverse directory tree
            for root, dirs, files in os.walk(notebook_dir):
                # Filter out unwanted directories
                dirs[:] = [d for d in dirs if d not in exclude_dirs]

                # Filter and process files
                for file in files:
                    # Check file extension
                    _, ext = os.path.splitext(file)
                    if ext not in exclude_extensions and not file.startswith('.'):
                        # Get relative path
                        rel_path = os.path.relpath(
                            os.path.join(root, file), notebook_dir)
                        data_files.append(
                            f"- A {ext[1:]} file named '{file}' located at '{rel_path}'")

            # Build natural language description
            if not data_files:
                context_description = "No relevant data files found in the current directory."
            else:
                context_description = "The following data files are available in the current working directory:\n"
                context_description += "\n".join(data_files)
                context_description += "\n\nThese files might be useful as input data for model operations."

            return context_description

        except Exception as e:
            print(f"Error getting data context: {str(e)}")
            return "Failed to analyze data context due to an error."

    def _get_model_context(self):
        """Get model repository context information"""
        try:
            # Get directory of current file
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # Build JSON file path
            json_path = os.path.join(current_dir, "data", "computeModel.json")

            # Load model configuration file
            with open(json_path, encoding='utf-8') as f:
                models_data = json.load(f)

            # If no model data, return appropriate description
            if not models_data:
                return "No models are currently available in the model repository."

            # Build model description table
            model_descriptions = [
                "The following models are available in the model repository:"]

            for model_name, model_data in models_data.items():
                # Extract information from model data
                mdl_json = model_data.get("mdlJson", {})
                mdl = mdl_json.get("mdl", {})

                description = model_data.get(
                    "description", "No description available")
                author = model_data.get("author", "Unknown")
                tags = model_data.get("normalTags", [])
                states = mdl.get("states", [])

                # Build description for this model
                model_desc = [f"\n- Model: {model_name}"]
                model_desc.append(f"  Description: {description}")
                model_desc.append(f"  Author: {author}")

                if tags:
                    model_desc.append(f"  Tags: {', '.join(tags)}")

                # Collect all input/output events
                all_inputs = []
                all_outputs = []

                for state in states:
                    state_events = state.get("event", [])
                    all_inputs.extend(
                        [e for e in state_events if e.get("eventType") == "response"])
                    all_outputs.extend(
                        [e for e in state_events if e.get("eventType") == "noresponse"])

                # Describe input requirements
                if all_inputs:
                    model_desc.append("  Input Requirements:")
                    for event in all_inputs:
                        event_name = event.get("eventName", "Unnamed input")
                        event_desc = event.get("eventDesc", "No description")
                        event_optional = "Optional" if event.get(
                            "optional", False) else "Required"

                        model_desc.append(
                            f"    - {event_name} ({event_optional})")
                        model_desc.append(f"      Description: {event_desc}")

                # Describe output data
                if all_outputs:
                    model_desc.append("  Generated Outputs:")
                    for event in all_outputs:
                        event_name = event.get("eventName", "Unnamed output")
                        event_desc = event.get("eventDesc", "No description")

                        model_desc.append(f"    - {event_name}")
                        model_desc.append(f"      Description: {event_desc}")

                # Add this model's description to total description
                model_descriptions.extend(model_desc)

            # Add summary statement
            model_descriptions.append(
                "\nThese models can be used for various computational tasks based on their specific purposes and requirements.")
            model_descriptions.append(
                "Each model has specific input requirements and generates corresponding outputs.")

            # Combine all descriptions into a single string
            return "\n".join(model_descriptions)

        except Exception as e:
            print(f"Error getting model context: {str(e)}")
            return "Failed to analyze model repository context due to an error."

    def _get_modeling_history_context(self):
        """Get modeling history context information, including code and Markdown content"""
        try:
            # Get IPython shell instance
            get_ipython = _lazy_import_ipython()
            ipython = get_ipython()
            if ipython is None:
                raise RuntimeError(
                    "This function must be run in an IPython environment")

            # Get current working directory
            current_dir = os.getcwd()

            # Find the latest ipynb file
            notebook_path = None
            latest_time = 0
            for root, dirs, files in os.walk(current_dir):
                for file in files:
                    if file.endswith('.ipynb') and not file.endswith('-checkpoint.ipynb'):
                        file_path = os.path.join(root, file)
                        mod_time = os.path.getmtime(file_path)
                        if mod_time > latest_time:
                            latest_time = mod_time
                            notebook_path = file_path

            # Record all content
            history_desc = []

            # If notebook file found
            if notebook_path:
                try:
                    import nbformat
                    notebook = nbformat.read(notebook_path, as_version=4)

                    for cell in notebook.cells:
                        if cell.cell_type == 'code':
                            if cell.source.strip():  # Skip empty cells
                                history_desc.append(
                                    f"Code Cell:\n{cell.source}")
                        elif cell.cell_type == 'markdown':
                            if cell.source.strip():  # Skip empty cells
                                history_desc.append(
                                    f"Markdown Cell:\n{cell.source}")
                except Exception as e:
                    print(
                        f"Warning: Could not read notebook content: {str(e)}")

            # Get command history
            code_history = list(
                ipython.history_manager.get_range(output=False))
            for session, line_number, code in code_history:
                if code.strip():  # Skip empty lines
                    history_desc.append(f"In [{line_number}]: {code}")

            # Combine all descriptions into a single string
            return "\n\n".join(history_desc)

        except Exception as e:
            print(f"Error getting modeling history: {str(e)}")
            return "Failed to analyze modeling history due to an error."


# Backwards compatibility alias
ModelGUI = GeoModeler
