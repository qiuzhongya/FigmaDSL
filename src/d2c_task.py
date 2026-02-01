from d2c_logger import get_task_logger, clean_threading_context
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
from d2c import create_workflow
import d2c_datautil
import d2c_config
import d2c_msg
import subprocess
from datetime import datetime
from typing import Dict, Tuple, List

_executor = ThreadPoolExecutor() 

def get_git_global_user_info():
    try:
        user_name = subprocess.check_output(
            ["git", "config", "--global", "user.name"],
            encoding="utf-8"
        ).strip()
        user_email = subprocess.check_output(
            ["git", "config", "--global", "user.email"],
            encoding="utf-8"
        ).strip()
        
        return {"user_name": user_name, "user_email": user_email}
    except subprocess.CalledProcessError:
        return {"user_name": None, "user_email": "未配置全局Git用户信息"}


def d2c_exec_task(task_id: str, figma_url: str, figma_token: str):
    """后台任务：获取Figma数据并存储，带独立日志"""
    # 获取该任务的专属日志器
    task_logger = get_task_logger(task_id)
    try:
        # 记录任务开始
        git_user_info = get_git_global_user_info()
        task_logger.info(f"Starting task with UUID: {task_id}")
        task_logger.info(f"Received Figma URL: {figma_url}, token: {figma_token}, "
                         f"git user name: {git_user_info['user_name']},"
                         f"Git user email: {git_user_info['user_email']}")
        state = {
            "task_id": str(task_id),
            "figma_url": figma_url,
            "figma_token": figma_token
        }
        output_log_path = os.path.join(d2c_config.OUTPUT_DIR, f"{task_id}.log")
        d2c_datautil.update_task_log(task_id, output_log_path) 
        app = create_workflow()
        for output in app.stream(state, config={"recursion_limit": d2c_config.RecursionLimit}):
            for key, value in output.items():
                task_logger.info(f"Finished running: {key}")
        task_logger.info("Status updated to 'completed'")
        task_logger.info(f"Task {task_id} execute completed")
    except Exception as e:
        error_msg = str(e)
        task_logger.error(f"Error processing task: {error_msg}", exc_info=True)  # 记录完整异常信息
        task_logger.info(f"Status updated to 'error'")
        d2c_datautil.update_task_complete(task_id, d2c_config.TaskStatus.Failed.value, output_log_path) 
    finally:
        # 清理线程本地存储（关键！避免线程复用导致数据残留
        clean_threading_context()
        # 移除日志处理器，避免资源泄露
        for handler in task_logger.handlers:
            handler.close()
            task_logger.removeHandler(handler)

def task_id_to_number(task_str_id: str)->int:
    try:
        return int(task_str_id)
    except ValueError:
        return -1


def create_task(figma_url: str, figma_token: str, app_name: str) -> Tuple[str, Dict[str, str]]:
    """
    核心：创建任务（无接口依赖）
    返回：(task_id, 状态信息字典)
    """
    task_id = d2c_datautil.id_generator()
    task_logger = get_task_logger(task_id)
    task_logger.info(f"创建任务 {task_id}（app: {app_name}）")

    # 校验运行中任务数量
    running_task_count = d2c_datautil.count_app_running_task(app_name)
    if running_task_count >= d2c_config.MaxUserRunningTask:
        return {
            "task_id": task_id,
            "status": d2c_config.TaskStatus.CreateFail,
            "msg": d2c_msg.D2C_CREATE_MAXIMUM_MSG
        }
    
    output_log_path = os.path.join(d2c_config.OUTPUT_DIR, f"{task_id}.log")
    # 初始化任务数据
    d2c_datautil.add_task(
        app_name=app_name,
        figma_url=figma_url,
        figma_token=figma_token,
        task_id=task_id,
        task_status=d2c_config.TaskStatus.Creating.value,
        create_time=datetime.now(),
        output_url=output_log_path
    )
    loop = asyncio.get_running_loop()
    loop.run_in_executor(_executor, d2c_exec_task, task_id, figma_url, figma_token)

    task_logger.info(f"任务 {task_id} 提交至后台执行")

    return {
        "task_id": str(task_id), 
        "status": d2c_config.TaskStatus.Creating,
        "msg": d2c_msg.D2C_CREATE_OK_MSG,
        "log_path": output_log_path
    }


def query_task(task_id: str) -> Dict[str, object]:
    """
    核心：查询任务状态（无接口依赖）
    返回：任务信息字典
    """
    task_number_id = task_id_to_number(task_id)
    if task_number_id < 0:
        return {
            "task_id": task_id,
            "page_title": "",
            "status": d2c_config.TaskStatus.Unkonw,
            "msg": d2c_msg.D2C_INPUT_TASK_ID_ERROR_MSG
        }

    task_data = d2c_datautil.get_task_by_id(task_number_id)
    if not task_data:
        return {
            "task_id": task_id,
            "page_title": "",
            "status": d2c_config.TaskStatus.Unkonw,
            "msg": d2c_msg.D2C_QUERY_ID_ERROR_MSG
        }

    # 组装返回数据
    task_status = task_data["task_status"]
    output_content = d2c_datautil.get_task_output(task_number_id) if task_status == d2c_config.TaskStatus.Successed.value else ""
    current_stage = d2c_datautil.get_task_stage(task_number_id)
    return {
        "task_id": task_id,
        "page_title": task_data.get("page_title", ""),
        "status": task_status,
        "output_url": task_data.get("output_url", ""),
        "create_time": task_data.get("create_time").strftime("%Y-%m-%d %H:%M:%S") if task_data.get("create_time") else "",
        "output_code": output_content,
        "stage_msg": d2c_msg.get_last_stage_message(current_stage),
        "msg": d2c_msg.get_msg_by_status(task_status)
    }


def query_tasks(app_name: str, offset: int = 0, limit: int = 10) -> Tuple[List[Dict], int]:
    """核心：查询任务列表（无接口依赖）"""
    return d2c_datautil.list_app_tasks(app_name, offset, limit)

"""
def test_upload_output():
    task_id = "b45859ee-5199-46df-bc06-e5f4d012ce52"
    state = {
        "task_id": task_id,
        "workspace_directory": "/tmp/d2c_task_output/%s" % task_id
    }
    import d2c
    d2c.compress_upload(state)
"""