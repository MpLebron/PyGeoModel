"""
Author: DiChen
Date: 2024-09-08 11:46:48
LastEditors: DiChen
LastEditTime: 2024-09-09 21:59:50
"""

"""
Author: DiChen
Date: 2024-09-08 11:46:48
LastEditors: DiChen
LastEditTime: 2024-09-08 11:46:51
"""

# exceptions.py


# 基础自定义异常类
class MyBaseError(Exception):
    """自定义基础异常类"""

    def __init__(self, message, error_code=None):
        super().__init__(message)
        self.error_code = error_code

    def __str__(self):
        if self.error_code:
            return f"[Error {self.error_code}]: {self.args[0]}"
        else:
            return self.args[0]


# 具体的自定义异常类
class NotValueError(MyBaseError):
    """data is none"""

    def __init__(self, message="not Value", error_code=1001):
        super().__init__(message, error_code)


class DatabaseError(MyBaseError):
    """database error"""

    def __init__(self, message="database error", error_code=1002):
        super().__init__(message, error_code)


class NetworkError(MyBaseError):
    """network error"""

    def __init__(self, message="network error", error_code=1003):
        super().__init__(message, error_code)


class modelStatusError(MyBaseError):
    """model status error"""

    def __init__(self, message="model status error", error_code=1004):
        super().__init__(message, error_code)


class calTimeoutError(MyBaseError):
    """model calculate timeout error"""

    def __init__(self, message="model calculate timeout error", error_code=1005):
        super().__init__(message, error_code)


class UploadFileError(MyBaseError):
    """upload file error"""

    def __init__(self, message="upload file error", error_code=1006):
        super().__init__(message, error_code)


class MDLVaildParamsError(MyBaseError):
    """MDL vaild params error"""

    def __init__(self, message="MDL vaild params error", error_code=1007):
        super().__init__(message, error_code)
