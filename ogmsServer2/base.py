"""
Author: DiChen
Date: 2024-09-06 15:22:20
LastEditors: DiChen
LastEditTime: 2024-09-11 18:37:16
"""

import sys
from . import constants as C
from .openUtils.http_client import HttpClient


class Service:
    def __init__(self, token: str = None):
        # res = HttpClient.hander_response(
        #     HttpClient.get_sync(
        #         url="http://www.baidu.com"
        #     )
        # )
        self.token: str = token
        self.portalUrl = C.basePortalUrl
        self.managerUrl = C.baseManagerUrl
        self.dataUrl = C.baseDataUrl
        if not (self.portalUrl or self.managerUrl or self.dataUrl):
            print("读取配置文件有误，请联系管理员！")
            sys.exit(1)
        self._validateToken()

    #########################private#########################################
    def _validateToken(self):
        res = HttpClient.hander_response(
            HttpClient.get_sync(
                self.portalUrl + C.CHECK_SDK, params={"token": self.token}
            )
        ).get("json", {})
        if res.get("data") != 1:
            print("token无效，请联系管理员！")
            sys.exit(1)
