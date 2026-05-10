import json
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

    def test_notebook_interface_smoke(self):
        from pygeomodel import GeoModeler

        modeler = GeoModeler(client=FakeClient())
        widget = modeler.invoke_model("Roof Photovoltaic Carbon Emission Reduction Potential Assessment Model")

        self.assertTrue(hasattr(widget, "children"))

    def test_error_sanitizer_masks_api_tokens(self):
        from pygeomodel import GeoModeler

        modeler = GeoModeler(client=FakeClient())
        message = "Incorrect API key provided: sk-test1234567890. Authorization: Bearer abc.def"
        sanitized = modeler._sanitize_error_message(message)

        self.assertNotIn("sk-test1234567890", sanitized)
        self.assertNotIn("abc.def", sanitized)
        self.assertIn("sk-***", sanitized)
        self.assertIn("Bearer ***", sanitized)


if __name__ == "__main__":
    unittest.main()
