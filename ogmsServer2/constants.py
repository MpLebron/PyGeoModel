"""
Author: DiChen
Date: 2024-09-10 18:54:44
LastEditors: DiChen
LastEditTime: 2024-09-10 18:54:56
"""

###################### configPath######################
basePortalUrl = "http://222.192.7.75"
# basePortalUrl = "http://172.21.212.251:7777"
baseManagerUrl = "http://222.192.7.75/managerServer"
baseDataUrl = "http://222.192.7.75/dataTransferServer"


###################### apiPath########################
CHECK_MODEL = "/computableModel/ModelInfo_name/"
CHECK_MODEL_SERVICE = "/GeoModeling/task/verify/"
INVOKE_MODEL = "/GeoModeling/computableModel/invoke"
REFRESH_RECORD = "/GeoModeling/computableModel/refreshTaskRecord"
UPLOAD_DATA = "/data/"
CHECK_SDK = "/sdk/check_test/"
