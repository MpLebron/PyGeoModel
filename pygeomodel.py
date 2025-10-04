import asyncio
import time
import json
import os
import gc
import weakref
import sys
from typing import Dict, List, Optional

# 延迟导入所有可能缺失的模块


def _lazy_import_ipywidgets():
    """延迟导入ipywidgets"""
    global widgets
    if 'widgets' not in globals():
        import ipywidgets as widgets
    return widgets


def _lazy_import_ipython_display():
    """延迟导入IPython display"""
    global display, HTML, clear_output
    if 'display' not in globals():
        from IPython.display import display, HTML, clear_output
    return display, HTML, clear_output


# 基本模块


def _lazy_import_ipython():
    """延迟导入IPython"""
    global get_ipython
    if 'get_ipython' not in globals():
        from IPython import get_ipython
    return get_ipython

# 延迟导入 - 只在需要时导入


def _lazy_import_openmodel():
    """延迟导入openModel模块"""
    global openModel
    if 'openModel' not in globals():
        import ogmsServer2.openModel as openModel
    return openModel


def _lazy_import_requests():
    """延迟导入requests"""
    global requests
    if 'requests' not in globals():
        import requests
    return requests


def _lazy_import_academic_service():
    """延迟导入学术查询服务"""
    global AcademicQueryService
    if 'AcademicQueryService' not in globals():
        from scripts import AcademicQueryService
    return AcademicQueryService


def _lazy_import_openai():
    """延迟导入OpenAI"""
    global OpenAI
    if 'OpenAI' not in globals():
        from openai import OpenAI
    return OpenAI


def _lazy_import_filechooser():
    """延迟导入FileChooser"""
    global FileChooser
    if 'FileChooser' not in globals():
        from ipyfilechooser import FileChooser
    return FileChooser


def _lazy_import_markdown():
    """延迟导入markdown"""
    global markdown, Markdown
    if 'markdown' not in globals():
        from markdown import markdown
        from IPython.display import Markdown
    return markdown, Markdown


def _lazy_import_nest_asyncio():
    """延迟导入nest_asyncio"""
    global nest_asyncio
    if 'nest_asyncio' not in globals():
        import nest_asyncio
    return nest_asyncio


# 在文件开头应用nest_asyncio（如果可用）
try:
    _lazy_import_nest_asyncio().apply()
except ImportError:
    # 如果nest_asyncio不可用，跳过
    pass

# 工具函数


def cleanup_memory():
    """清理内存的工具函数"""
    gc.collect()
    # 清理弱引用 - 使用更安全的方式
    try:
        # 尝试清理弱引用，如果失败则跳过
        if hasattr(weakref, '_weakrefs'):
            for obj in list(weakref._weakrefs):
                if obj() is None:
                    weakref._weakrefs.remove(obj)
    except (AttributeError, RuntimeError):
        # 如果weakref._weakrefs不存在或访问失败，则跳过
        pass


def safe_import(module_name):
    """安全导入模块"""
    try:
        return __import__(module_name)
    except ImportError:
        return None


class Model:
    """模型基类,用于处理模型的基本属性和操作"""

    def __init__(self, model_name, model_data):
        mdl_json = model_data.get("mdlJson", {})
        mdl = mdl_json.get("mdl", {})

        self.id = model_data.get("_id", "")
        self.name = model_name  # 使用键名作为型名称
        self.description = model_data.get("description", "")
        self.author = model_data.get("author", "")
        self.tags = model_data.get("normalTags", [])
        self.tags_en = model_data.get("normalTagsEn", [])

        self.states = mdl.get("states", [])


class GeoModeler:
    """智能地理建模助手,负责模型管理、推荐和交互界面"""

    def __init__(self):
        # 内存管理相关
        self._instances = weakref.WeakSet()  # 跟踪实例
        self._instances.add(self)

        # 模型数据 - 轻量级管理
        self.models = {}  # 存储已加载的模型（按需加载）
        self.model_names = []  # 存储所有模型名称
        self._model_cache = {}  # 模型数据缓存
        self._max_cache_size = 10  # 最大缓存模型数量

        # UI状态
        self.current_model = None
        self.widgets = {}  # 存储界面组件
        self.page_size = 20
        self.current_page = 1
        self.filtered_models = []

        # 上下文数据 - 延迟加载
        self._context_cache = {}
        self._context_cache_timeout = 300  # 5分钟缓存

        # 初始化
        self._load_model_names()

        # 注册清理函数
        import atexit
        atexit.register(self._cleanup)

    def _cleanup(self):
        """清理资源"""
        try:
            # 清理界面组件
            for widget_key in list(self.widgets.keys()):
                if widget_key in self.widgets:
                    widget = self.widgets[widget_key]
                    if hasattr(widget, 'close'):
                        widget.close()
                    del self.widgets[widget_key]

            # 清理模型缓存
            self.models.clear()
            self._model_cache.clear()
            self._context_cache.clear()

            # 清理弱引用
            cleanup_memory()

        except Exception as e:
            print(f"清理过程中出现错误: {e}")

    def __del__(self):
        """析构函数"""
        if hasattr(self, '_instances'):
            self._instances.discard(self)
        self._cleanup()

    def _load_model_names(self):
        """轻量级加载 - 只加载模型名称，不加载完整数据"""
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
        """加载所有模型的完整数据（保留原有方法作为兼容性接口）"""
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
        """按需加载特定模型（带缓存和内存管理）"""
        # 检查是否已加载
        if model_name in self.models:
            return self.models[model_name]

        # 检查缓存
        if model_name in self._model_cache:
            model_data = self._model_cache[model_name]
            self.models[model_name] = Model(model_name, model_data)
            return self.models[model_name]

        if model_name not in self.model_names:
            print(f"Model '{model_name}' not found")
            return None

        # 从文件加载特定模型数据
        current_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(current_dir, "data", "computeModel.json")

        try:
            with open(json_path, encoding='utf-8') as f:
                models_data = json.load(f)
                if model_name in models_data:
                    model_data = models_data[model_name]

                    # 添加到缓存
                    if len(self._model_cache) >= self._max_cache_size:
                        # 移除最旧的缓存项
                        oldest_key = next(iter(self._model_cache))
                        del self._model_cache[oldest_key]

                    self._model_cache[model_name] = model_data
                    self.models[model_name] = Model(model_name, model_data)

                    # 定期清理内存
                    if len(self.models) % 5 == 0:
                        cleanup_memory()

                    return self.models[model_name]
        except Exception as e:
            print(f"Failed to load model '{model_name}': {str(e)}")
            return None

    def show_models(self):
        """显示模型列表界面"""
        widgets = _lazy_import_ipywidgets()
        main_widget = widgets.HBox(layout=widgets.Layout(width='100%'))

        # 创建左侧面板
        left_panel = widgets.VBox(
            layout=widgets.Layout(width='300px', margin='10px'))

        # 创建搜索框
        search_box = widgets.Text(
            placeholder='Search...',
            description='Search:',
            layout=widgets.Layout(width='100%', margin='5px 0')
        )
        search_box.observe(self._on_search, 'value')

        # 创建分页导航容器
        self.widgets['nav_box'] = widgets.HBox(layout=widgets.Layout(
            width='100%',
            margin='5px 0',
            justify_content='space-between'
        ))

        # 创建模型列表容器
        self.widgets['model_list'] = widgets.VBox(
            layout=widgets.Layout(width='100%'))

        # 组装左侧面板
        left_panel.children = [
            search_box,
            self.widgets['nav_box'],
            self.widgets['model_list']
        ]

        # 建右侧模型详情面板
        right_panel = widgets.VBox(
            layout=widgets.Layout(flex='1', margin='10px'))
        self.widgets['model_detail_area'] = right_panel

        main_widget.children = [left_panel, right_panel]

        # 初始显示
        self._update_model_list()

        return main_widget

    def suggest_model(self):
        """显示模型推荐上下文数据（优化内存使用）"""
        # 定期清理内存
        cleanup_memory()

        # 创建 NotebookContext 实例（使用缓存）
        import time
        cache_key = "notebook_context"
        current_time = time.time()

        if (cache_key in self._context_cache and
                current_time - self._context_cache[cache_key]['time'] < self._context_cache_timeout):
            # 使用缓存的上下文
            context_data = self._context_cache[cache_key]['data']
        else:
            # 创建新的上下文并缓存
            notebook_context = NotebookContext()
            context_data = {
                "modeling_history": notebook_context.history_context,
                "data_context": notebook_context.data_context
            }

            # 更新缓存
            self._context_cache[cache_key] = {
                'data': context_data,
                'time': current_time
            }

            # 清理notebook_context对象
            del notebook_context
            cleanup_memory()

        # 显示加载状态
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
            # 调用API获取模型推荐
            requests = _lazy_import_requests()
            import json

            # API配置
            api_url = 'https://api.dify.ai/v1/workflows/run'  # 根据实际URL调整
            api_key = 'app-CuNONc6hSct2ap07nmUgcaw9'

            # 准备请求数据
            payload = {
                "inputs": {
                    "modeling_history": context_data["modeling_history"],
                    "data_context": context_data["data_context"]
                },
                "response_mode": "blocking",  # 使用阻塞模式
                "user": "jupyter_user"  # 用户标识符
            }

            # 设置请求头
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }

            # 发送POST请求
            response = requests.post(api_url, headers=headers, json=payload)

            # 清除加载状态
            loading_display.update(HTML(''))

            # 处理响应
            if response.status_code == 200:
                result = response.json()

                # 根据API响应解析结果 - 纠正解析路径
                if 'data' in result and 'outputs' in result['data']:
                    # 直接获取API返回的对象，这是一个完整的JSON对象，不是文本
                    recommendation_data = result['data']['outputs']

                    # 检查是否直接包含model_recommendation字段
                    if 'model_recommendation' in recommendation_data:
                        model_rec = recommendation_data['model_recommendation']
                        recommended_data = recommendation_data.get(
                            'recommended_data', {})
                    else:
                        # 如果不是直接包含，可能是第二层嵌套的文本，需要解析
                        try:
                            # 尝试解析text字段中的JSON
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

                    # 从model_rec中提取信息
                    model_name = model_rec.get('name', 'Unknown Model')
                    model_desc = model_rec.get('description', 'No Description')
                    key_strengths = model_rec.get('key_strengths', [])
                    rec_reason = model_rec.get('recommendation_reason', '')
                    app_scenario = model_rec.get('application_scenario', '')

                    # 从recommended_data中提取信息
                    local_data = recommended_data.get('local_data', [])
                    kb_data = recommended_data.get('knowledge_base_data', [])

                    if model_name != 'Unknown Model':  # 确保我们至少有模型名称
                        # 构建优美的HTML展示
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

                        # 添加推荐数据部分
                        if local_data or kb_data:
                            html_output += """
                                <div class="model-rec-section" style="grid-column: 1 / -1;">
                                    <div class="model-rec-title">Recommended Data Resources</div>
                                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                            """

                            # 添加本地数据列
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

                            # 添加知识库数据列
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

                            # 关闭数据资源的网格容器
                            html_output += """
                                    </div>
                                </div>
                            """

                        # 关闭容器div
                        html_output += """
                            </div>
                        </div>
                        """

                        # 显示结果
                        display(HTML(html_output))
                    else:
                        # 处理无模型推荐的情况
                        error_msg = "No valid model recommendation information found in API response"
                        self._display_error_message(error_msg)

                        # 显示原始数据以便调试
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
                    # 处理API返回格式不符预期的情况
                    error_msg = "API response data format does not meet expectations"
                    self._display_error_message(error_msg)

                    # 显示原始数据以便调试
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
            # 清除加载状态

            # 显示错误信息
            self._display_error_message(
                f"Model recommendation service call failed: {str(e)}")

        # 不返回任何值，避免在Jupyter中显示不必要的调试信息
        return None

    def _display_error_message(self, message):
        """显示错误信息"""
        from IPython.display import HTML, display
        error_html = f"""
        <div style="background: #fee2e2; border-left: 4px solid #ef4444; padding: 12px 15px; margin: 10px 0; border-radius: 4px; color: #b91c1c;">
            <div style="font-weight: 500; margin-bottom: 5px;">Error</div>
            <div>{message}</div>
        </div>
        """
        display(HTML(error_html))

    def _show_running_spinner(self):
        """在右侧面板顶部显示运行中动画"""
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
        """移除运行中动画（如果环境支持DOM更新，Notebook多次刷新会清除）"""
        # 简单实现：不做任何事，新的输出会覆盖旧内容
        pass

    def _update_model_list(self, filter_text=''):
        """更新模型列表"""
        # 更新过滤后的模型列表（轻量级搜索，只基于模型名称）
        if filter_text.strip() == "":
            # 无搜索条件时显示所有模型
            self.filtered_models = sorted(self.model_names)
        else:
            # 有搜索条件时基于模型名称过滤
            self.filtered_models = [
                model_name for model_name in sorted(self.model_names)
                if filter_text.lower() in model_name.lower()
            ]

        # 重置页码
        self.current_page = 1

        # 更新显示
        self._refresh_display()

    def _refresh_display(self):
        """刷新当前页面显示"""
        # 计算页面信息
        total_models = len(self.filtered_models)
        total_pages = max(
            1, (total_models + self.page_size - 1) // self.page_size)
        start_idx = (self.current_page - 1) * self.page_size
        end_idx = min(start_idx + self.page_size, total_models)

        # 更新导航按钮和页面息
        prev_button = widgets.Button(
            description='Previous',
            disabled=self.current_page == 1,
            layout=widgets.Layout(width='80px'),
            style=widgets.ButtonStyle(button_color='#e2e8f0')  # 添加柔和的背景色
        )
        prev_button.on_click(self._prev_page)

        next_button = widgets.Button(
            description='Next',
            disabled=self.current_page == total_pages,
            layout=widgets.Layout(width='80px'),
            style=widgets.ButtonStyle(button_color='#e2e8f0')  # 添加柔和的背景色
        )
        next_button.on_click(self._next_page)

        page_info = widgets.HTML(
            value=f'<div style="text-align: center;">Page {self.current_page}/{total_pages}</div>'
        )

        self.widgets['nav_box'].children = [
            prev_button, page_info, next_button]

        # 更新模型列表
        model_buttons = []
        for model_name in self.filtered_models[start_idx:end_idx]:
            button = widgets.Button(
                description=model_name,
                layout=widgets.Layout(
                    width='100%',
                    margin='3px 0',  # 增加按钮间距
                    padding='6px 10px'  # 增加按钮内边距
                ),
                style=widgets.ButtonStyle(
                    button_color='white',  # 按钮背景色
                    font_weight='normal'  # 字体粗细
                )
            )
            button.on_click(self._on_model_button_clicked)
            model_buttons.append(button)

        self.widgets['model_list'].children = tuple(model_buttons)

    def _prev_page(self, b):
        """转到上一页"""
        if self.current_page > 1:
            self.current_page -= 1
            self._refresh_display()

    def _next_page(self, b):
        """转到下一页"""
        total_pages = (len(self.filtered_models) +
                       self.page_size - 1) // self.page_size
        if self.current_page < total_pages:
            self.current_page += 1
            self._refresh_display()

    def _on_search(self, change):
        """处理搜索事件"""
        search_text = change['new']
        self._update_model_list(search_text)

    def _on_model_button_clicked(self, button):
        """处理模型按钮点击事件"""
        model_name = button.description
        # print(f"点击了模型: {model_name}")  # 调试信息

        # 在右侧面板显示模型界面
        self._show_model_in_panel(model_name)

    def _show_model_in_panel(self, model_name):
        """在侧面板中显示模型界面"""
        if model_name not in self.model_names:
            print(f"Error: Model '{model_name}' does not exist")
            return

        # 按需加载模型
        model = self.load_model_on_demand(model_name)
        if model is None:
            print(f"Error: Failed to load model '{model_name}'")
            return

        self.current_model = model

        # 创建主容器
        main_container = widgets.VBox()
        widgets_list = []

        # 添加模型基本信息
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

        # 隐藏的触发按钮（纯widgets，用于可靠触发Python回调）
        hidden_trigger_btn = widgets.Button(
            description='',
            layout=widgets.Layout(width='0px', height='0px',
                                  padding='0', margin='0', border='0'),
            style=widgets.ButtonStyle(button_color='#ffffff')
        )
        hidden_trigger_btn._dom_classes = ['qa-hidden-trigger']
        # 放入极小的容器，避免影响布局
        widgets_list.append(widgets.Box(
            [hidden_trigger_btn], layout=widgets.Layout(width='0px', height='0px')))
        # 保存引用，稍后绑定回调
        self.widgets['qa_hidden_btn'] = hidden_trigger_btn

        # 遍历状态
        for i, state in enumerate(self.current_model.states):
            state_container = widgets.VBox(
                layout=widgets.Layout(margin='0 0 8px 0')
            )
            state_widgets = []

            # 添加状态信息
            state_info = widgets.HTML(value=f"""
                <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px; margin-bottom: 8px;">
                    <h3 style="color: #1e293b; margin: 0 0 4px 0; font-size: 16px; font-weight: 600;">{state.get('name', '')}</h3>
                    <p style="color: #64748b; margin: 0; font-size: 14px;">{state.get('desc', '')}</p>
                </div>
            """)
            state_widgets.append(state_info)

            # 检查该状态是否有需要用户输入的事件
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

                    # 添加事件标题和描述
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

                    # 检查是否含nodes数据
                    has_nodes = False
                    nodes_data = []
                    for data_item in event.get('data', []):
                        if 'nodes' in data_item:
                            has_nodes = True
                            nodes_data = data_item['nodes']

                    if has_nodes:
                        # 创建表格容器
                        table_container = widgets.VBox()
                        table_widgets = []

                        # 添加表头
                        header = widgets.HTML(value="""
                            <div style="display: grid; grid-template-columns: 1fr 2fr 1fr; gap: 8px; padding: 8px; background: #f8fafc; border: 1px solid #e2e8f0;">
                                <div style="font-weight: 500;">Parameter Name</div>
                                <div style="font-weight: 500;">Description</div>
                                <div style="font-weight: 500;">Value</div>
                            </div>
                        """)
                        table_widgets.append(header)

                        # 个参数创建一行
                        for node in nodes_data:
                            # 创建行容器
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
                            # 存储Text widget的引用
                            self.widgets[f'node-{event_name}-{node.get("text")}'] = row.children[-1]
                            table_widgets.append(row)

                        table_container.children = table_widgets
                        event_widgets.append(table_container)
                    else:
                        # 创建文件选择器
                        FileChooser = _lazy_import_filechooser()
                        fc = FileChooser(
                            path='./',
                            layout=widgets.Layout(width='100%')
                        )
                        self.widgets[f'file_chooser_{event_name}'] = fc
                        event_widgets.append(fc)

                    event_container.children = event_widgets
                    state_widgets.append(event_container)

            # 如果没有输入事件，添加提示信息
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

        # 创建输出区域
        self.widgets['output_area'] = widgets.Output()
        # 将输出区域添加到widgets_list
        widgets_list.append(self.widgets['output_area'])

        # 创建按钮容器（水平布局，右对齐）
        button_container = widgets.HBox(
            layout=widgets.Layout(
                display='flex',
                justify_content='flex-end',
                gap='10px'
            )
        )

        # 创建Run按钮（运行期间禁用）
        run_button = widgets.Button(
            description='Run',
            style=widgets.ButtonStyle(
                button_color='#4CAF50', text_color='white')
        )

        # 运行中动画（放在按钮右侧，默认隐藏）
        spinner_widget = widgets.HTML(
            value='', layout=widgets.Layout(margin='0 6px'))
        self.widgets['running_spinner'] = spinner_widget

        def on_run_click(b):
            # 禁用按钮，按钮文案与图标切换为运行中
            run_button.disabled = True
            original_desc = run_button.description
            original_icon = getattr(run_button, 'icon', '')
            run_button.description = 'Model calculating...'
            # 在按钮内使用 fontawesome spinner 图标并注入旋转CSS
            try:
                run_button.icon = 'spinner'
                display, HTML, _ = _lazy_import_ipython_display()
                if not getattr(self, '_spinner_css_injected', False):
                    display(HTML(
                        '<style>@keyframes fa-spin{0%{transform:rotate(0)}100%{transform:rotate(360deg)}} .fa-spinner{animation:fa-spin 1s linear infinite!important;}</style>'))
                    self._spinner_css_injected = True
            except Exception:
                pass
            # 静默运行，屏蔽底层print日志
            import contextlib
            import io
            _buf_out, _buf_err = io.StringIO(), io.StringIO()
            try:
                with contextlib.redirect_stdout(_buf_out), contextlib.redirect_stderr(_buf_err):
                    self._on_run_button_clicked(b)
            finally:
                # 恢复按钮状态
                run_button.disabled = False
                run_button.description = original_desc
                try:
                    run_button.icon = original_icon
                except Exception:
                    pass
                spinner_widget.value = ''

        run_button.on_click(on_run_click)

        # 将按钮添加到按钮容器（移除Close按钮）
        button_container.children = [run_button, spinner_widget]

        # 将按钮容器添加到widgets_list
        widgets_list.append(button_container)

        # 设置主容器的子组件
        main_container.children = widgets_list

        # 更新右侧面板的内容
        self.widgets['model_detail_area'].children = [main_container]

    def invoke_model(self, model_name):
        """调用指定模型的交互界面"""
        if model_name not in self.model_names:
            raise ValueError(f"Model '{model_name}' does not exist")

        # 按需加载模型
        model = self.load_model_on_demand(model_name)
        if model is None:
            raise ValueError(f"Failed to load model '{model_name}'")

        self.current_model = model

        # 导入widgets
        widgets = _lazy_import_ipywidgets()

        # 创建主容器
        main_container = widgets.VBox()
        widgets_list = []

        # 使用HBox布局来放置模型信息和问号按钮
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

        # 添加模型基本信息HTML
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

        # 创建问号按钮 - 使用原有配色风格
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

        # 将信息和按钮放入HBox
        model_info_hbox.children = [model_info, qa_toggle_button]
        widgets_list.append(model_info_hbox)

        # 遍历状态
        for i, state in enumerate(self.current_model.states):
            state_container = widgets.VBox(
                layout=widgets.Layout(margin='0 0 8px 0')
            )
            state_widgets = []

            # 添加状态信息
            state_info = widgets.HTML(value=f"""
                <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px; margin-bottom: 8px;">
                    <h3 style="color: #1e293b; margin: 0 0 4px 0; font-size: 16px; font-weight: 600;">{state.get('name', '')}</h3>
                    <p style="color: #64748b; margin: 0; font-size: 14px;">{state.get('desc', '')}</p>
                </div>
            """)
            state_widgets.append(state_info)

            # 检查该状态是否有需要用户输入的事件
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

                    # 添加事件标题和描述
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

                    # 检查是否包含nodes类数据
                    has_nodes = False
                    nodes_data = []
                    for data_item in event.get('data', []):
                        if 'nodes' in data_item:
                            has_nodes = True
                            nodes_data = data_item['nodes']

                    if has_nodes:
                        # 创建表格容器
                        table_container = widgets.VBox()
                        table_widgets = []

                        # 添加表头
                        header = widgets.HTML(value="""
                            <div style="display: grid; grid-template-columns: 1fr 2fr 1fr; gap: 8px; padding: 8px; background: #f8fafc; border: 1px solid #e2e8f0;">
                                <div style="font-weight: 500;">Parameter Name</div>
                                <div style="font-weight: 500;">Description</div>
                                <div style="font-weight: 500;">Value</div>
                            </div>
                        """)
                        table_widgets.append(header)

                        # 为每个参数创建一行
                        for node in nodes_data:
                            # 创建行容器
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
                            # 存储Text widget的引用
                            self.widgets[f'node-{event_name}-{node.get("text")}'] = row.children[-1]
                            table_widgets.append(row)

                        table_container.children = table_widgets
                        event_widgets.append(table_container)
                    else:
                        # 创建文件选择器
                        FileChooser = _lazy_import_filechooser()
                        fc = FileChooser(
                            path='./',
                            layout=widgets.Layout(width='100%')
                        )
                        self.widgets[f'file_chooser_{event_name}'] = fc
                        event_widgets.append(fc)

                    event_container.children = event_widgets
                    state_widgets.append(event_container)

            # 如果没有输入事件，添加提示信息
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

        # 创建输出区域
        self.widgets['output_area'] = widgets.Output()
        # 将输出区域添加到widgets_list
        widgets_list.append(self.widgets['output_area'])

        # 创建按钮容器（水平布局）
        button_container = widgets.HBox(
            layout=widgets.Layout(
                display='flex',
                justify_content='flex-end',
                gap='10px'
            )
        )

        # 创建Run按钮（运行期间禁用）
        run_button = widgets.Button(
            description='Run',
            style=widgets.ButtonStyle(
                button_color='#4CAF50', text_color='white')
        )

        # 运行中动画（放在按钮右侧，默认隐藏）
        spinner_widget = widgets.HTML(
            value='', layout=widgets.Layout(margin='0 6px'))
        self.widgets['running_spinner'] = spinner_widget

        def on_run_click(b):
            # 禁用按钮，按钮文案与图标切换为运行中
            run_button.disabled = True
            original_desc = run_button.description
            original_icon = getattr(run_button, 'icon', '')
            run_button.description = 'Model calculating...'
            # 在按钮内使用 fontawesome spinner 图标并注入旋转CSS
            try:
                run_button.icon = 'spinner'
                display, HTML, _ = _lazy_import_ipython_display()
                if not getattr(self, '_spinner_css_injected', False):
                    display(HTML(
                        '<style>@keyframes fa-spin{0%{transform:rotate(0)}100%{transform:rotate(360deg)}} .fa-spinner{animation:fa-spin 1s linear infinite!important;}</style>'))
                    self._spinner_css_injected = True
            except Exception:
                pass
            # 静默运行，屏蔽底层print日志
            import contextlib
            import io
            _buf_out, _buf_err = io.StringIO(), io.StringIO()
            try:
                with contextlib.redirect_stdout(_buf_out), contextlib.redirect_stderr(_buf_err):
                    self._on_run_button_clicked(b)
            finally:
                # 恢复按钮状态
                run_button.disabled = False
                run_button.description = original_desc
                try:
                    run_button.icon = original_icon
                except Exception:
                    pass
                spinner_widget.value = ''

        run_button.on_click(on_run_click)

        # 将按钮添加到按钮容器
        button_container.children = [run_button, spinner_widget]

        # 将按钮容器添加到widgets_list
        widgets_list.append(button_container)

        # 设置主容器的子组件
        main_container.children = widgets_list

        # 创建水平分栏容器
        split_container = widgets.HBox(
            layout=widgets.Layout(
                width='100%',
                display='flex'
            )
        )

        # 创建左侧容器 (65%)
        left_panel = widgets.VBox(
            layout=widgets.Layout(
                width='60%',
                padding='10px'
            )
        )

        # 创建右侧容器 (35%)
        right_panel = widgets.VBox(
            layout=widgets.Layout(
                width='40%',
                padding='10px',  # 增加内边距
                border_left='1px solid #ccc'
            )
        )

        # 创建搜索框
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
        # 添加悬停和焦点效果
        search_box._dom_classes = ['hover:border-indigo-500',
                                   'focus:ring-2', 'focus:ring-indigo-500', 'focus:border-indigo-500']

        # 创建结果显示区域，添加固定高度和滚动条
        result_area = widgets.Output(
            layout=widgets.Layout(
                width='100%',
                height='500px',  # 固定高度
                # border='1px solid #ddd',
                padding='5px',
                overflow_y='auto'  # 添加垂直滚动条
            )
        )

        # 保存到实例变量中
        self.widgets['result_area'] = result_area

        # 绑定事件处理函数
        search_box.on_submit(self.on_search_submit)

        # 创建标题
        title = widgets.HTML(
            value='<h3 style="margin:0 0 2px 0;">Model QA Assistant</h3>'
        )

        # 组装右侧面板 - 修改这部分代码
        right_panel.children = [
            title,
            search_box,
            result_area
        ]

        # 将原有的main_container放入左侧面板
        left_panel.children = [main_container]

        # 组装分栏容器
        split_container.children = [left_panel, right_panel]

        # 定义切换QA Panel的函数
        qa_panel_visible = [True]  # 初始状态为显示

        def toggle_qa_panel(button=None):
            if qa_panel_visible[0]:
                # 隐藏QA Panel
                split_container.children = [left_panel]
                left_panel.layout.width = '100%'
                qa_panel_visible[0] = False
                # print("QA Panel hidden")  # 调试信息
            else:
                # 显示QA Panel
                split_container.children = [left_panel, right_panel]
                left_panel.layout.width = '60%'
                qa_panel_visible[0] = True
                # print("QA Panel shown")  # 调试信息

        # 直接绑定问号按钮的点击事件
        qa_toggle_button.on_click(toggle_qa_panel)

        # 添加CSS样式来美化按钮
        display, HTML, _ = _lazy_import_ipython_display()
        button_css = HTML("""
            <style>
                /* 美化问号按钮 - 使用原有配色风格 */
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
        """显示指定模型的交互界面（invoke_model的别名，保持向后兼容）"""
        return self.invoke_model(model_name)

    def _on_run_button_clicked(self, b):
        """处理运行按钮点击事件"""
        # 导入requests模块
        requests = _lazy_import_requests()

        # 检查是否为静默模式
        silent_mode = getattr(self, '_silent_mode', False)

        # 定义输出上下文
        if not silent_mode:
            output_context = self.widgets['output_area']
        else:
            # 静默模式下使用空的上下文管理器
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

                        # 检查是否有nodes数据
                        has_nodes = False
                        nodes_data = []
                        for data_item in event.get('data', []):
                            if 'nodes' in data_item:
                                has_nodes = True
                                nodes_data = data_item['nodes']

                        if has_nodes:
                            # 直接收集节点参数值，不转XML
                            for node in nodes_data:
                                widget = self.widgets.get(
                                    f'node-{event_name}-{node.get("text")}')
                                if widget:
                                    value = widget.value
                                    if value:
                                        kernel_type = node.get(
                                            'kernelType', 'string')
                                        node_name = node.get("text")

                                        # 根据kernelType转换数据类型
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

                                            # 直接存储到input_files中
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
                            # 处理文件输入
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

            try:
                # 只在非静默模式下打印调试信息
                if not silent_mode:
                    print(input_files)
                # 继续执行模型
                # 导入openModel模块
                openModel = _lazy_import_openmodel()
                taskServer = openModel.OGMSAccess(
                    modelName=self.current_model.name,
                    token="6U3O1Sy5696I5ryJFaYCYVjcIV7rhd1MKK0QGX9A7zafogi8xTdvejl6ISUP1lEs"
                )
                # 静默运行，不打印控制台日志
                import contextlib
                import io
                _b1, _b2 = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(_b1), contextlib.redirect_stderr(_b2):
                    result = taskServer.createTask(params=input_files)
                # print(result)

                # 在UI中展示结果的下载链接（不自动下载到本地）
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

                    # 预生成表格行HTML，避免在f-string表达式中包含反斜杠
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
                print(f"❌ Error: Model run failed - {str(e)}")

    def _upload_to_server(self, xml_content, event_name):
        """上传XML据到中转服务器并获取下载链接"""
        # 导入requests模块
        requests = _lazy_import_requests()
        from io import StringIO

        try:
            # 务器地址
            upload_url = 'http://221.224.35.86:38083/data'

            # 使用event_name作为文件名
            filename = f"{event_name}"

            # 创建表单数据
            files = {
                'datafile': (filename, StringIO(xml_content), 'application/xml')
            }
            data = {
                'name': filename  # 使用相同的文件名
            }

            # 发送POST请求
            response = requests.post(upload_url, files=files, data=data)

            # 检查响应状态
            if response.status_code == 200:
                response_data = response.json()
                # 构造下载链接
                download_url = f"{upload_url}/{response_data['data']['id']}"
                return download_url
            else:
                raise Exception(
                    f"Server returned error status code: {response.status_code}")

        except Exception as e:
            raise Exception(f"Failed to upload data to server: {str(e)}")

    async def _rewrite_user_query(self, original_query: str) -> str:
        """
        使用LLM对用户查询进行改写，基于当前模型上下文和用户建模历史
        """
        # 导入IPython模块
        get_ipython = _lazy_import_ipython()

        # 导入OpenAI模块
        OpenAI = _lazy_import_openai()

        # 只收集模型名称和描述
        model_info = {
            "name": self.current_model.name,
            "description": self.current_model.description
        }

        # 获取Jupyter历史上下文
        ip = get_ipython()
        history_context = ""
        if ip is not None:
            history = []
            for session, line_num, input in ip.history_manager.get_range():
                history.append(input)
            history_context = "\n".join(history[-10:])  # 只取最近10条指令

        # 构建上下文增强提示
        prompt = f"""
你是一个专业的地理建模系统助手，你的任务是理解用户对模型的问题并进行智能改写，使其更加明确和全面，以便更好地回答用户真正的需求。

### 当前上下文:
1. 用户正在使用名为"{model_info['name']}"的地理模型
2. 模型描述: {model_info['description']}
3. 用户最近的Jupyter代码历史: 
```
{history_context}
```

### 原始用户查询:
"{original_query}"

### 你的任务:
1. 分析用户原始查询，考虑查询是否具体明确
2. 如果用户查询过于宽泛或模糊，请根据上下文将其具体化和明确化
3. 如果用户查询是关于模型参数，请确保改写后的查询包括该参数的具体角色、作用、推荐值范围等内容
4. 如果用户查询是关于模型整体的，请考虑将查询扩展到包含模型的理论基础、应用场景、实际案例等
5. 如果用户查询是关于模型与其他模型比较的，请明确比较的具体方面(如精度、速度、适用场景等)

### 输出格式:
只输出改写后的查询，不要包含任何解释或前缀，直接返回改写后的查询文本。如果原始查询已经足够明确和全面，可以保持不变或进行微调。改写后的问题要短小精炼，不要冗余。问题要限制在200个英文字符以内。
"""

        # 调用OpenAI API进行查询改写
        client = OpenAI(api_key="sk-4bp5a1DcdLSHCiw1401270055f47424b9eA58cAd587266A3",
                        base_url="https://aihubmix.com/v1")
        try:
            response = client.chat.completions.create(
                model="gpt-4.1-nano",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": original_query}
                ],
                temperature=0.3,  # 使用较低温度以获得更确定性的输出
                max_tokens=15000
            )
            rewritten_query = response.choices[0].message.content.strip()
            return rewritten_query
        except Exception as e:
            print(f"查询改写出错: {str(e)}")
            return original_query  # 如果出错，返回原始查询

    async def _get_search_result(self, query: str) -> str:
        """
        调用学术查询服务和自建知识库获取结果
        """
        # 导入IPython模块
        get_ipython = _lazy_import_ipython()

        # 首先进行查询改写
        rewritten_query = await self._rewrite_user_query(query)

        # 获取历史上下文
        ip = get_ipython()
        history_context = ""
        if ip is not None:
            history = []
            for session, line_num, input in ip.history_manager.get_range():
                history.append(input)
            history_context = "\n".join(history)

        # 构建建模上下文
        modeling_context = f"""
                            当前模型: {self.current_model.name}
                            模型描述: {self.current_model.description}
                            历史记录:
                            {history_context}
                            """

        try:
            # 并行查询两个数据源
            tasks = []

            # 任务1: 查询学术论文API
            academic_task = asyncio.create_task(
                self._query_academic_api(rewritten_query))
            tasks.append(academic_task)

            # 任务2: 查询本地知识库
            # 直接查询本地模型数据，不需要外部ID
            kb_task = asyncio.create_task(
                self._query_knowledge_base(rewritten_query))
            tasks.append(kb_task)

            # 等待所有查询完成
            results = await asyncio.gather(*tasks)

            # 收集结果
            academic_result = results[0] if results else {}
            kb_records = results[1] if len(results) > 1 else []

            # 如果自建知识库有结果，合并到最终结果中
            if kb_records:
                # 处理知识库结果
                kb_contents = []
                for record in kb_records:
                    segment = record.get("segment", {})
                    kb_contents.append(segment.get("content", ""))

                # 使用OpenAI合成最终回答
                final_answer = await self._synthesize_final_answer(
                    academic_result.get("answer", ""),
                    kb_contents,
                    rewritten_query
                )

                # 构建包含自建知识库的新结果
                enhanced_result = {
                    "question": academic_result.get("question", rewritten_query),
                    "answer": final_answer,
                    "paperList": academic_result.get("paperList", []),
                    "knowledgeBase": kb_records
                }

                return enhanced_result
            else:
                # 如果没有知识库结果，直接返回学术结果
                return academic_result

        except Exception as e:
            print(f"获取搜索结果时出错: {str(e)}")
            return {"answer": "网络异常请稍后重试", "paperList": []}

    async def _query_academic_api(self, query: str) -> dict:
        """
        查询学术API获取论文和答案
        """
        # 导入学术查询服务
        AcademicQueryService = _lazy_import_academic_service()

        try:
            service = AcademicQueryService()
            full_query = f"Tell me about {self.current_model.name} model's {query}"
            result = await service.get_academic_question_answer(full_query)
            return result
        except Exception as e:
            print(f"查询学术API时出错: {str(e)}")
            return {"answer": "学术查询服务暂时不可用", "paperList": []}

    async def _synthesize_final_answer(self, academic_answer: str, kb_contents: list, query: str) -> str:
        """
        使用OpenAI合成最终答案，整合学术答案和知识库内容
        """
        # 导入OpenAI模块
        OpenAI = _lazy_import_openai()

        try:
            # 准备知识库内容
            kb_content_text = "\n---\n".join(kb_contents)

            # 构建提示
            prompt = f"""
作为地理建模领域的专家助手，你的任务是基于以下两个来源的信息，为用户提供最全面、最准确的回答:

1. 来自学术论文的答案:
{academic_answer}

2. 来自模型知识库的内容:
{kb_content_text}

用户的问题是: "{query}"

请综合分析这两个来源的信息，给出一个完整的回答，满足以下要求:
1. 合并这两个来源的关键信息，避免重复
2. 如果学术来源和知识库来源有冲突，请说明这种差异
3. 优先引用知识库的具体参数值、配置建议和使用方法
4. 以清晰的结构组织回答，必要时使用小标题和列表
5. 如果知识库内容包含具体的模型参数或配置指南，请着重强调这些实用信息

你的回答应当既满足科学严谨性，又具有实操指导价值。请直接给出回答，不需要解释或总结你的分析过程。 
Please output in English.
"""

            # 调用OpenAI API
            client = OpenAI(api_key="sk-4bp5a1DcdLSHCiw1401270055f47424b9eA58cAd587266A3",
                            base_url="https://aihubmix.com/v1")
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
            print(f"合成最终答案时出错: {str(e)}")
            return f"{academic_answer}\n\n[注: 知识库内容集成失败]"

    async def _get_knowledge_base_model_id(self, model_name: str) -> str:
        """
        查询MongoDB获取模型ID
        """
        try:
            # 模型ID映射表 - 实际应用中可以从MongoDB查询
            # 以下是示例映射，实际使用时应替换为真实的数据库查询
            model_id_mapping = {
                "SWAT_Model": "67eaa67e713cad3b0e31b438",
                # 其他模型映射...
            }

            # 查找当前模型ID
            model_id = model_id_mapping.get(model_name)
            if not model_id:
                print(f"警告: 未找到模型 '{model_name}' 的知识库ID")
                return None

            return model_id
        except Exception as e:
            print(f"获取模型知识库ID时出错: {str(e)}")
            return None

    async def _query_knowledge_base(self, query: str, top_k: int = 3) -> list:
        """
        查询本地模型知识库（基于computeModel.json）
        """
        try:
            import json
            import os

            # 加载本地模型数据
            model_data_path = os.path.join(os.path.dirname(
                __file__), 'data', 'computeModel.json')

            if not os.path.exists(model_data_path):
                return []

            with open(model_data_path, 'r', encoding='utf-8') as f:
                all_models = json.load(f)

            # 获取当前模型信息
            current_model_name = self.current_model.name
            if current_model_name not in all_models:
                return []

            model_info = all_models[current_model_name]

            # 构建知识库内容
            kb_contents = []

            # 1. 模型描述
            if 'description' in model_info:
                kb_contents.append({
                    "type": "model_description",
                    "content": f"模型描述: {model_info['description']}",
                    "relevance": 0.9
                })

            # 2. 模型标签
            if 'normalTags' in model_info:
                tags = model_info['normalTags']
                kb_contents.append({
                    "type": "model_tags",
                    "content": f"应用领域: {', '.join(tags)}",
                    "relevance": 0.7
                })

            # 3. 参数信息
            if 'mdlJson' in model_info and 'mdl' in model_info['mdlJson']:
                mdl = model_info['mdlJson']['mdl']

                # 提取事件和参数信息
                if 'events' in mdl:
                    for event in mdl['events']:
                        event_desc = event.get('eventDesc', '')
                        if event_desc and any(keyword in event_desc.lower() for keyword in query.lower().split()):
                            kb_contents.append({
                                "type": "event_description",
                                "content": f"操作步骤: {event_desc}",
                                "relevance": 0.8
                            })

                        # 提取参数信息
                        if 'data' in event:
                            for param in event['data']:
                                param_text = param.get('text', '')
                                param_desc = param.get('desc', '')
                                param_type = param.get('dataType', '')

                                if param_text and any(keyword in param_text.lower() for keyword in query.lower().split()):
                                    kb_contents.append({
                                        "type": "parameter_info",
                                        "content": f"参数 '{param_text}': {param_desc} (类型: {param_type})",
                                        "relevance": 0.9
                                    })

            # 4. 按相关性排序并返回前top_k个结果
            kb_contents.sort(key=lambda x: x['relevance'], reverse=True)

            # 转换为与原来格式兼容的结构
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
        """处理搜索提交"""
        # 导入IPython display模块
        _lazy_import_ipython_display()

        query = widget.value.strip()
        with self.widgets['result_area']:
            self.widgets['result_area'].clear_output()
            if query:
                # 显示加载动画
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

                # 获取当前运行的事件循环
                loop = asyncio.get_event_loop()
                try:
                    # 清除之前的输出，包括加载动画
                    self.widgets['result_area'].clear_output(wait=True)

                    # 执行查询
                    result = loop.run_until_complete(
                        self._get_search_result(query))
                    if isinstance(result, dict):
                        # 将答案转换为markdown格式
                        markdown_func, _ = _lazy_import_markdown()
                        answer_html = markdown_func(
                            result['answer'], extensions=['extra'])
                        # 包装在div中显示
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

                        # 创建选项卡的HTML内容
                        has_kb = 'knowledgeBase' in result and result['knowledgeBase']
                        has_papers = 'paperList' in result and result['paperList']

                        if has_papers:
                            # 只显示Related Resources选项卡
                            tab_buttons = []
                            active_tab = "papers"

                            papers_active = 'active'
                            tab_buttons.append(
                                f"""<button class="tab-button {papers_active}" onclick="switchTab(event, 'papers-content')">Related Resources ({len(result['paperList'])})</button>""")

                            # 构建论文内容
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

                            # 组合选项卡
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
                                
                                // 隐藏所有标签内容
                                tabContent = document.getElementsByClassName("tab-content");
                                for (i = 0; i < tabContent.length; i++) {
                                    tabContent[i].style.display = "none";
                                }
                                
                                // 移除所有按钮的活动状态
                                tabButtons = document.getElementsByClassName("tab-button");
                                for (i = 0; i < tabButtons.length; i++) {
                                    tabButtons[i].className = tabButtons[i].className.replace(" active", "");
                                }
                                
                                // 显示当前标签并添加活动状态
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
                    print(f"发生错误: {str(e)}")


class NotebookContext:
    """用于收集和处理Notebook上下文信息"""

    def __init__(self):
        self.data_context = self._get_data_context()
        self.model_context = self._get_model_context()
        self.history_context = self._get_modeling_history_context()

    def to_dict(self):
        """将上下文信息转换为字典格式"""
        return {
            "data_context": self.data_context,
            "model_context": self.model_context,
            "history_context": self.history_context
        }

    def _get_data_context(self):
        """获取数据仓库上下文信息"""
        try:
            # 获取IPython shell实例
            get_ipython = _lazy_import_ipython()
            ipython = get_ipython()
            if ipython is None:
                raise RuntimeError(
                    "This function must be run in an IPython environment")

            # 获取当前工作录
            notebook_dir = os.getcwd()

            # 定义要排除的目录和文件模式
            exclude_dirs = {
                '.git',
                '__pycache__',
                '.ipynb_checkpoints',
                'node_modules',
                '.idea',
                '.vscode'
            }

            # 定义要排除的扩展名
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

            # 创建数据文件列表
            data_files = []

            # 遍历目录树
            for root, dirs, files in os.walk(notebook_dir):
                # 过滤掉不需要的目录
                dirs[:] = [d for d in dirs if d not in exclude_dirs]

                # 过滤并处理文件
                for file in files:
                    # 检查文件扩展名
                    _, ext = os.path.splitext(file)
                    if ext not in exclude_extensions and not file.startswith('.'):
                        # 获取相对路径
                        rel_path = os.path.relpath(
                            os.path.join(root, file), notebook_dir)
                        data_files.append(
                            f"- A {ext[1:]} file named '{file}' located at '{rel_path}'")

            # 构建自然语描述
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
        """获取模型仓库上下文信息"""
        try:
            # 获取当前文件所在目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # 构建JSON文件路径
            json_path = os.path.join(current_dir, "data", "computeModel.json")

            # 取模型配置文件
            with open(json_path, encoding='utf-8') as f:
                models_data = json.load(f)

            # 如果没有模型数据，返回相应描述
            if not models_data:
                return "No models are currently available in the model repository."

            # 构建模型描述表
            model_descriptions = [
                "The following models are available in the model repository:"]

            for model_name, model_data in models_data.items():
                # 模型数据中提取信息
                mdl_json = model_data.get("mdlJson", {})
                mdl = mdl_json.get("mdl", {})

                description = model_data.get(
                    "description", "No description available")
                author = model_data.get("author", "Unknown")
                tags = model_data.get("normalTags", [])
                states = mdl.get("states", [])

                # 构建该模型的描述
                model_desc = [f"\n- Model: {model_name}"]
                model_desc.append(f"  Description: {description}")
                model_desc.append(f"  Author: {author}")

                if tags:
                    model_desc.append(f"  Tags: {', '.join(tags)}")

                # 收集所有输入输出事件
                all_inputs = []
                all_outputs = []

                for state in states:
                    state_events = state.get("event", [])
                    all_inputs.extend(
                        [e for e in state_events if e.get("eventType") == "response"])
                    all_outputs.extend(
                        [e for e in state_events if e.get("eventType") == "noresponse"])

                # 描述输入需求
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

                # 描述输出数据
                if all_outputs:
                    model_desc.append("  Generated Outputs:")
                    for event in all_outputs:
                        event_name = event.get("eventName", "Unnamed output")
                        event_desc = event.get("eventDesc", "No description")

                        model_desc.append(f"    - {event_name}")
                        model_desc.append(f"      Description: {event_desc}")

                # 将该模型的描述添加到总描述中
                model_descriptions.extend(model_desc)

            # 添加总结性述
            model_descriptions.append(
                "\nThese models can be used for various computational tasks based on their specific purposes and requirements.")
            model_descriptions.append(
                "Each model has specific input requirements and generates corresponding outputs.")

            # 将所有描述组合成一个字符串
            return "\n".join(model_descriptions)

        except Exception as e:
            print(f"Error getting model context: {str(e)}")
            return "Failed to analyze model repository context due to an error."

    def _get_modeling_history_context(self):
        """获取建模历史上下文信息，包括代码和Markdown内容"""
        try:
            # 获取IPython shell实例
            get_ipython = _lazy_import_ipython()
            ipython = get_ipython()
            if ipython is None:
                raise RuntimeError(
                    "This function must be run in an IPython environment")

            # 获取当前工作目录
            current_dir = os.getcwd()

            # 查找最新的ipynb文件
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

            # 记录所有内容
            history_desc = []

            # 如果找到notebook文件
            if notebook_path:
                try:
                    import nbformat
                    notebook = nbformat.read(notebook_path, as_version=4)

                    for cell in notebook.cells:
                        if cell.cell_type == 'code':
                            if cell.source.strip():  # 忽略空单元格
                                history_desc.append(
                                    f"Code Cell:\n{cell.source}")
                        elif cell.cell_type == 'markdown':
                            if cell.source.strip():  # 忽略空单元格
                                history_desc.append(
                                    f"Markdown Cell:\n{cell.source}")
                except Exception as e:
                    print(
                        f"Warning: Could not read notebook content: {str(e)}")

            # 获取命令历史
            code_history = list(
                ipython.history_manager.get_range(output=False))
            for session, line_number, code in code_history:
                if code.strip():  # 忽略空行
                    history_desc.append(f"In [{line_number}]: {code}")

            # 将所有描述组合成一个字符串
            return "\n\n".join(history_desc)

        except Exception as e:
            print(f"Error getting modeling history: {str(e)}")
            return "Failed to analyze modeling history due to an error."


# 向后兼容别名
ModelGUI = GeoModeler
