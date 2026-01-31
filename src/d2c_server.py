#!/usr/bin/env python3
# d2c_server_file.py  (1.18.0 官方示例结构)
from typing import Optional, Dict, List

import uvicorn  # 新增：导入uvicorn，避免main函数中未定义
from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel

from d2c_task import create_task, query_task, query_tasks


app = FastAPI(title="D2C Task Management API", version="1.0")


# ------------------------------
# 请求模型定义
# ------------------------------
class CreateTaskRequest(BaseModel):
    figma_url: str
    figma_token: str
    app_name: str

# ------------------------------
# 核心API接口（修复后）
# ------------------------------
@app.post("/d2c/task", response_model=Dict[str, str])
async def create_task_api(req: CreateTaskRequest):
    return create_task(req.figma_url, req.figma_token, req.app_name)

@app.get("/d2c/tasks", response_model=Dict[str, object])
async def query_tasks_api(
    app_name: str,
    offset: Optional[int] = Query(0, ge=0),
    limit: Optional[int] = Query(10, ge=1, le=1000)
):
    """REST 接口：查询任务列表（直接调用核心逻辑）"""
    try:
        tasks, total = query_tasks(app_name, offset, limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    for task in tasks:
        task["task_id"] = str(task["task_id"])
    return {"tasks": tasks, "total_task_count": total, "offset": offset, "limit": limit}


@app.get("/d2c/task", response_model=Dict[str, object])
async def query_task_api(task_id: str):
    """REST 接口：查询单个任务（直接调用核心逻辑）"""
    return query_task(task_id)


# ------------------------------
# 服务启动入口（修复模块名引用）
# ------------------------------
if __name__ == "__main__":
    # 注意：模块名需与当前脚本文件名一致（如脚本名为d2c_api.py，则为"d2c_api:app"）
    uvicorn.run(
        app=app,
        host="::",  # 允许外部访问
        port=7654,  # 服务端口
        reload=False,  # 开发模式：代码修改自动重启（生产环境禁用）
        log_level="info"  # 日志级别：便于调试
    )
