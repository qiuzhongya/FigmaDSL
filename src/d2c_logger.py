import logging
from logging.handlers import RotatingFileHandler
import os
import threading
import functools
import d2c_config
import time

# 初始化线程本地存储（每个线程独立的数据空间）
task_context = threading.local()

def get_task_logger(task_id: int) -> logging.Logger:
    """为特定任务创建或获取日志记录器"""
    logger = logging.getLogger(f"task_{task_id}")
    task_context.logger = logger

    # 避免重复添加处理器
    if logger.handlers:
        return logger
    
    # 设置日志格式
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    # 创建文件处理器，每个任务一个日志文件
    log_file = os.path.join(d2c_config.OUTPUT_DIR, f"{task_id}.log")
    os.makedirs(d2c_config.OUTPUT_DIR, exist_ok=True)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 1MB
        backupCount=5,         # 最多保留3个备份
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    
    # 添加处理器并设置级别
    logger.addHandler(file_handler)
    logger.setLevel(logging.INFO)
    
    return logger


def clean_threading_context():
    if hasattr(task_context, "logger"):
        del task_context.logger

def tlogger() -> logging.Logger:
    """从线程本地存储获取当前任务的日志器（全局可用）"""
    try:
        if not hasattr(task_context, "logger"):
            task_context.logger = get_task_logger(10000)
        # 从线程本地存储中获取日志器
        return task_context.logger
    except AttributeError:
        raise RuntimeError("No logger found in current context. Ensure task is initialized.")
    

def log_duration(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        tlogger().info(f"{func.__name__} stage 耗时: {elapsed:.3f}s")
        return result
    return wrapper