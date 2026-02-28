from concurrent.futures import ThreadPoolExecutor, Future
import time
from d2c_logger import tlogger


class RetryPool:
    """
    带自动重试的线程池
    :param max_workers:  线程池大小
    :param max_retry:    单任务最大重试次数（含首次）
    :param retry_delay:  每次重试间隔(秒)
    """

    def __init__(self, max_workers: int = 6, max_retry: int = 3, retry_delay: float = 1.0, task_id: int = 10000):
        self._pool   = ThreadPoolExecutor(max_workers=max_workers)
        self._max_r  = max_retry
        self._delay  = retry_delay
        self._task_id = task_id

    # ---------- 公共 API ----------
    def submit(self, fn, /, *args, **kwargs) -> Future:
        """
        提交任务，返回 Future；任务异常时会自动重试，直到成功或达到 max_retry。
        如果最终仍失败，Future 会 set_exception，调用方可自行处理。
        """
        future = Future()
        # 包装成可重试函数
        self._pool.submit(self._retry_runner, future, fn, args, kwargs)
        return future

    def shutdown(self, wait=True):
        self._pool.shutdown(wait=wait)

    # ---------- 支持 with 语句 ----------
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown(wait=True)

    # ---------- 内部：重试逻辑 ----------
    def _retry_runner(self, future: Future, fn, args, kwargs):
        """真正在线程里跑的任务包装"""
        for attempt in range(1, self._max_r + 1):
            try:
                result = fn(*args, **kwargs)
                future.set_result(result)
                return
            except Exception as e:
                tlogger(self._task_id).info(f"任务异常 {attempt}/{self._max_r}: {e}")
                if attempt == self._max_r:
                    # 已达重试上限，把异常抛给 Future
                    future.set_exception(e)
                else:
                    time.sleep(self._delay)
