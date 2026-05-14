"""
Author: DiChen
Date: 2024-09-06 15:14:57
LastEditors: DiChen
LastEditTime: 2024-09-07 00:16:30
"""

from . import *
import secrets
import os


class OGMSTask(Service):
    def __init__(self, origin_lists: dict, token: str = None):
        super().__init__(token=token)
        self.status: None | int = None
        self.username = token
        PV.v_empty(origin_lists, "origin lists")
        self.origin_lists = origin_lists
        self.subscirbe_lists = {}
        self.tid = None
        # Validate input parameters, upload files, etc.

    def wait4Status(self, timeout: int = 7200):
        try:
            start_time = time.time()
            stateManager = StateManager()
            stateManager.checkInputStatus(PV.v_status(self._refresh()))
            while stateManager.hasStatus(0b100) is False:
                stateManager.checkInputStatus(PV.v_status(self._refresh()))
                if time.time() - start_time > timeout:
                    raise calTimeoutError()
                time.sleep(3)
            return {
                "outputs": self.outputs,
            }

        except (NotValueError, modelStatusError) as e:
            raise RuntimeError(f"Model execution failed: {e}")

    def configInputData(self, params: dict):
        try:
            PV.v_empty(params, "params list")
            lists = {"inputs": self._uploadData(
                params), "username": self.username}
            return self._mergeData(lists)
        except (NotValueError, UploadFileError, MDLVaildParamsError) as e:
            raise RuntimeError(f"Failed to configure input data: {e}")

    ######################## private################################
    def _uploadData(self, pathList: dict):
        from pathlib import Path

        inputs = {}
        for category, files in pathList.items():
            inputs[category] = {}
            for key, value in files.items():
                if isinstance(value, dict) and "children" in value:
                    children = self._normalize_xml_children(value.get("children", []))
                    child_types = self._event_child_types(category, key)
                    xml_content = self._create_children_xml(children, child_types=child_types)
                    xml_url = self._upload_xml_string(xml_content, f"{key}.xml")
                    inputs[category][key] = {
                        "name": f"{key}.xml",
                        "url": xml_url,
                        "children": children,
                    }
                    continue

                file_path = Path(str(value)).expanduser() if isinstance(value, str) else None
                is_file = bool(file_path and file_path.exists())
                is_scalar = isinstance(value, (str, int, float, bool)) and not is_file
                # Check if it's a scalar parameter or file parameter. Relative file paths
                # must be treated as files when they exist on disk.
                if is_scalar:
                    # Numeric parameter: generate XML, upload and return URL; keep children for value filling
                    child_types = self._event_child_types(category, key)
                    xml_content = self._create_value_xml(str(key), str(value), child_types=child_types)
                    xml_url = self._upload_xml_string(
                        xml_content, f"{key}.xml")
                    inputs[category][key] = {
                        "name": f"{key}.xml",
                        "url": xml_url,
                        "children": [{str(key): str(value)}],
                    }
                else:
                    # File parameter: upload file and get URL
                    file_path = str(file_path if file_path else value)
                    file_name = Path(file_path).name
                    inputs[category][key] = {
                        "name": file_name,
                        "url": self._getUploadData(file_path),
                    }
        return inputs

    def _getUploadData(self, path: str):
        res = (
            HttpClient.hander_response(
                HttpClient.post_sync(
                    self.dataUrl + C.UPLOAD_DATA, files={"datafile": open(path, "rb")}
                )
            )
            .get("json", {})
            .get("data", {})
        )
        if res.get("id"):
            return self.dataUrl+C.UPLOAD_DATA + res.get(
                "id"
            )
        raise UploadFileError()

    def _create_value_xml(self, name: str, value: str, child_types: dict | None = None) -> str:
        """Generate XML content compatible with server for numeric parameters."""
        # Reference from testify directory example:
        # <Dataset> <XDO name="system_efficiency" kernelType="string" value="0.8" /> </Dataset>
        return self._create_children_xml([{name: value}], child_types=child_types)

    def _normalize_xml_children(self, children: list[dict]) -> list[dict[str, str]]:
        normalized = []
        for child in children:
            if not isinstance(child, dict):
                continue
            for name, value in child.items():
                normalized.append({str(name): str(value)})
        return normalized

    def _create_children_xml(self, children: list[dict], child_types: dict | None = None) -> str:
        """Generate XML content for internal OpenGMS parameters with child values."""
        from xml.sax.saxutils import quoteattr

        child_types = child_types or {}
        nodes = []
        for child in self._normalize_xml_children(children):
            for name, value in child.items():
                kernel_type = self._normalize_kernel_type(child_types.get(name))
                nodes.append(
                    f"<XDO name={quoteattr(name)} kernelType={quoteattr(kernel_type)} value={quoteattr(value)} />"
                )
        return f"<Dataset> {' '.join(nodes)} </Dataset>"

    def _event_child_types(self, state_name: str, event_name: str) -> dict[str, str]:
        """Return MDL-declared child kernel types for an input event."""
        for input_item in self.origin_lists.get("inputs", []):
            if input_item.get("statename") != state_name or input_item.get("event") != event_name:
                continue
            child_types = {}
            for child in input_item.get("children", []):
                name = child.get("eventName") or child.get("eventId")
                event_type = child.get("eventType")
                if name and event_type:
                    child_types[str(name)] = str(event_type)
            return child_types
        return {}

    def _normalize_kernel_type(self, event_type: str | None) -> str:
        if not event_type:
            return "string"
        normalized = str(event_type).replace("DTKT_", "").strip().lower()
        if normalized == "real":
            return "float"
        return normalized or "string"

    def _upload_xml_string(self, xml_content: str, filename: str) -> str:
        """Write XML string to temp file and use file upload interface, return URL."""
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False, encoding="utf-8") as tmp_file:
            tmp_file.write(xml_content)
            tmp_path = tmp_file.name
        try:
            return self._getUploadData(tmp_path)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def _mergeData(self, params: dict):
        def extract_file_suffix(filename: str) -> str:
            """Extract file extension from filename."""
            return filename.split(".")[-1] if "." in filename else ""

        def update_input_item(input_item: dict, event_data: dict):
            """
            Update input_item in origin_data with event_data from input_data.
            Supports direct 'value' fields and children structures.
            """
            # Handle direct value passing (numeric parameters)
            if "value" in event_data and "url" not in event_data:
                # Numeric parameter: e.g. {"value": "0.8"}
                if "children" in input_item and input_item["children"]:
                    child = input_item["children"][0]
                    child["value"] = event_data["value"]
                    input_item["suffix"] = "xml"  # Numeric parameters use xml format
                return  # Early return to avoid executing following logic

            # Original processing logic
            if "children" in event_data:
                input_item["suffix"] = "xml"  # If children exists, suffix is fixed to xml
                for child in input_item.get("children", []):
                    event_name = child["eventName"]
                    for b_child in event_data["children"]:
                        if event_name in b_child:
                            child["value"] = b_child[event_name]
            else:
                if "name" in event_data:
                    input_item["suffix"] = extract_file_suffix(
                        event_data["name"])

            if "url" in event_data:
                input_item["url"] = event_data["url"]

        def fill_data_with_input(input_data: dict, origin_data: dict) -> dict:
            """Fill origin_data with input_data."""
            for input_item in origin_data.get("inputs", []):
                state_name = input_item.get("statename")
                event_name = input_item.get("event")

                PV.v_empty(state_name, "State name")
                PV.v_empty(event_name, "Event name")

                state_data = input_data["inputs"].get(state_name)
                if state_data and event_name in state_data:
                    update_input_item(input_item, state_data[event_name])
            origin_data["username"] = input_data.get("username")
            return origin_data

        filled_origin_data = fill_data_with_input(params, self.origin_lists)
        return self._validData(filled_origin_data)

    def _validData(self, merge_data: dict):
        def validate_event(event):
            errors = []
            event_name = f"{event.get('statename')}-{event.get('event')}"

            # Check if it's a numeric parameter (has children but no URL)
            is_numeric_param = "children" in event and not event.get("url")

            optional = str(event.get("optional")).lower()
            if optional == "false":
                # Required field
                if is_numeric_param:
                    # Numeric parameter: only check children and suffix
                    if not event.get("suffix"):
                        errors.append(f"{event_name} has invalid file format!")
                    for child in event["children"]:
                        if not child.get("value"):
                            errors.append(f"{event_name} has invalid child parameter")
                else:
                    # File parameter: check url and suffix
                    if not event.get("url"):
                        errors.append(f"{event_name} has invalid transfer data!")
                    if not event.get("suffix"):
                        errors.append(f"{event_name} has invalid file!")
            elif optional == "true":
                # Optional field
                if event.get("url") or event.get("suffix") or "children" in event:
                    if not (event.get("url") and event.get("suffix")):
                        errors.append(f"{event_name} has invalid child parameter!")
                    if "children" in event:
                        for child in event["children"]:
                            if not child.get("value"):
                                errors.append(f"{event_name} child parameter cannot be empty!")

            return errors

        def process_inputs(inputs):
            errors = []
            valid_inputs = []
            for event in inputs:
                event_errors = validate_event(event)
                if event_errors:
                    errors.extend(event_errors)
                else:
                    if str(event.get("optional")).lower() == "true":
                        if not (
                            event.get("url")
                            or event.get("suffix")
                            or "children" in event
                        ):
                            continue
                    valid_inputs.append(event)
            return valid_inputs, errors

        def check_username(username):
            errors = []
            if not username:
                errors.append("no token")
            return errors

        errors = check_username(merge_data.get("username"))

        # Process inputs
        valid_inputs, input_errors = process_inputs(
            merge_data.get("inputs", []))
        errors.extend(input_errors)

        # Update data
        merge_data["inputs"] = valid_inputs

        # Print error messages
        if errors:
            raise MDLVaildParamsError("\n".join(errors))
        else:
            self.subscirbe_lists = merge_data
            return 1

    def _refresh(self):
        PV.v_empty(self.modelSign, "Model sign")
        res = HttpClient.hander_response(
            HttpClient.post_sync(
                url=self.managerUrl + C.REFRESH_RECORD, json=self.modelSign
            )
        ).get("json", {})
        if res.get("code") == 1:
            if res.get("data").get("status") != 2:
                return res.get("data").get("status")
            else:
                outputs = res.get("data", {}).get("outputs") or []
                for output in outputs:
                    if output.get("url") is not None and output.get("url") != "":
                        url = output.get("url")
                        # updated_url = url.replace(
                        #     "http://112.4.132.6:8083",
                        #     "http://geomodeling.njnu.edu.cn/dataTransferServer",
                        # )
                        output["url"] = url
                    if "[" in output.get("url", ""):
                        output["multiple"] = True
                self.outputs = outputs
                return 2
        return -2


class OGMSAccess(Service):
    def __init__(self, modelName: str, token: str = None):
        super().__init__(token=token)
        PV.v_empty(modelName, "Model name")
        self.modelName = modelName
        self.outputs = []
        if self._checkModelService(pid=self._checkModel(modelName=modelName)):
            print("✅ Model service is ready!")
        else:
            raise RuntimeError(f"Model service '{modelName}' is not ready. Please try again later.")

    def createTask(self, params: dict):
        PV.v_empty(params, "Params")
        task = OGMSTask(self.originLists, self.token)
        if task.configInputData(params) and self._subscribeTask(task):
            self.last_task = task
            self.task_id = task.tid
            result = task.wait4Status()
            self.outputs = result["outputs"]
            return self.outputs

    def downloadAllData(self):

        s_id = secrets.token_hex(8)
        downloadFilesNum = 0
        downlaodedFilesNum = 0
        if not self.outputs:
            print("No data available for download")
            return False

        for output in self.outputs:
            statename = output["statename"]
            event = output["event"]
            url = output["url"]
            suffix = output["suffix"]
            # Build filename
            base_filename = f"{statename}-{event}"
            filename = f"{base_filename}.{suffix}"
            counter = 1

            file_path = "./data/" + self.modelName + "_" + s_id + "/" + filename

            dir_path = os.path.dirname(file_path)
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)

            # Check if file already exists
            while os.path.exists(file_path):
                filename = f"{base_filename}_{counter}.{suffix}"
                file_path = "./data/" + self.modelName + "_" + s_id + "/" + filename
                counter += 1
            downloadFilesNum = downloadFilesNum + 1
            # Download and save file
            content = HttpClient.hander_response(HttpClient.get_file_sync(url=url)).get(
                "content", {}
            )
            if content:
                with open(file_path, "wb") as f:
                    f.write(content)
                print(f"Downloaded {filename}")
                downlaodedFilesNum = downlaodedFilesNum + 1
            else:
                print(f"Failed to download {url}")
        if downlaodedFilesNum == 0:
            print("Failed to download files")
            return False
        if downloadFilesNum == downlaodedFilesNum:
            print("All files downloaded successfully")
            return True
        else:
            print("Failed to download some files")
            return True

    ######################## private################################
    def _checkModel(self, modelName: str):
        PV.v_empty(modelName, "Model name")
        res = (
            HttpClient.hander_response(
                HttpClient.get_sync(
                    self.portalUrl + C.CHECK_MODEL +
                    urllib.parse.quote(modelName)
                )
            )
            .get("json", {})
            .get("data", {})
        )
        if res.get("md5"):
            self.originLists = MDL().resolvingMDL(res)
            if self.originLists:
                return res.get("md5")
        return 0

    def _checkModelService(self, pid: str):
        PV.v_empty(pid, "Model pid")
        if (
            HttpClient.hander_response(
                HttpClient.get_sync(
                    self.managerUrl + C.CHECK_MODEL_SERVICE + pid)
            )
            .get("json", {})
            .get("data", {})
            == True
        ):
            return 1
        return 0

    def _subscribeTask(self, task):
        res = HttpClient.hander_response(
            HttpClient.post_sync(
                self.managerUrl + C.INVOKE_MODEL, json=task.subscirbe_lists
            )
        ).get("json", {})
        if res.get("code") == 1:
            task.ip = res.get("data").get("ip")
            task.port = res.get("data").get("port")
            task.tid = res.get("data").get("tid")
            task.modelSign = {"port": task.port,
                              "ip": task.ip, "tid": task.tid}
            return 1
        raise NotValueError("Model invoke error!")
