# PyGeoModel

PyGeoModel is a Python package for integrating OpenGMS geographic model services into Python-based urban data science workflows. It provides programmatic access to model-service discovery, metadata inspection, service invocation, task records, and result management. For exploratory notebook-based analysis, PyGeoModel also provides an optional Jupyter interface built on the same core API.

## Installation

```bash
pip install PyGeoModel
```

Use the package in Python with:

```python
from pygeomodel import GeoModeler
```

## Core API

```python
from pygeomodel import GeoModeler

modeler = GeoModeler()

models = modeler.search_models("photovoltaic")
model = modeler.get_model("Roof Photovoltaic Carbon Emission Reduction Potential Assessment Model")

print(model.description)
print(model.inputs)
print(model.outputs)
```

Model services can be invoked programmatically:

```python
result = modeler.invoke(
    "Roof Photovoltaic Carbon Emission Reduction Potential Assessment Model",
    params={
        "system_efficiency": 0.8,
        "start_time": 201801,
        "end_time": 201812,
        "roof_vector_path": "data/rooftops.zip",
    },
)

result.to_json("execution_record.json")
```

OpenGMS execution requires an access token:

```bash
export OGMS_TOKEN="your-token"
```

Optional endpoint overrides:

```bash
export OGMS_BASE_PORTAL_URL="http://222.192.7.75"
export OGMS_BASE_MANAGER_URL="http://222.192.7.75/managerServer"
export OGMS_BASE_DATA_URL="http://222.192.7.75/dataTransferServer"
```

## Notebook Interface

```python
modeler.show_models()
modeler.invoke_model("SWAT_Model")
```

The notebook interface renders model search, metadata inspection, parameter entry, task execution, and output display. It uses the same `search_models()`, `get_model()`, and `invoke()` functions as the programmatic API so GUI operations can be converted into Python dictionaries and execution records.

## Recommendation and Q&A Records

```python
recommendation = modeler.suggest_model(return_result=True)
recommendation.to_json("recommendation_record.json")

answer = modeler.ask_model("SWAT_Model", "What input data are required?")
answer.to_json("qa_record.json")
```

The recommendation service uses notebook context and data context to call the configured Dify workflow. If `DIFY_API_KEY` is not configured, PyGeoModel returns a local metadata-based fallback recommendation. Q&A uses model metadata by default and can use OpenAI when `OPENAI_API_KEY` is configured.

## Relation to OpenGMS

OpenGMS provides the model-service platform and online execution infrastructure. PyGeoModel is a Python client package that exposes OpenGMS model-service discovery, metadata inspection, task invocation, and result records to Python and notebook workflows.

## Development

Run the lightweight test suite with:

```bash
python -m unittest discover -s tests
```

The source distribution should not include real API keys, local `.env` files, bytecode caches, generated C files, `.pyd` binaries, or previous build artifacts.
