import threading
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from d2c_logger import tlogger

# ---------- 线程安全内存表 ----------
_lock = threading.Lock()
_tasks: Dict[int, dict] = {}          # task_id -> 任务字典
_tasks_output_code: Dict[int, str] = {}          # task_id -> output content代码
_tasks_stage: Dict[int, List[str]] = {}          # task_id -> stage
_app_index: Dict[str, List[int]] = {}  # app_name -> [task_id, ...]

# ---------- 工具函数 ----------
def _now() -> datetime:
    return datetime.now()

def id_generator() -> datetime:
    return int(_now().timestamp() * 1000) & 0x7FFFFFFFFFFFFFFF

def add_task(app_name: str,
             figma_url: str,
             figma_token: str,
             task_id: Optional[int] = None,
             task_status: int = 0,
             create_time: Optional[datetime] = None,
             page_title: Optional[str] = None,
             output_url: Optional[str] = None) -> int:
    if task_id is None:
        # 用雪花算法生成，这里先简单用时间戳毫秒
        task_id = id_generator()
    if create_time is None:
        create_time = _now()

    with _lock:
        _tasks[task_id] = {
            "task_id": task_id,
            "create_time": create_time,
            "end_time": None,
            "app_name": app_name,
            "figma_url": figma_url,
            "page_title": page_title or "",
            "figma_token": figma_token,
            "task_status": task_status,
            "output_url": output_url or "",
        }
        _app_index.setdefault(app_name, []).append(task_id)
        tlogger().info(f"[内存] 新增任务 {task_id}")
    return task_id

def update_task(task_id: int,
                page_title: Optional[str] = None,
                task_status: Optional[int] = None,
                output_url: Optional[str] = None,
                end_time: Optional[datetime] = None) -> None:
    with _lock:
        task = _tasks.get(task_id)
        if not task:
            return
        if page_title is not None:
            task["page_title"] = page_title
        if task_status is not None:
            task["task_status"] = task_status
        if output_url is not None:
            task["output_url"] = output_url
        if end_time is not None:
            task["end_time"] = end_time
        tlogger().info(f"[内存] 更新任务 {task_id}")

def update_page_title(task_id: int,
                      page_title: str,
                      task_status: int) -> None:
    """更新任务的页面标题和状态"""
    update_task(task_id, page_title=page_title, task_status=task_status)

def get_task_by_id(task_id: int) -> Optional[dict]:
    with _lock:
        return _tasks.get(task_id)

def list_app_tasks(app_name: str, offset: int = 0, limit: int = 20) -> Tuple[List[dict], int]:
    with _lock:
        task_ids = _app_index.get(app_name, [])
        total = len(task_ids)
        # 按 create_time 倒序
        tasks = [_tasks[tid] for tid in task_ids if tid in _tasks]
        tasks.sort(key=lambda x: x["create_time"], reverse=True)
        return tasks[offset:offset + limit], total

def count_app_running_task(app_name: str) -> int:
    RUNNING = {0, 2}          # 与原业务保持一致
    with _lock:
        task_ids = _app_index.get(app_name, [])
        return sum(1 for tid in task_ids if _tasks.get(tid, {}).get("task_status") in RUNNING)


def update_task_log(task_id: int,    
                    output_url: Optional[str] = None) -> None:
    """更新任务日志存储位置（执行失败或者未执行完毕时，output为日志）"""
    update_task(task_id, output_url=output_url)


def update_task_complete(task_id: int,
                         task_status: int,
                         output_url: Optional[str] = None,
                         end_time: Optional[datetime] = None) -> None:
    """更新任务完成状态（成功或失败）"""
    if end_time is None:
        end_time = datetime.now()
    update_task(task_id, task_status=task_status, output_url=output_url, end_time=end_time)


def set_task_output(task_id: int,
             output_code: str) -> None:
    with _lock:
        _tasks_output_code[task_id] = output_code


def get_task_output(task_id: int) -> str:
    with _lock:
        return _tasks_output_code.get(task_id)


def update_task_stage(task_id: int, new_stage: str) -> None:
    with _lock:
        if task_id not in _tasks_stage:
            _tasks_stage[task_id] = []
        _tasks_stage[task_id].append(new_stage)


def get_task_stage(task_id: int) -> str:
    with _lock:
        return _tasks_stage.get(task_id)