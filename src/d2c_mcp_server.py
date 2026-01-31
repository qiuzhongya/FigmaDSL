#!/usr/bin/env python3
#  d2c_mcp_server.py
import asyncio
import os, sys
import subprocess
import signal 
from typing import Any, Dict
from pathlib import Path
import mcp.server.stdio as stdio
import mcp.types as types
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.models import InitializationOptions
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



src_dir = Path(__file__).parent.resolve()
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

# ---------- 新增：引入纯业务函数 ----------
from .d2c_task import create_task, query_task
from .d2c_config import TaskStatus

# ---------------- 配置 ----------------
DEFAULT_FIGMA_TOKEN = os.getenv("D2C_DEFAULT_FIGMA_TOKEN", "")
DEFAULT_APP_NAME    = os.getenv("D2C_DEFAULT_APP_NAME", "default_app")
POLL_INTERVAL       = 15         # 秒
MAX_WAIT            = 150

server = Server("d2c-mcp")


# ---------------- 工具列表 ----------------
@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="translate_figma",
            description="一键把 Figma 设计翻译成 Kotlin Compose 源码（自动等待完成，返回可复制代码块，并显示工程的路径)；\n"
            "如果用户没有输入token，就使用环境变量里的默认token；\n"
            "自动调用 query_translate_task 工具查询compose代码生产状态，如果成功则返回可直接复制的代码块，否则返回错误信息;\n"
            "打开terminal窗口调用 tail -f 系统命令在聊天框中实时打印最新日志内容直至任务完成",
            inputSchema={
                "type": "object",
                "properties": {
                    "figma_url": {"type": "string", "description": "Figma 设计 URL（含 node-id）"},
                    "figma_token": {"type": "string", "description": "Figma 个人令牌（可选，默认环境变量）"},
                    "app_name": {"type": "string", "description": "应用名（可选，默认环境变量）"},
                },
                "required": ["figma_url"],
            },
        ),
        types.Tool(
            name="query_translate_task",
            description="根据任务 ID 查询翻译结果，返回可复制代码块，并显示工程的路径。（需先调用 translate_figma）;\n"
                        "如果没有指定task_id,就使用上面translate_figma任务返回的task_id;\n"
                        "一轮查询任务还没结束，立马使用query_translate_task启动下一轮查询",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "translate_figma 返回的任务 ID"},
                },
                "required": ["task_id"],
            },
        ),
    ]


def _format_log_tip(log_path: str) -> str:
    """统一格式：如何查看后台日志"""
    if log_path:
        return f"\n\n手动执行 tail -f {log_path} 系统命令可打印最新日志。\n\n"
    else:
        return "\n\n任务日志路径未记录，请联系管理员查看服务端日志。"


# ---------------- 本地轮询直到完成 ----------------
async def wait_for_code(task_id: str) -> list[types.TextContent]:
    """轮询数据库直到任务完成"""
    started = asyncio.get_event_loop().time()
    log_path = ""
    stage_msg = ""
    while True:
        if asyncio.get_event_loop().time() - started > MAX_WAIT:
            return [types.TextContent(type="text", 
                                      text=_format_log_tip(log_path) 
                                      + f"\n正在{stage_msg}\n"
                                      + "任务还在执行中，请使用query_translate_task稍后再查询。")]
        data = query_task(task_id)          # ← 直接查库
        status   = data["status"]
        code_str = data.get("output_code", "")
        zip_url  = data.get("output_url", "")
        stage_msg = data.get("stage_msg", "")
        log_path = zip_url
        if status == TaskStatus.Successed:          # Successed
            if not code_str:
                raise RuntimeError("任务成功但未返回源码")
            code_block = f"```kotlin\n{code_str}\n```"
            extra_info = ""
            if zip_url:
                extra_info = f"\n\n其他资源文件（如图标、主题等）请从工程包下载：\n`{zip_url}/app/src/main/res`"
            logger.info("zip_url: %s, extra_info: %s", zip_url, extra_info)
            output_text = (
                "【输出规则】\n"
                "- 你必须严格按以下要求输出，不得有任何偏差\n"
                "- 不要解释、不要总结、不要添加任何前缀（如“好的”、“代码如下”）\n"
                "- 首先原样输出下方的 Kotlin Compose 代码块（包含 ```kotlin 和 ```）\n\n"
                f"{code_block}"
                f"{extra_info}"
            )
            return [types.TextContent(type="text", text=output_text)]

        if status in (TaskStatus.Creating, TaskStatus.Running):     # Creating / Running
            await asyncio.sleep(POLL_INTERVAL)
            continue

        if status == TaskStatus.CreateFail:
            return [types.TextContent(type="text", text="服务器忙，同时运行任务过多，请稍后重试")]
        if status == TaskStatus.Failed:
            return [types.TextContent(type="text", text=f"任务执行失败，日志：{zip_url or '无'}")]
        raise RuntimeError(f"未知任务状态：{status}")

# ---------------- 工具执行 ----------------
@server.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> list[types.TextContent]:
    if name == "translate_figma":
        try:
            figma_url   = arguments["figma_url"]
            figma_token = arguments.get("figma_token") or DEFAULT_FIGMA_TOKEN
            app_name    = arguments.get("app_name") or DEFAULT_APP_NAME

            if not figma_url:
                return [types.TextContent(type="text", text="缺少必填参数：figma_url")]
            if not figma_token:
                return [types.TextContent(type="text", text="缺少 Figma Token")]
            if not app_name:
                return [types.TextContent(type="text", text="缺少应用名称")]

            logger.info("figma_url: %s, figma_token: %s", figma_url, figma_token)
            result = create_task(figma_url, figma_token, app_name)
            task_id = result["task_id"]        # 只取任务 ID
            log_path = result.get("log_path", "")
            msg = (
                f"任务 `{task_id}` 已提交！任务执行时间预期 10-30 分钟。\n"
                + _format_log_tip(log_path)
                + "Trae 将自动调用 `query_translate_task` 查询结果，请稍候……\n"
            )
            return [types.TextContent(type="text", text=msg)]            
        except Exception as e:
            return [types.TextContent(type="text", text=f"提交翻译任务异常：{e}")]
    elif name == "query_translate_task":
        task_id = arguments["task_id"].strip()
        if not task_id:
            return [types.TextContent(type="text", text="缺少 task_id 参数")]
        return await wait_for_code(task_id)
    raise ValueError(f"Unknown tool: {name}")

# ---------------- 入口 ----------------
async def main() -> None:
    async with stdio.stdio_server() as (reader, writer):
        await server.run(
            reader,
            writer,
            InitializationOptions(
                server_name="d2c-mcp",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

def cli_main() -> None:
    """Synchronous entry point for the 'd2c-mcp-server' command."""
    asyncio.run(main())


if __name__ == "__main__":
    cli_main()