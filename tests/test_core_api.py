import json
import os
import tempfile
import unittest
from pathlib import Path


class FakeClient:
    def __init__(self):
        self.calls = []

    def create_task(self, model_name, params, wait=True):
        self.calls.append((model_name, params, wait))
        return {
            "task_id": "task-123",
            "status": "completed",
            "outputs": [
                {
                    "statename": "SolarCalculation",
                    "event": "roofSloar",
                    "url": "http://example.com/result.zip",
                    "suffix": "zip",
                    "tag": "roofSloar",
                }
            ],
        }


class CoreApiTests(unittest.TestCase):
    def test_catalog_loading_uses_executable_registry_when_available(self):
        from pygeomodel import GeoModeler

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            catalog_path = tmp_path / "computeModel.json"
            registry_path = tmp_path / "modellist_2070.csv"
            catalog_path.write_text(
                json.dumps(
                    {
                        "Alpha Model": {"md5": "md5-alpha", "_id": "uid-alpha"},
                        "Beta Model": {"md5": "md5-beta", "_id": "uid-beta"},
                        "Gamma Model": {"md5": "md5-gamma", "_id": "uid-gamma"},
                        "Unverified Model": {"md5": "md5-unverified", "_id": "uid-unverified"},
                    }
                ),
                encoding="utf-8",
            )
            registry_path.write_text(
                "\ufeff序号,MD5,名称,介绍,模型UID,模型参数及说明,是否有示例数据（资源）,display_name_en\n"
                "1,md5-alpha,Alpha Registry Name,,different-uid,,,English Alpha Model\n"
                "2,,Beta Registry Name,,uid-beta,,,English Beta Model\n"
                "3,,Gamma Model,,,,,English Gamma Model\n",
                encoding="utf-8",
            )

            modeler = GeoModeler(data_path=catalog_path)

        self.assertEqual(
            set(modeler.model_names),
            {"Alpha Model", "Beta Model", "Gamma Model"},
        )

        alpha = modeler.get_model("Alpha Model")
        self.assertEqual(alpha.display_name, "English Alpha Model")
        self.assertEqual(alpha.name, "Alpha Model")
        search_results = modeler.search_models("English Alpha", limit=5)
        self.assertEqual(search_results[0].name, "Alpha Model")
        self.assertEqual(search_results[0].display_name, "English Alpha Model")
        self.assertEqual(
            [summary.name for summary in modeler.search_models("", limit=3)],
            ["Gamma Model", "Beta Model", "Alpha Model"],
        )

    def test_catalog_loading_applies_english_parameter_descriptions(self):
        from pygeomodel import GeoModeler

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            catalog_path = tmp_path / "computeModel.json"
            registry_path = tmp_path / "modellist_2070.csv"
            translations_path = tmp_path / "description_translations_en.json"
            catalog_path.write_text(
                json.dumps(
                    {
                        "BES算法": {
                            "md5": "md5-bes",
                            "_id": "uid-bes",
                            "description": "BES",
                            "mdlJson": {
                                "mdl": {
                                    "states": [
                                        {
                                            "name": "LOADDATA",
                                            "event": [
                                                {
                                                    "eventType": "response",
                                                    "eventName": "T4",
                                                    "eventDesc": "通道4的卫星亮度",
                                                    "optional": False,
                                                    "data": [{"dataType": "REAL"}],
                                                }
                                            ],
                                        }
                                    ]
                                }
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )
            registry_path.write_text(
                "\ufeff序号,MD5,名称,介绍,模型UID,模型参数及说明,是否有示例数据（资源）,display_name_en\n"
                "1,md5-bes,BES算法,,uid-bes,,,BES Land Surface Temperature Algorithm\n",
                encoding="utf-8",
            )
            translations_path.write_text(
                json.dumps({"通道4的卫星亮度": "Satellite Brightness of Channel 4"}),
                encoding="utf-8",
            )

            model = GeoModeler(data_path=catalog_path).get_model("BES算法")

        self.assertEqual(model.display_name, "BES Land Surface Temperature Algorithm")
        self.assertEqual(model.inputs[0].description, "Satellite Brightness of Channel 4")

    def test_search_and_get_model_parse_metadata(self):
        from pygeomodel import GeoModeler, ModelService

        modeler = GeoModeler()
        results = modeler.search_models("photovoltaic", limit=5)

        self.assertTrue(results)
        self.assertTrue(any("Photovoltaic" in item.name for item in results))

        model = modeler.get_model(
            "Roof Photovoltaic Carbon Emission Reduction Potential Assessment Model"
        )
        self.assertIsInstance(model, ModelService)
        self.assertEqual(model.name, "Roof Photovoltaic Carbon Emission Reduction Potential Assessment Model")
        self.assertTrue(model.inputs)
        self.assertTrue(model.outputs)
        self.assertTrue(any(item.name == "system_efficiency" for item in model.inputs))
        self.assertTrue(any(item.name == "roof_vector_path" for item in model.inputs))

    def test_optional_and_datatype_are_normalized_from_metadata(self):
        from pygeomodel import GeoModeler
        from pygeomodel.models import normalize_optional

        model = GeoModeler().get_model(
            "Roof Photovoltaic Carbon Emission Reduction Potential Assessment Model"
        )
        system_efficiency = next(item for item in model.inputs if item.name == "system_efficiency")
        roof_vector = next(item for item in model.inputs if item.name == "roof_vector_path")

        self.assertTrue(system_efficiency.required)
        self.assertEqual(system_efficiency.data_type, "REAL")
        self.assertFalse(system_efficiency.is_file)
        self.assertTrue(roof_vector.is_file)
        self.assertTrue(normalize_optional("true"))
        self.assertTrue(normalize_optional("True"))
        self.assertFalse(normalize_optional("false"))
        self.assertFalse(normalize_optional(False))

    def test_model_invocation_normalizes_flat_params_and_returns_record(self):
        from pygeomodel import GeoModeler, TaskResult

        with tempfile.TemporaryDirectory() as tmpdir:
            roof_file = Path(tmpdir) / "rooftops.zip"
            roof_file.write_bytes(b"fake-data")

            client = FakeClient()
            modeler = GeoModeler(client=client)
            result = modeler.invoke(
                "Roof Photovoltaic Carbon Emission Reduction Potential Assessment Model",
                params={
                    "system_efficiency": 0.8,
                    "start_time": 201801,
                    "end_time": 201812,
                    "roof_vector_path": str(roof_file),
                },
            )

        self.assertIsInstance(result, TaskResult)
        self.assertEqual(result.task_id, "task-123")
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.outputs[0]["event"], "roofSloar")
        self.assertEqual(len(client.calls), 1)

        _, normalized, wait = client.calls[0]
        self.assertTrue(wait)
        self.assertEqual(normalized["SpatialAnalysis"]["system_efficiency"], 0.8)
        self.assertEqual(normalized["SpatialAnalysis"]["start_time"], 201801)
        self.assertEqual(normalized["SpatialAnalysis"]["end_time"], 201812)
        self.assertTrue(normalized["SolarCalculation"]["roof_vector_path"].endswith("rooftops.zip"))

    def test_model_invocation_records_downloaded_output_paths(self):
        import pygeomodel.client as client_module
        from pygeomodel import GeoModeler

        original_downloader = client_module.download_output_files
        try:
            client_module.download_output_files = lambda outputs, output_dir: [
                str(Path(output_dir) / "SolarCalculation-roofSloar.zip")
            ]

            with tempfile.TemporaryDirectory() as tmpdir:
                modeler = GeoModeler(client=FakeClient())
                result = modeler.invoke(
                    "Roof Photovoltaic Carbon Emission Reduction Potential Assessment Model",
                    params={
                        "system_efficiency": 0.8,
                        "start_time": 201801,
                        "end_time": 201812,
                        "roof_vector_path": str(Path(tmpdir) / "rooftops.zip"),
                    },
                    output_dir=Path(tmpdir) / "outputs",
                )
        finally:
            client_module.download_output_files = original_downloader

        self.assertEqual(
            result.downloaded_outputs,
            [str(Path(tmpdir) / "outputs" / "SolarCalculation-roofSloar.zip")],
        )

    def test_download_rewrites_internal_data_node_urls_to_public_gateway(self):
        import pygeomodel.client as client_module

        requested_urls = []

        class FakeResponse:
            content = b"downloaded-output"

            def raise_for_status(self):
                return None

        original_get = client_module.requests.get
        try:
            def fake_get(url, timeout):
                requested_urls.append(url)
                self.assertEqual(timeout, 120)
                return FakeResponse()

            client_module.requests.get = fake_get
            with tempfile.TemporaryDirectory() as tmpdir:
                returned = client_module.download_output_files(
                    [
                        {
                            "url": "http://221.224.35.86:38083/data/687d91a4-f205-4659-ae9d-dd2aed896f8c?pwd=",
                            "tag": "SolarCalculation-roofSloar",
                            "suffix": "zip",
                        }
                    ],
                    tmpdir,
                )
                self.assertEqual(Path(returned[0]).read_bytes(), b"downloaded-output")
        finally:
            client_module.requests.get = original_get

        self.assertEqual(
            requested_urls,
            [
                "https://geomodeling.njnu.edu.cn/dataTransferServer/data/687d91a4-f205-4659-ae9d-dd2aed896f8c?pwd="
            ],
        )

    def test_model_invocation_preserves_multi_child_internal_params(self):
        from pygeomodel import GeoModeler

        model = GeoModeler().get_model("建筑期间河流沉积量Qs")
        normalized = model.normalize_params({"R": "1", "Qe": "1", "Ac": "1", "A": "1", "q": "1"})

        self.assertEqual(
            normalized["LOADDATA"]["inputdata"],
            {
                "children": [
                    {"R": 1.0},
                    {"Qe": 1.0},
                    {"Ac": 1.0},
                    {"A": 1.0},
                    {"q": 1.0},
                ]
            },
        )

    def test_model_invocation_reports_missing_multi_child_params(self):
        from pygeomodel import GeoModeler

        model = GeoModeler().get_model("建筑期间河流沉积量Qs")

        with self.assertRaisesRegex(ValueError, "Qe"):
            model.normalize_params({"R": "1"})

    def test_opengms_xml_builder_supports_multiple_child_values(self):
        from ogmsServer2.openModel import OGMSTask

        task = object.__new__(OGMSTask)
        xml = task._create_children_xml([{"R": 1.0}, {"Qe": 1.0}, {"Ac": 1.0}])

        self.assertIn('name="R"', xml)
        self.assertIn('value="1.0"', xml)
        self.assertIn('name="Qe"', xml)
        self.assertIn('name="Ac"', xml)

    def test_opengms_xml_builder_uses_declared_child_kernel_types(self):
        from ogmsServer2.openModel import OGMSTask

        task = object.__new__(OGMSTask)
        xml = task._create_children_xml(
            [{"ea": 3.0}, {"Mm": 2.0}],
            child_types={"ea": "FLOAT", "Mm": "FLOAT"},
        )

        self.assertIn('name="ea"', xml)
        self.assertIn('kernelType="float"', xml)
        self.assertIn('name="Mm"', xml)

    def test_upload_data_builds_internal_xml_with_mdl_child_types(self):
        from ogmsServer2.openModel import OGMSTask

        task = object.__new__(OGMSTask)
        task.origin_lists = {
            "inputs": [
                {
                    "statename": "LOADDATA",
                    "event": "inputdata",
                    "children": [
                        {"eventName": "ea", "eventType": "FLOAT"},
                        {"eventName": "Mm", "eventType": "FLOAT"},
                    ],
                }
            ]
        }
        captured = {}

        def fake_upload(xml_content, filename):
            captured["xml"] = xml_content
            captured["filename"] = filename
            return "http://example.test/inputdata.xml"

        task._upload_xml_string = fake_upload
        uploaded = task._uploadData(
            {"LOADDATA": {"inputdata": {"children": [{"ea": 3.0}, {"Mm": 2.0}]}}}
        )

        self.assertEqual(uploaded["LOADDATA"]["inputdata"]["url"], "http://example.test/inputdata.xml")
        self.assertEqual(captured["filename"], "inputdata.xml")
        self.assertIn('name="ea" kernelType="float" value="3.0"', captured["xml"])
        self.assertIn('name="Mm" kernelType="float" value="2.0"', captured["xml"])

    def test_mdl_parser_reads_uppercase_udxnode_children(self):
        from ogmsServer2.openUtils.mdlUtils import MDL

        mdl_data = {
            "id": "model-id",
            "md5": "model-md5",
            "mdlJson": {
                "ModelClass": [
                    {
                        "Behavior": [
                            {
                                "RelatedDatasets": [
                                    {
                                        "DatasetItem": [
                                            {
                                                "name": "inputdata",
                                                "type": "internal",
                                                "UdxDeclaration": [
                                                    {
                                                        "UDXNode": [
                                                            {
                                                                "UDXNode": [
                                                                    {
                                                                        "name": "R",
                                                                        "type": "DTKT_REAL",
                                                                        "description": "rate",
                                                                    },
                                                                    {
                                                                        "name": "Qe",
                                                                        "type": "DTKT_REAL",
                                                                        "description": "erosion",
                                                                    },
                                                                ]
                                                            }
                                                        ]
                                                    }
                                                ],
                                            }
                                        ]
                                    }
                                ],
                                "StateGroup": [
                                    {
                                        "States": [
                                            {
                                                "State": [
                                                    {
                                                        "name": "LOADDATA",
                                                        "Event": [
                                                            {
                                                                "name": "inputdata",
                                                                "optional": "False",
                                                                "type": "response",
                                                                "ResponseParameter": [
                                                                    {"datasetReference": "inputdata"}
                                                                ],
                                                            }
                                                        ],
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                ],
                            }
                        ]
                    }
                ]
            },
        }

        parsed = MDL().resolvingMDL(mdl_data)

        self.assertEqual(
            parsed["inputs"][0]["children"],
            [
                {
                    "eventId": "R",
                    "eventName": "R",
                    "eventDesc": "rate",
                    "eventType": "FLOAT",
                    "child": "true",
                    "value": "",
                },
                {
                    "eventId": "Qe",
                    "eventName": "Qe",
                    "eventDesc": "erosion",
                    "eventType": "FLOAT",
                    "child": "true",
                    "value": "",
                },
            ],
        )

    def test_result_objects_serialize_to_json(self):
        from pygeomodel import QAResult, RecommendationResult, TaskResult

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            task = TaskResult(model_name="m", status="completed", outputs=[{"url": "u"}])
            task_path = task.to_json(tmpdir / "task.json")
            self.assertEqual(json.loads(Path(task_path).read_text())["model_name"], "m")

            recommendation = RecommendationResult(
                primary_model={"name": "m"},
                candidates=[{"name": "a"}],
                recommended_data={"local_data": []},
                context={"modeling_history": "h"},
            )
            rec_path = recommendation.to_json(tmpdir / "rec.json")
            self.assertEqual(json.loads(Path(rec_path).read_text())["primary_model"]["name"], "m")

            qa = QAResult(question="q", answer="a", model_name="m", sources=[{"type": "metadata"}])
            qa_path = qa.to_json(tmpdir / "qa.json")
            self.assertEqual(json.loads(Path(qa_path).read_text())["answer"], "a")

    def test_task_result_save_records_metadata_and_outputs(self):
        import pygeomodel.client as client_module
        from pygeomodel import TaskResult

        original_downloader = client_module.download_output_files
        try:
            client_module.download_output_files = lambda outputs, output_dir: [
                str(Path(output_dir) / "SolarCalculation-roofSloar.zip")
            ]

            with tempfile.TemporaryDirectory() as tmpdir:
                tmpdir = Path(tmpdir)
                result = TaskResult(
                    model_name="m",
                    status="completed",
                    task_id="task-123",
                    outputs=[{"url": "http://example.test/result.zip", "tag": "roofSloar", "suffix": "zip"}],
                    params={"system_efficiency": 0.8},
                )

                returned = result.save(
                    output_dir=tmpdir / "outputs",
                    record_path=tmpdir / "records" / "execution_record.json",
                )
                record = json.loads((tmpdir / "records" / "execution_record.json").read_text())
        finally:
            client_module.download_output_files = original_downloader

        self.assertEqual(returned, [str(tmpdir / "outputs" / "SolarCalculation-roofSloar.zip")])
        self.assertEqual(
            result.downloaded_outputs,
            [str(tmpdir / "outputs" / "SolarCalculation-roofSloar.zip")],
        )
        self.assertEqual(record["task_id"], "task-123")
        self.assertEqual(record["record_path"], str(tmpdir / "records" / "execution_record.json"))
        self.assertEqual(record["downloaded_outputs"], result.downloaded_outputs)

    def test_task_result_save_only_outputs_when_no_record_path_is_given(self):
        import pygeomodel.client as client_module
        from pygeomodel import TaskResult

        original_downloader = client_module.download_output_files
        try:
            client_module.download_output_files = lambda outputs, output_dir: [
                str(Path(output_dir) / "SolarCalculation-roofSloar.zip")
            ]

            with tempfile.TemporaryDirectory() as tmpdir:
                tmpdir = Path(tmpdir)
                result = TaskResult(
                    model_name="m",
                    status="completed",
                    task_id="task-123",
                    outputs=[{"url": "http://example.test/result.zip", "tag": "roofSloar", "suffix": "zip"}],
                )

                returned = result.save(output_dir=tmpdir / "outputs")
                implicit_record = tmpdir / "outputs" / "execution_record.json"
        finally:
            client_module.download_output_files = original_downloader

        self.assertEqual(returned, [str(tmpdir / "outputs" / "SolarCalculation-roofSloar.zip")])
        self.assertEqual(
            result.downloaded_outputs,
            [str(tmpdir / "outputs" / "SolarCalculation-roofSloar.zip")],
        )
        self.assertIsNone(result.record_path)
        self.assertFalse(implicit_record.exists())

    def test_task_result_has_notebook_rich_display(self):
        from pygeomodel import TaskResult

        result = TaskResult(
            model_name="Roof Photovoltaic Carbon Emission Reduction Potential Assessment Model",
            status="completed",
            task_id="task-123",
            outputs=[
                {
                    "statename": "SolarCalculation",
                    "event": "roofSloar",
                    "tag": "SolarCalculation-roofSloar",
                    "suffix": "",
                    "url": "",
                }
            ],
            params={
                "system_efficiency": 0.8,
                "start_time": 201801,
                "end_time": 201812,
                "roof_vector_path": "data/xuanwu_rooftop.zip",
            },
            record_path="records/execution_record.json",
            execution_time=103.39,
        )

        html = result._repr_html_()

        self.assertIn("Model Execution Summary", html)
        self.assertIn("completed", html)
        self.assertIn("task-123", html)
        self.assertIn("records/execution_record.json", html)
        self.assertIn("Input parameters", html)
        self.assertIn("roof_vector_path", html)
        self.assertIn("Output resources", html)
        self.assertIn("No downloadable URL returned", html)
        self.assertNotIn("TaskResult(", html)

    def test_opengms_config_uses_public_demo_token_as_fallback(self):
        import pygeomodel.config as config_module

        original_loader = config_module._load_local_api_keys
        original_env = os.environ.get("OGMS_TOKEN")
        try:
            config_module._load_local_api_keys = lambda: {}
            os.environ.pop("OGMS_TOKEN", None)
            self.assertEqual(
                config_module.get_opengms_config().token,
                config_module.PUBLIC_DEMO_OGMS_TOKEN,
            )

            config_module._load_local_api_keys = lambda: {"opengms": {"token": "local-token"}}
            self.assertEqual(config_module.get_opengms_config().token, "local-token")

            os.environ["OGMS_TOKEN"] = "env-token"
            self.assertEqual(config_module.get_opengms_config().token, "env-token")
        finally:
            config_module._load_local_api_keys = original_loader
            if original_env is None:
                os.environ.pop("OGMS_TOKEN", None)
            else:
                os.environ["OGMS_TOKEN"] = original_env

    def test_llm_config_uses_public_demo_credentials_as_fallback(self):
        import pygeomodel.config as config_module

        env_keys = [
            "DIFY_API_KEY",
            "DIFY_BASE_URL",
            "OPENAI_API_KEY",
            "OPENAI_BASE_URL",
            "OPENAI_MODEL",
            "PYGEOMODEL_DIFY_API_KEY",
            "PYGEOMODEL_DIFY_BASE_URL",
            "PYGEOMODEL_OPENAI_API_KEY",
            "PYGEOMODEL_OPENAI_BASE_URL",
            "PYGEOMODEL_OPENAI_MODEL",
        ]
        original_env = {key: os.environ.get(key) for key in env_keys}
        original_loader = config_module._load_local_api_keys
        try:
            config_module._load_local_api_keys = lambda: {}
            for key in env_keys:
                os.environ.pop(key, None)

            cfg = config_module.get_llm_config()
            self.assertEqual(cfg.dify_api_key, config_module.PUBLIC_DEMO_DIFY_API_KEY)
            self.assertEqual(cfg.dify_base_url, config_module.PUBLIC_DEMO_DIFY_BASE_URL)
            self.assertEqual(cfg.openai_api_key, config_module.PUBLIC_DEMO_OPENAI_API_KEY)
            self.assertEqual(cfg.openai_base_url, config_module.PUBLIC_DEMO_OPENAI_BASE_URL)
            self.assertEqual(cfg.openai_model, config_module.PUBLIC_DEMO_OPENAI_MODEL)

            config_module._load_local_api_keys = lambda: {
                "dify": {"api_key": "local-dify", "base_url": "https://local-dify.example/v1"},
                "openai": {
                    "api_key": "local-openai",
                    "base_url": "https://local-openai.example/v1",
                    "model": "local-model",
                },
            }
            cfg = config_module.get_llm_config()
            self.assertEqual(cfg.dify_api_key, "local-dify")
            self.assertEqual(cfg.openai_api_key, "local-openai")
            self.assertEqual(cfg.openai_model, "local-model")

            os.environ["DIFY_API_KEY"] = "generic-env-dify"
            os.environ["OPENAI_API_KEY"] = "generic-env-openai"
            os.environ["OPENAI_MODEL"] = "generic-env-model"
            cfg = config_module.get_llm_config()
            self.assertEqual(cfg.dify_api_key, "local-dify")
            self.assertEqual(cfg.openai_api_key, "local-openai")
            self.assertEqual(cfg.openai_model, "local-model")

            os.environ["PYGEOMODEL_DIFY_API_KEY"] = "pygeomodel-env-dify"
            os.environ["PYGEOMODEL_OPENAI_API_KEY"] = "pygeomodel-env-openai"
            os.environ["PYGEOMODEL_OPENAI_MODEL"] = "pygeomodel-env-model"
            cfg = config_module.get_llm_config()
            self.assertEqual(cfg.dify_api_key, "pygeomodel-env-dify")
            self.assertEqual(cfg.openai_api_key, "pygeomodel-env-openai")
            self.assertEqual(cfg.openai_model, "pygeomodel-env-model")
        finally:
            config_module._load_local_api_keys = original_loader
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_recommendation_result_has_notebook_rich_display(self):
        from pygeomodel import RecommendationResult

        result = RecommendationResult(
            primary_model={
                "name": "Solar Potential Analysis Model",
                "description": "Assesses rooftop photovoltaic potential.",
                "key_strengths": ["Matches rooftop data"],
                "recommendation_reason": "It is directly relevant to rooftop PV assessment.",
                "application_scenario": "Annual PV potential assessment.",
            },
            candidates=[
                {
                    "rank": 1,
                    "name": "Solar Potential Analysis Model",
                    "reason": "Directly matches the task.",
                    "brief_input_data_desc": "Rooftop polygon data.",
                    "is_primary": True,
                },
                {
                    "rank": 2,
                    "name": "Rooftop Suitability Model",
                    "reason": "Related rooftop assessment candidate.",
                    "is_primary": False,
                },
            ],
            recommended_data={
                "local_data": [{"name": "rooftops.geojson", "location": "data/rooftops.geojson"}],
                "knowledge_base_data": [{"name": "Solar radiation data", "url": "https://example.org/solar"}],
            },
        )

        html = result._repr_html_()

        self.assertIn("&#9733; Rank 1", html)
        self.assertNotIn("Recommended</span>", html)
        self.assertIn("Solar Potential Analysis Model", html)
        self.assertIn("Rooftop Suitability Model", html)
        self.assertIn("Relevant Data", html)
        self.assertIn("https://example.org/solar", html)
        self.assertNotIn("Recommendation Reason", html)
        self.assertNotIn("Key Strengths", html)

    def test_suggest_model_requires_configured_dify_workflow(self):
        import pygeomodel.modeler as modeler_module
        from pygeomodel import GeoModeler
        from pygeomodel.config import LLMConfig

        original_get_llm_config = modeler_module.get_llm_config
        try:
            modeler_module.get_llm_config = lambda: LLMConfig(dify_api_key=None)
            with self.assertRaisesRegex(RuntimeError, "DIFY_API_KEY"):
                GeoModeler(client=FakeClient()).suggest_model()
        finally:
            modeler_module.get_llm_config = original_get_llm_config

    def test_suggest_model_calls_dify_workflow_and_returns_record(self):
        import pygeomodel.modeler as modeler_module
        from pygeomodel import GeoModeler, RecommendationResult
        from pygeomodel.config import LLMConfig

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "data": {
                        "outputs": {
                            "text": json.dumps(
                                {
                                    "model_recommendation": {
                                        "name": "Roof Photovoltaic Carbon Emission Reduction Potential Assessment Model",
                                        "recommendation_reason": "Matches the rooftop photovoltaic assessment context.",
                                    },
                                    "recommended_data": {
                                        "local_data": [{"name": "rooftops.zip", "location": "data/rooftops.zip"}],
                                        "knowledge_base_data": [],
                                    },
                                    "candidates": [{"name": "candidate-a"}],
                                }
                            )
                        }
                    }
                }

        calls = []

        def fake_post(url, headers, json, timeout):
            calls.append((url, headers, json, timeout))
            return FakeResponse()

        original_get_llm_config = modeler_module.get_llm_config
        original_post = modeler_module.requests.post
        try:
            modeler_module.get_llm_config = lambda: LLMConfig(
                dify_api_key="test-dify-key",
                dify_base_url="https://dify.example/v1",
            )
            modeler_module.requests.post = fake_post

            modeler = GeoModeler(client=FakeClient())
            result = modeler.suggest_model(
                context="Assess rooftop photovoltaic potential.",
                data_context="A local rooftop polygon dataset is available.",
            )
        finally:
            modeler_module.get_llm_config = original_get_llm_config
            modeler_module.requests.post = original_post

        self.assertIsInstance(result, RecommendationResult)
        self.assertEqual(
            result.primary_model["name"],
            "Roof Photovoltaic Carbon Emission Reduction Potential Assessment Model",
        )
        self.assertEqual(result.recommended_data["local_data"][0]["name"], "rooftops.zip")
        self.assertEqual(result.candidates[0]["name"], "candidate-a")
        self.assertEqual(result.context["modeling_history"], "Assess rooftop photovoltaic potential.")
        self.assertEqual(result.raw_response["source"], "dify_workflow")
        self.assertIs(modeler.last_recommendation, result)

        self.assertEqual(calls[0][0], "https://dify.example/v1/workflows/run")
        self.assertEqual(calls[0][1]["Authorization"], "Bearer test-dify-key")
        self.assertEqual(calls[0][2]["inputs"]["modeling_history"], "Assess rooftop photovoltaic potential.")
        self.assertEqual(calls[0][2]["inputs"]["data_context"], "A local rooftop polygon dataset is available.")
        self.assertEqual(calls[0][2]["response_mode"], "blocking")

    def test_suggest_model_parses_dify_markdown_json_output(self):
        import pygeomodel.modeler as modeler_module
        from pygeomodel import GeoModeler
        from pygeomodel.config import LLMConfig

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "data": {
                        "outputs": {
                            "text": """```json
{
  "model_recommendation": {
    "name": "Solar Potential Assessment Model",
    "recommendation_reason": "Matches the rooftop photovoltaic assessment context."
  },
  "recommended_data": {
    "local_data": [
      {
        "name": "Local Rooftop Polygon Dataset",
        "location": "Local storage"
      }
    ],
    "knowledge_base_data": []
  },
  "candidate_models": [
    {
      "rank": 1,
      "name": "Solar Potential Assessment Model",
      "reason": "Directly matches the user's photovoltaic assessment task.",
      "is_primary": true
    },
    {
      "rank": 2,
      "name": "Solar Radiation Estimation Model",
      "reason": "Useful as a related candidate for solar-resource estimation.",
      "is_primary": false
    }
  ]
}
```"""
                        }
                    }
                }

        def fake_post(url, headers, json, timeout):
            return FakeResponse()

        original_get_llm_config = modeler_module.get_llm_config
        original_post = modeler_module.requests.post
        try:
            modeler_module.get_llm_config = lambda: LLMConfig(
                dify_api_key="test-dify-key",
                dify_base_url="https://dify.example/v1",
            )
            modeler_module.requests.post = fake_post

            result = GeoModeler(client=FakeClient()).suggest_model(
                context="Assess rooftop photovoltaic potential.",
                data_context="A local rooftop polygon dataset is available.",
            )
        finally:
            modeler_module.get_llm_config = original_get_llm_config
            modeler_module.requests.post = original_post

        self.assertEqual(result.primary_model["name"], "Solar Potential Assessment Model")
        self.assertEqual(result.recommended_data["local_data"][0]["name"], "Local Rooftop Polygon Dataset")
        self.assertEqual(len(result.candidates), 2)
        self.assertEqual(result.candidates[0]["name"], "Solar Potential Assessment Model")
        self.assertTrue(result.candidates[0]["is_primary"])
        self.assertFalse(result.candidates[1]["is_primary"])

    def test_qa_result_has_notebook_rich_display(self):
        from pygeomodel import QAResult

        result = QAResult(
            question="这个模型的输入参数是什么意思？",
            answer="参考来源：https://example.org/paper\n\n- `ea`: 水汽压力",
            model_name="绝对湿度模型",
            sources=[{"type": "OpenGMS metadata", "model": "绝对湿度模型"}],
            raw_response={"source": "openai_web", "openai_model": "gpt-5.2-low"},
        )

        html = result._repr_html_()

        self.assertIn("绝对湿度模型", html)
        self.assertIn("OpenGMS Knowledge Base", html)
        self.assertIn("https://example.org/paper", html)
        self.assertNotIn("gpt-5.2-low", html)
        self.assertNotIn("openai_web", html)
        self.assertNotIn("Model:", html)
        self.assertNotIn("PyGeoModel Q&A", result._repr_markdown_())
        self.assertNotIn("Question:", result._repr_markdown_())

    def test_qa_result_renders_common_math_forms(self):
        from pygeomodel.results import _answer_to_html

        text = (
            "公式如下：\n\n"
            "[ pV = nRT ]\n\n"
            "常见形式类似 (\\rho = \\frac{pM}{RT})，也可写作 $R = 8.314$。"
        )

        rendered = _answer_to_html(text)

        self.assertIn("pygeomodel-qa-math-block", rendered)
        self.assertIn("pV = nRT", rendered)
        self.assertIn("pygeomodel-qa-math-inline", rendered)
        self.assertIn("ρ =", rendered)
        self.assertIn("pygeomodel-qa-frac", rendered)

    def test_consensus_client_parses_quick_search_results(self):
        from pygeomodel.consensus import ConsensusClient

        class FakeResponse:
            status_code = 200
            text = "{}"

            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "papers": [
                        {
                            "title": "Absolute humidity and air temperature",
                            "abstract": "Humidity is calculated from vapor pressure and temperature.",
                            "journal": "Climate Research",
                            "year": 2020,
                            "doi": "10.123/example",
                        }
                    ]
                }

        calls = []

        def fake_get(url, headers, params, timeout):
            calls.append((url, headers, params, timeout))
            return FakeResponse()

        client = ConsensusClient(api_key="test-key", request_get=fake_get)
        papers = client.quick_search("absolute humidity model")

        self.assertEqual(calls[0][0], "https://api.consensus.app/v1/quick_search")
        self.assertEqual(calls[0][1]["x-api-key"], "test-key")
        self.assertEqual(papers[0]["title"], "Absolute humidity and air temperature")

    def test_ask_model_uses_web_enabled_openai_without_provider_argument(self):
        from pygeomodel import GeoModeler

        modeler = GeoModeler(client=FakeClient())

        def fake_openai(model, question, context):
            return "这是一个由联网大模型结合学术来源生成的回答。"

        modeler._call_openai_qa = fake_openai

        result = modeler.ask_model("绝对湿度模型", "这个模型的输入参数是什么意思？")

        self.assertIn("联网大模型", result.answer)
        self.assertEqual(result.raw_response["source"], "openai_web")
        self.assertEqual(result.sources, [{"type": "OpenGMS metadata", "model": "绝对湿度模型"}])

    def test_qa_prompt_prioritizes_scientific_paper_resources(self):
        from pygeomodel import GeoModeler

        prompt = GeoModeler(client=FakeClient())._qa_system_prompt()

        self.assertIn("peer-reviewed scientific papers", prompt)
        self.assertIn("DOI", prompt)
        self.assertIn("stable URLs", prompt)
        self.assertIn("Do not rely primarily on Wikipedia", prompt)

    def test_notebook_interface_smoke(self):
        from pygeomodel import GeoModeler

        modeler = GeoModeler(client=FakeClient())
        widget = modeler.invoke_model("Roof Photovoltaic Carbon Emission Reduction Potential Assessment Model")

        self.assertTrue(hasattr(widget, "children"))

    def test_model_browser_survives_opened_invocation_form(self):
        from pygeomodel import GeoModeler

        modeler = GeoModeler(client=FakeClient())
        interface = modeler._interface()
        interface.show_models()
        detail_area = interface.widgets["model_detail_area"]

        interface.invoke_model("绝对湿度模型")
        interface._render_model_detail("绝对湿度模型")
        interface.current_query = "绝对"
        interface._refresh_model_browser()

        self.assertTrue(detail_area.children)

    def test_notebook_result_renderer_uses_structured_html(self):
        from pygeomodel import GeoModeler, TaskResult

        modeler = GeoModeler(client=FakeClient())
        interface = modeler._interface()
        result = TaskResult(
            model_name="m",
            status="completed",
            task_id="task-1",
            execution_time=1.23,
            outputs=[
                {
                    "statename": "RETURNDATA",
                    "event": "Output",
                    "tag": "RETURNDATA-Output",
                    "suffix": "xml",
                    "url": "http://example.test/result.xml",
                }
            ],
            params={"ea": "3"},
        )

        html = interface._render_task_result_html(result, "Model service is ready!")

        self.assertIn("Model run completed", html)
        self.assertIn("Output resources", html)
        self.assertIn("Open output", html)
        self.assertIn("Execution details", html)
        self.assertIn("task-1", html)

    def test_notebook_qa_renderer_uses_clean_html_card(self):
        from pygeomodel import GeoModeler, QAResult

        modeler = GeoModeler(client=FakeClient())
        interface = modeler._interface()
        result = QAResult(
            question="这个模型是干啥的",
            answer="常见形式类似 (\\rho = \\frac{pM}{RT})。",
            model_name="绝对湿度模型",
            sources=[{"type": "OpenGMS metadata", "model": "绝对湿度模型"}],
        )

        html = interface._render_qa_result_html(result)

        self.assertIn("pygeomodel-qa-card", html)
        self.assertIn("pygeomodel-qa-math-inline", html)
        self.assertIn("OpenGMS Knowledge Base", html)
        self.assertNotIn("PyGeoModel Q&A", html)
        self.assertNotIn("Question:", html)

    def test_error_sanitizer_masks_api_tokens(self):
        from pygeomodel import GeoModeler

        modeler = GeoModeler(client=FakeClient())
        message = "Incorrect API key provided: sk-test1234567890. Authorization: Bearer abc.def"
        sanitized = modeler._sanitize_error_message(message)

        self.assertNotIn("sk-test1234567890", sanitized)
        self.assertNotIn("abc.def", sanitized)
        self.assertIn("sk-***", sanitized)
        self.assertIn("Bearer ***", sanitized)

    def test_status_validator_reports_empty_outputs_clearly(self):
        from ogmsServer2.openUtils import modelStatusError
        from ogmsServer2.openUtils.parameterValidator import ParameterValidator

        with self.assertRaisesRegex(modelStatusError, "returned no output data"):
            ParameterValidator.v_status(-1)

    def test_completed_task_with_empty_output_url_is_still_completed(self):
        from ogmsServer2 import openModel

        task = object.__new__(openModel.OGMSTask)
        task.modelSign = {"ip": "127.0.0.1", "port": 8061, "tid": "task-1"}
        task.managerUrl = "http://example.test"

        original_post_sync = openModel.HttpClient.post_sync
        original_handler = openModel.HttpClient.hander_response

        def fake_post_sync(url, json):
            return {"url": url, "json": json}

        def fake_handler(_response):
            return {
                "json": {
                    "code": 1,
                    "data": {
                        "status": 2,
                        "outputs": [
                            {
                                "statename": "RETURNDATA",
                                "event": "Output",
                                "url": "",
                                "tag": "RETURNDATA-Output",
                                "suffix": "",
                            }
                        ],
                    },
                }
            }

        try:
            openModel.HttpClient.post_sync = fake_post_sync
            openModel.HttpClient.hander_response = fake_handler

            status = task._refresh()
        finally:
            openModel.HttpClient.post_sync = original_post_sync
            openModel.HttpClient.hander_response = original_handler

        self.assertEqual(status, 2)
        self.assertEqual(task.outputs[0]["event"], "Output")
        self.assertEqual(task.outputs[0]["url"], "")


if __name__ == "__main__":
    unittest.main()
