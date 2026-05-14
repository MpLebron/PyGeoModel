"""
Author: DiChen
Date: 2024-09-10 18:54:44
LastEditors: DiChen
LastEditTime: 2024-09-10 18:54:56
"""

import os

###################### configPath######################
basePortalUrl = os.environ.get("OGMS_BASE_PORTAL_URL", "http://222.192.7.75")
baseManagerUrl = os.environ.get(
    "OGMS_BASE_MANAGER_URL", "http://222.192.7.75/managerServer"
)
baseDataUrl = os.environ.get(
    "OGMS_BASE_DATA_URL", "http://222.192.7.75/dataTransferServer"
)


###################### apiPath########################
CHECK_MODEL = "/computableModel/ModelInfo_name/"
CHECK_MODEL_SERVICE = "/GeoModeling/task/verify/"
INVOKE_MODEL = "/GeoModeling/computableModel/invoke"
REFRESH_RECORD = "/GeoModeling/computableModel/refreshTaskRecord"
UPLOAD_DATA = "/data/"
CHECK_SDK = "/sdk/check_test/"
