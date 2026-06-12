# -*- coding: utf-8 -*-
"""
运行器基类 - 所有运行器的抽象基类
"""

from abc import ABC, abstractmethod
import AmazingData as ad
from config.settings import DBConfig
from utils.encoding import configure_utf8_console
from utils.logging import RunnerLogSession


class BaseRunner(ABC):
    """运行器基类"""
    
    def __init__(self, auto_login=True):
        self._auto_login = auto_login
        self._logged_in = False
        self._log_session = None
    
    def login(self):
        """登录API"""
        if not self._logged_in:
            ad.login(
                username=DBConfig.USERNAME, 
                password=DBConfig.PASSWORD, 
                host=DBConfig.IP, 
                port=DBConfig.PORT
            )
            self._logged_in = True
    
    def logout(self):
        """登出API"""
        if self._logged_in:
            ad.logout(DBConfig.USERNAME)
            self._logged_in = False
    
    @abstractmethod
    def run(self, **kwargs):
        """执行运行逻辑"""
        pass
    
    def __enter__(self):
        configure_utf8_console()
        self._log_session = RunnerLogSession(self.__class__.__name__)
        self._log_session.start()
        if self._auto_login:
            self.login()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self.logout()
        finally:
            if self._log_session is not None:
                self._log_session.stop()
