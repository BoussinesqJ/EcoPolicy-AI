# -*- coding: utf-8 -*-
"""
统一异常类定义

用法：
  from exceptions import EcoPolicyError, FetchError, ParseError, MatchError

  # 抛出异常
  raise FetchError("无法访问 URL", url="https://...")

  # 捕获异常
  try:
      ...
  except FetchError as e:
      logger.error(f"抓取失败: {e}")
      logger.error(f"URL: {e.url}")
"""

from typing import Optional, Any, Dict


class EcoPolicyError(Exception):
    """EcoPolicy-AI 基础异常类
    
    所有自定义异常的父类，用于统一捕获项目相关错误。
    """
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)
    
    def __str__(self) -> str:
        if self.details:
            detail_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"{self.message} ({detail_str})"
        return self.message


class ConfigError(EcoPolicyError):
    """配置错误
    
    用于配置文件格式错误、必填字段缺失等情况。
    """
    
    def __init__(self, message: str, config_path: Optional[str] = None, **kwargs):
        details = {"config_path": config_path} if config_path else {}
        details.update(kwargs)
        super().__init__(message, details)
        self.config_path = config_path


class FetchError(EcoPolicyError):
    """抓取错误
    
    用于 HTTP 请求失败、robots.txt 禁止等情况。
    """
    
    def __init__(self, message: str, url: Optional[str] = None, status_code: Optional[int] = None, **kwargs):
        details = {}
        if url:
            details["url"] = url
        if status_code:
            details["status_code"] = status_code
        details.update(kwargs)
        super().__init__(message, details)
        self.url = url
        self.status_code = status_code


class ParseError(EcoPolicyError):
    """解析错误
    
    用于 HTML/JSON/文件解析失败等情况。
    """
    
    def __init__(self, message: str, source: Optional[str] = None, parser_type: Optional[str] = None, **kwargs):
        details = {}
        if source:
            details["source"] = source
        if parser_type:
            details["parser_type"] = parser_type
        details.update(kwargs)
        super().__init__(message, details)
        self.source = source
        self.parser_type = parser_type


class MatchError(EcoPolicyError):
    """匹配错误
    
    用于企业画像加载失败、匹配过程异常等情况。
    """
    
    def __init__(self, message: str, enterprise_id: Optional[str] = None, policy_title: Optional[str] = None, **kwargs):
        details = {}
        if enterprise_id:
            details["enterprise_id"] = enterprise_id
        if policy_title:
            details["policy_title"] = policy_title
        details.update(kwargs)
        super().__init__(message, details)
        self.enterprise_id = enterprise_id
        self.policy_title = policy_title


class DatabaseError(EcoPolicyError):
    """数据库错误
    
    用于数据库连接失败、查询异常等情况。
    """
    
    def __init__(self, message: str, db_path: Optional[str] = None, operation: Optional[str] = None, **kwargs):
        details = {}
        if db_path:
            details["db_path"] = db_path
        if operation:
            details["operation"] = operation
        details.update(kwargs)
        super().__init__(message, details)
        self.db_path = db_path
        self.operation = operation


class ValidationError(EcoPolicyError):
    """验证错误
    
    用于数据验证失败、格式错误等情况。
    """
    
    def __init__(self, message: str, field: Optional[str] = None, value: Optional[Any] = None, **kwargs):
        details = {}
        if field:
            details["field"] = field
        if value is not None:
            details["value"] = value
        details.update(kwargs)
        super().__init__(message, details)
        self.field = field
        self.value = value


class SchedulerError(EcoPolicyError):
    """调度器错误
    
    用于定时任务配置错误、执行失败等情况。
    """
    
    def __init__(self, message: str, task_name: Optional[str] = None, **kwargs):
        details = {"task_name": task_name} if task_name else {}
        details.update(kwargs)
        super().__init__(message, details)
        self.task_name = task_name


class SecurityError(EcoPolicyError):
    """安全审查错误
    
    用于安全审查失败、敏感信息泄露等情况。
    """
    
    def __init__(self, message: str, file_path: Optional[str] = None, issue_type: Optional[str] = None, **kwargs):
        details = {}
        if file_path:
            details["file_path"] = file_path
        if issue_type:
            details["issue_type"] = issue_type
        details.update(kwargs)
        super().__init__(message, details)
        self.file_path = file_path
        self.issue_type = issue_type


# ============================================================
# 异常处理工具函数
# ============================================================

def handle_exception(e: Exception, logger=None, reraise: bool = True) -> Optional[str]:
    """统一异常处理
    
    Args:
        e: 异常对象
        logger: 日志记录器（可选）
        reraise: 是否重新抛出异常
        
    Returns:
        错误消息字符串（如果不重新抛出）
    """
    # 构建错误消息
    if isinstance(e, EcoPolicyError):
        error_msg = str(e)
    else:
        error_msg = f"{type(e).__name__}: {e}"
    
    # 记录日志
    if logger:
        if isinstance(e, (ConfigError, ValidationError)):
            logger.warning(error_msg)
        elif isinstance(e, (FetchError, ParseError)):
            logger.error(error_msg)
        elif isinstance(e, (DatabaseError, SecurityError)):
            logger.critical(error_msg)
        else:
            logger.error(error_msg)
    
    # 重新抛出或返回
    if reraise:
        raise
    return error_msg


def safe_execute(func, *args, logger=None, default=None, **kwargs):
    """安全执行函数
    
    捕获异常并返回默认值，适用于非关键操作。
    
    Args:
        func: 要执行的函数
        *args: 函数参数
        logger: 日志记录器（可选）
        default: 异常时返回的默认值
        **kwargs: 函数关键字参数
        
    Returns:
        函数返回值或默认值
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        if logger:
            logger.warning(f"安全执行失败: {func.__name__} - {e}")
        return default
