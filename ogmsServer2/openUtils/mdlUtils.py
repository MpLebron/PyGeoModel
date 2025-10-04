"""
Author: DiChen
Date: 2024-09-09 21:19:00
LastEditors: DiChen
LastEditTime: 2024-09-09 21:25:48
"""


class MDL:
    # TODO:应该为动态IP
    def __init__(self):
        self.ip = "172.21.252.204"
        self.port = 8061
        self.origin_lists = {}

    def resolvingMDL(self, mdlData: dict):
        if mdlData:
            self.origin_lists = self.parse_model_data(mdlData)
            return self.origin_lists
        else:
            # TODO: 处理无mdl的情况
            return None

    ####################### private#######################

    def parse_model_data(self, mdl_data: dict):
        def extract_children(udx_node):
            return [
                {
                    "eventId": child["name"],
                    "eventName": child["name"],
                    "eventDesc": child["name"],
                    "eventType": child["type"]
                    .replace("DTKT_", "")
                    .replace("REAL", "FLOAT"),
                    "child": "true",
                    "value": "",
                }
                for child in udx_node.get("UdxNode", [])
            ]

        def process_event(event, evt, dataset_item, data, is_input=True):
            entry_type = "inputs" if is_input else "outputs"
            entry = {
                "statename": event.get("name"),
                "event": evt.get("name"),
                "optional": evt.get("optional"),
            }
            if is_input:
                entry.update(
                    {
                        "url": "",
                        "tag": dataset_item.get("name"),
                        "suffix": "",
                    }
                )
            else:
                entry["template"] = {
                    "type": "id" if "externalId" in dataset_item else "None",
                    "value": dataset_item.get("externalId", ""),
                }

            if dataset_item["type"] == "internal" and dataset_item.get(
                    "UdxDeclaration"
            ):
                udx_node = dataset_item["UdxDeclaration"][0].get("UdxNode")
                if udx_node:
                    entry["children"] = extract_children(
                        dataset_item["UdxDeclaration"][0]["UdxNode"][0]
                    )

            data[entry_type].append(entry)

        data = {
            "outputs": [],
            "port": self.port,  # Fill with actual port if available
            "inputs": [],
            "ip": self.ip,  # Fill with actual IP if available
            "pid": mdl_data.get("md5", ""),
            "oid": mdl_data.get("id", ""),
            "username": "",  # Fill with actual username if available
        }
        related_datasets = mdl_data["mdlJson"]["ModelClass"][0]["Behavior"][0][
            "RelatedDatasets"
        ][0]["DatasetItem"]

        for model_class in mdl_data.get("mdlJson", {}).get("ModelClass", []):
            for behavior in model_class.get("Behavior", []):
                for state_group in behavior.get("StateGroup", []):
                    for state in state_group.get("States", []):
                        for event in state.get("State", []):
                            for evt in event.get("Event", []):
                                dataset_reference = evt.get(
                                    "ResponseParameter",
                                    evt.get("DispatchParameter", []),
                                )
                                for param in dataset_reference:
                                    dataset_item = next(
                                        (
                                            item
                                            for item in related_datasets
                                            if item["name"] == param["datasetReference"]
                                        ),
                                        None,
                                    )
                                    if dataset_item:
                                        process_event(
                                            event,
                                            evt,
                                            dataset_item,
                                            data,
                                            is_input=(evt.get("type")
                                                      == "response"),
                                        )

        return data
