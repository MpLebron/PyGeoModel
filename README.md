# PyGeoModel

PyGeoModel is a Python package for integrating OpenGMS geographic model services into Python-based urban data science workflows. It provides programmatic access to model-service discovery, metadata inspection, service invocation, and result management. For exploratory notebook-based analysis, PyGeoModel also provides an optional Jupyter interface built on the same core API.

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
        "start_time": "2018-01",
        "end_time": "2018-12",
        "roof_vector_path": "data/rooftops.zip",
    },
)

saved_files = result.save(output_dir="data/result/live_run")
```

The model configuration is recorded directly in the Python cell through the explicit `params` dictionary, while `TaskResult.save()` stores the downloadable model outputs for subsequent analysis.

## Notebook Interface

```python
modeler.show_models()
modeler.invoke_model("Roof Photovoltaic Carbon Emission Reduction Potential Assessment Model")
```

The notebook interface renders model search, metadata inspection, parameter entry, task execution, and output display. It uses the same `search_models()`, `get_model()`, and `invoke()` functions as the programmatic API so GUI operations can be converted into explicit Python parameters and saved model outputs when needed.

## Recommendation and Q&A

```python
recommendation = modeler.suggest_model()

answer = modeler.ask_model(
    "Roof Photovoltaic Carbon Emission Reduction Potential Assessment Model",
    "What input data are required?",
)
```

The recommendation service automatically builds notebook/data context and calls the configured recommendation workflow. Q&A uses OpenGMS model metadata and an OpenAI-compatible web-enabled model. The main notebook workflow is designed to run out of the box for demonstration use.

## Relation to OpenGMS

OpenGMS provides the model-service platform and online execution infrastructure. PyGeoModel is a Python client package that exposes OpenGMS model-service discovery, metadata inspection, task invocation, and result management to Python and notebook workflows.
