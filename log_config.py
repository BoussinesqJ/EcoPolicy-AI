# -*- coding: utf-8 -*-
"""
统一日志配置

用法：
  # 在程序入口调用
  from log_config import setup_logging
  setup_logging(level="INFO")

  # 在各模块获取 logger
  import logging
  logger = logging.getLogger("ecopolicy.matcher")
"""

import logging
import logging.config
from pathlib import Path


# ============================================================
# 日志配置字典
# ============================================================

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    
    "formatters": {
        "standard": {
            "format": "%(asctime)s [%(name)s] %(levelname)s: %(message)s",
            "datefmt": "%H:%M:%S",
        },
        "detailed": {
            "format": "%(asctime)s [%(name)s] %(levelname)s %(filename)s:%(lineno)d: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "simple": {
            "format": "%(levelname)s: %(message)s",
        },
    },
    
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
            "formatter": "standard",
            "stream": "ext://sys.stdout",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "DEBUG",
            "formatter": "detailed",
            "filename": "policy_data/logs/ecopolicy.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
            "encoding": "utf-8",
        },
    },
    
    "loggers": {
        # 根 logger
        "ecopolicy": {
            "level": "DEBUG",
            "handlers": ["console"],
            "propagate": False,
        },
        # 子模块 logger
        "ecopolicy.matcher": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
        "ecopolicy.monitor": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
        "ecopolicy.reporter": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
        "ecopolicy.scheduler": {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
    },
    
    "root": {
        "level": "WARNING",
        "handlers": ["console"],
    },
}


# ============================================================
# Logger 名称常量
# ============================================================

# 统一的 logger 名称前缀
LOGGER_PREFIX = "ecopolicy"

# 各模块 logger 名称
LOGGER_MATCHER = "ecopolicy.matcher"
LOGGER_MONITOR = "ecopolicy.monitor"
LOGGER_REPORTER = "ecopolicy.reporter"
LOGGER_SCHEDULER = "ecopolicy.scheduler"
LOGGER_PARSER = "ecopolicy.parser"
LOGGER_BATCH = "ecopolicy.batch"
LOGGER_TRACKER = "ecopolicy.tracker"
LOGGER_STACKER = "ecopolicy.stacker"
LOGGER_ROI = "ecopolicy.roi"


# ============================================================
# 设置函数
# ============================================================

def setup_logging(level: str = "INFO", log_file: str = None, enable_file: bool = False):
    """设置日志配置
    
    Args:
        level: 日志级别 (DEBUG/INFO/WARNING/ERROR)
        log_file: 日志文件路径（可选）
        enable_file: 是否启用文件日志
    """
    # 确保日志目录存在
    Path("policy_data/logs").mkdir(parents=True, exist_ok=True)
    
    # 更新配置
    config = LOGGING_CONFIG.copy()
    
    # 设置根 logger 级别
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    config["root"]["level"] = numeric_level
    
    # 设置子模块级别
    for logger_name in config["loggers"]:
        config["loggers"][logger_name]["level"] = numeric_level
    
    # 如果启用文件日志
    if enable_file:
        for logger_name in config["loggers"]:
            if "file" not in config["loggers"][logger_name]["handlers"]:
                config["loggers"][logger_name]["handlers"].append("file")
    
    # 如果指定了日志文件
    if log_file:
        config["handlers"]["file"]["filename"] = log_file
        for logger_name in config["loggers"]:
            if "file" not in config["loggers"][logger_name]["handlers"]:
                config["loggers"][logger_name]["handlers"].append("file")
    
    # 应用配置
    logging.config.dictConfig(config)


def get_logger(name: str) -> logging.Logger:
    """获取 logger 实例
    
    Args:
        name: 模块名称（不含 ecopolicy 前缀）
        
    Returns:
        logging.Logger 实例
    """
    # 如果名称已经包含前缀，直接使用
    if name.startswith(LOGGER_PREFIX):
        return logging.getLogger(name)
    
    # 否则添加前缀
    return logging.getLogger(f"{LOGGER_PREFIX}.{name}")


# ============================================================
# 兼容性函数（用于迁移旧代码）
# ============================================================

def get_legacy_logger(old_name: str) -> logging.Logger:
    """获取兼容旧代码的 logger
    
    用于逐步迁移，保持旧 logger 名称可用
    
    Args:
        old_name: 旧的 logger 名称
        
    Returns:
        logging.Logger 实例
    """
    # 映射旧名称到新名称
    name_mapping = {
        "agent.matcher": LOGGER_MATCHER,
        "agent.reporter": LOGGER_REPORTER,
        "agent.roi": LOGGER_ROI,
        "agent.stacker": LOGGER_STACKER,
        "policy_monitor": LOGGER_MONITOR,
        "policy_tracker": LOGGER_TRACKER,
        "batch_matcher": LOGGER_BATCH,
        "scheduler": LOGGER_SCHEDULER,
        "policy_matcher": LOGGER_MATCHER,
    }
    
    new_name = name_mapping.get(old_name, old_name)
    return logging.getLogger(new_name)
