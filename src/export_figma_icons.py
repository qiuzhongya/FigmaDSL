# coding: utf-8

"""
识别并导出figma文件中的 icon
"""

import os
import time
import requests
from IPython.display import Image, display
import subprocess

import json
from langchain.chat_models import init_chat_model
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import AnyMessage
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt.chat_agent_executor import AgentState
from langgraph.checkpoint.memory import InMemorySaver
from pydantic.v1 import BaseModel, Field
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langchain_core.tools import tool
from pydantic.v1 import Field
from typing import Annotated, List
from llm import init_gpt_gemini_model


class ExportIcon(BaseModel):
    '''the icon need to be exported'''
    figma_node_id: str = Field(description="figma node id")
    icon_file_name: str = Field(description="icon file name, end with '.png'")


class ExportIcons(BaseModel):
    """export icons from figma file"""
    icons: List[ExportIcon]


class IconExportState(BaseModel):
    figma_file_key: str
    figma_node_json: dict
    icon_info: list = None  # 识别出的 icon 信息，List[dict]
    icon_path: list = None   # 导出后的 icon 路径，List[str]


# checkpointer = InMemorySaver()

if not os.getenv("ANTHROPIC_API_KEY"):
    raise Exception("env ANTHROPIC_API_KEY not found")

#model = init_chat_model(
#    "anthropic:claude-3-7-sonnet-latest",
#    temperature=0,
#)
model = init_gpt_gemini_model()

# 建议通过环境变量传递 Figma Token 和 file_key
FIGMA_TOKEN = "figd_rwuOMYJDUtN_BT7Xg-Lx5RVjZLv1fM7Q5eQAwjZk"
FIGMA_FILE_KEY = os.environ.get("FIGMA_FILE_KEY", "lEIy4VXyF0rnimZnnfYqqB")

icon_count = 0

@tool
def export_figma_icon(figma_node_id: str, figma_file_key: str, icon_file_name: str) -> str:
    """通过 Figma API 导出 icon png 资源

    arguments:
    - figma_node_id: figma node id
    - figma_file_key: figma file key
    - icon_file_name: filename to save icon, ends with ".png"
    """
    global icon_count
    icon_count += 1
    if not figma_file_key:
        raise Exception("请设置 FIGMA_FILE_KEY 环境变量")

    # 1. 获取图片下载链接
    url = f"https://api.figma.com/v1/images/{figma_file_key}?ids={figma_node_id}&format=png&scale=3"
    headers = {"X-Figma-Token": FIGMA_TOKEN}
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        print(f"获取图片链接失败: {resp.text}")
        return ""

    image_json = resp.json()
    image_url = image_json.get("images", {}).get(figma_node_id)
    if not image_url:
        print(f"未获取到图片下载链接: {image_json}")
        return ""

    # 2. 下载图片
    img_resp = requests.get(image_url)
    if img_resp.status_code != 200:
        print(f"下载图片失败: {img_resp.text}")
        return ""

    # 3. 保存图片
    save_dir = "res/drawable-xxhdpi"
    os.makedirs(save_dir, exist_ok=True)
    if not icon_file_name.endswith(".png"):
        save_path = os.path.join(save_dir, f"{icon_file_name}.png")
    else:
        save_path = os.path.join(save_dir, icon_file_name)

    with open(save_path, "wb") as f:
        f.write(img_resp.content)
    return save_path


def get_system_prompt()-> str:
    sp = """## 角色
你是一个经验丰富的 Android 工程师，擅长 Compose 开发和还原设计稿。

## 任务
识别并导出 figma json 节点中的 icon。

## 判断逻辑
判断研发在还原设计效果时，该节点是否包含需要导出 png 资源图片的 icon。如果是，使用工具导出 icon。

## 工具使用
### export_figma_icon
作用：导出 figma 中的 icon，并将 icon 保存到 res/drawable-xxhdpi/ 目录

你需要判断 figma node 是否包含应该被导出 icon 的图片。如果有，你需要调用 export_figma_icon 工具，否则则结束。
"""
    return sp


def read_figma_json(filepath: str) -> list[dict]:
    print(f"read figma json from {filepath}")
    with open(filepath) as f:
        content = f.read()
        json_content = json.loads(content)
        document = json_content['document']
        if not document:
            print("no document")
            raise Exception("no document found")
        return document["children"][1:]


tools = [export_figma_icon]
llm_with_tools = model.bind_tools(tools)


def recognize_icon_block(state: IconExportState) -> ExportIcons:
    node_json_str = json.dumps(state.figma_node_json, indent=4, ensure_ascii=False)
    user_prompt = f"node json is:\n```{node_json_str}\n```"
    export_icons_obj = llm_with_tools.with_structured_output(ExportIcons).invoke([
        ("system", get_system_prompt()),
        ("human", user_prompt),
    ])
    return export_icons_obj


def export_icon_block(state: IconExportState) -> IconExportState:
    if not state.icon_info:
        return state
    icon_paths = []
    for icon_info in state.icon_info:
        path = export_figma_icon.invoke({
            "figma_node_id": icon_info["figma_node_id"],
            "figma_file_key": state.figma_file_key,
            "icon_file_name": icon_info["icon_file_name"],
        })
        if path:
            icon_paths.append(path)
    return IconExportState(
        figma_file_key=state.figma_file_key,
        figma_node_json=state.figma_node_json,
        icon_info=state.icon_info,
        icon_path=icon_paths,
    )


def export_figma_icons(figma_json_filepath)->list:
    """
    导出figma icons
    
    返回形如 ["res/drawable-xxhdpi/ic_arrow_small_dt.png"] 的列表
    """

    # 删除 "res/drawable-xxhdpi" 目录下所有的 .png 文件
    # rm -rf res/drawable-xxhdpi/*.png
     # 定义命令
    command = ["rm", "-rf", "res/res_drawable-xxhdpi/*.png"]

    # 执行命令
    try:
        subprocess.run(command, check=True)
        print("删除打包文件夹下的 png 文件成功")
    except subprocess.CalledProcessError as e:
        print(f"删除打包文件夹下的 png 文件失败{e}")
        return []

    node_jsons = read_figma_json(figma_json_filepath)
    exported_icons = []
    for idx, node_json in enumerate(node_jsons):
        print(f"Processing node {idx}: type={node_json.get('type')}, name={node_json.get('name')}")
        builder = StateGraph(IconExportState)
        builder.add_node("recognize_icon", recognize_icon_block)
        builder.add_node("export_icon", export_icon_block)
        builder.add_edge(START, "recognize_icon")
        builder.add_edge("recognize_icon", "export_icon")
        builder.add_edge("export_icon", END)
        builder.set_entry_point("recognize_icon")
        builder.set_finish_point("export_icon")
        graph = builder.compile()
        result = graph.invoke({
            "figma_file_key": FIGMA_FILE_KEY,
            "figma_node_json": node_json
        })
        time.sleep(60)

        if "icon_path" in result and result["icon_path"] and len(result["icon_path"]):
            for icon_path in result["icon_path"]:
                print(f"icon 导出成功: {icon_path}")
                exported_icons.append(icon_path)
        
        # if idx == 2:
            # break

    return exported_icons


def main():
    exported_icons = export_figma_icons("dataset/figma_file0.json")
    print(exported_icons)


if __name__ == '__main__':
    main()
