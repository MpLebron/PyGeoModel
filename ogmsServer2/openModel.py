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
        # 对输入的参数进行校验、文件上传等操作

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

        except NotValueError or modelStatusError as e:
            print(e)
            exit(1)

    def configInputData(self, params: dict):
        try:
            PV.v_empty(params, "params list")
            lists = {"inputs": self._uploadData(
                params), "username": self.username}
            return self._mergeData(lists)
        except NotValueError or UploadFileError or MDLVaildParamsError as e:
            print(e)
            exit(1)

    ######################## private################################
    def _uploadData(self, pathList: dict):
        inputs = {}
        for category, files in pathList.items():
            inputs[category] = {}
            for key, value in files.items():
                # 判断是数值参数还是文件参数
                if isinstance(value, (str, int, float)) and not str(value).startswith('/'):
                    # 数值参数：生成XML，上传并返回url；同时保留children用于填充值
                    xml_content = self._create_value_xml(str(key), str(value))
                    xml_url = self._upload_xml_string(
                        xml_content, f"{key}.xml")
                    inputs[category][key] = {
                        "name": f"{key}.xml",
                        "url": xml_url,
                        "children": [{str(key): str(value)}],
                    }
                else:
                    # 文件参数：上传文件并获取URL
                    file_path = str(value)
                    file_name = file_path.split("/")[-1]
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

    def _create_value_xml(self, name: str, value: str) -> str:
        """根据数值参数生成与服务端兼容的XML内容。"""
        # 参考 testify 目录示例：
        # <Dataset> <XDO name="system_efficiency" kernelType="string" value="0.8" /> </Dataset>
        return f'<Dataset> <XDO name="{name}" kernelType="string" value="{value}" /> </Dataset>'

    def _upload_xml_string(self, xml_content: str, filename: str) -> str:
        """将XML字符串写入临时文件并复用文件上传接口，返回url。"""
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
            """提取文件名的后缀名."""
            return filename.split(".")[-1] if "." in filename else ""

        def update_input_item(input_item: dict, event_data: dict):
            """
            根据 input_data 中的 event_data 更新 origin_data 中的 input_item。
            支持处理直接传递的 'value' 字段和children结构。
            """
            # ✅ 处理直接传递value的情况（数值参数）
            if "value" in event_data and "url" not in event_data:
                # 数值参数：如 {"value": "0.8"}
                if "children" in input_item and input_item["children"]:
                    child = input_item["children"][0]
                    child["value"] = event_data["value"]
                    input_item["suffix"] = "xml"  # 数值参数使用xml格式
                return  # 早返回，避免执行后面的逻辑

            # 原有的处理逻辑
            if "children" in event_data:
                input_item["suffix"] = "xml"  # 如果有 children，后缀名固定为 xml
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
            """根据 input_data 填补 origin_data."""
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

            # 检查是否是数值参数（有children但没有url）
            is_numeric_param = "children" in event and not event.get("url")

            if event.get("optional") == "False":
                # 必填项
                if is_numeric_param:
                    # 数值参数：只检查children和suffix
                    if not event.get("suffix"):
                        errors.append(f"{event_name}的文件格式有误！")
                    for child in event["children"]:
                        if not child.get("value"):
                            errors.append(f"{event_name}子参数有误")
                else:
                    # 文件参数：检查url和suffix
                    if not event.get("url"):
                        errors.append(f"{event_name}的中转数据信息有误！")
                    if not event.get("suffix"):
                        errors.append(f"{event_name}的文件有误！")
            elif event.get("optional") == "True":
                # 选填项
                if event.get("url") or event.get("suffix") or "children" in event:
                    if not (event.get("url") and event.get("suffix")):
                        errors.append(f"{event_name}子参数有误！")
                    if "children" in event:
                        for child in event["children"]:
                            if not child.get("value"):
                                errors.append(f"{event_name}子参数不能为空！")

            return errors

        def process_inputs(inputs):
            errors = []
            valid_inputs = []
            for event in inputs:
                event_errors = validate_event(event)
                if event_errors:
                    errors.extend(event_errors)
                else:
                    if event.get("optional") == "True":
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

        # 处理 inputs
        valid_inputs, input_errors = process_inputs(
            merge_data.get("inputs", []))
        errors.extend(input_errors)

        # 更新数据
        merge_data["inputs"] = valid_inputs

        # 打印错误信息
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
                hasValue = False
                for output in res["data"]["outputs"]:
                    if output.get("url") is not None and output.get("url") != "":
                        url = output.get("url")
                        # updated_url = url.replace(
                        #     "http://112.4.132.6:8083",
                        #     "http://geomodeling.njnu.edu.cn/dataTransferServer",
                        # )
                        output["url"] = url
                        hasValue = True
                if hasValue is False:
                    return -1
                for output in res["data"]["outputs"]:
                    if "[" in output.get("url"):
                        output["multiple"] = True
                self.outputs = res["data"]["outputs"]
                return 2
        return -2


class OGMSAccess(Service):
    def __init__(self, modelName: str, token: str = None):
        super().__init__(token=token)
        PV.v_empty(modelName, "Model name")
        self.modelName = modelName
        self.outputs = []
        if self._checkModelService(pid=self._checkModel(modelName=modelName)):
            print("Model service is ready!")
        else:
            print("Model service is not ready, please try again later!")
            exit(1)

    def createTask(self, params: dict):
        PV.v_empty(params, "Params")
        task = OGMSTask(self.originLists, self.token)
        if task.configInputData(params) and self._subscribeTask(task):
            result = task.wait4Status()
            self.outputs = result["outputs"]
            return self.outputs

    def downloadAllData(self):

        s_id = secrets.token_hex(8)
        downloadFilesNum = 0
        downlaodedFilesNum = 0
        if not self.outputs:
            print("没有可下载的数据")
            return False

        for output in self.outputs:
            statename = output["statename"]
            event = output["event"]
            url = output["url"]
            suffix = output["suffix"]
            # 构建文件名
            base_filename = f"{statename}-{event}"
            filename = f"{base_filename}.{suffix}"
            counter = 1

            file_path = "./data/" + self.modelName + "_" + s_id + "/" + filename

            dir_path = os.path.dirname(file_path)
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)

            # 检查文件是否存在
            while os.path.exists(file_path):
                filename = f"{base_filename}_{counter}.{suffix}"
                file_path = "./data/" + self.modelName + "_" + s_id + "/" + filename
                counter += 1
            downloadFilesNum = downloadFilesNum + 1
            # 下载文件并保存
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
