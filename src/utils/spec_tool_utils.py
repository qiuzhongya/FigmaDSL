import os
import json
import subprocess
import requests
import re
import time
import d2c_config
from d2c_logger import tlogger
from typing import Dict, List, Any
from utils.figma_request_cache import read_json_cache, write_json_cache, read_image_json_cache, write_image_json_cache
from copy import deepcopy


def fetch_image_links(file_key: str,
                      node_ids: List[str],
                      token: str) -> Dict[str, str]:
    if d2c_config.FIGMA_REQUEST_CACHE:
        cached = read_image_json_cache(file_key, node_ids)
        if cached is not None:
           return cached
    url = f"https://api.figma.com/v1/images/{file_key}"
    params = {"ids": ",".join(node_ids), "format": "png", "scale": 3}
    headers = {"X-Figma-Token": token}
    resp = requests.get(url, headers=headers, params=params, timeout=30)

    if resp.status_code == 429:
        retry_after = int(resp.headers.get("Retry-After", 60))
        tlogger().error(f"Rate limited (429) -> retry_after={retry_after}")
        raise Exception(f"Figma API rate limited (429) -> retry_after={retry_after}")
    if resp.status_code != 200:
        tlogger().info(f"Get image urls failed, code={resp.status_code}, text={resp.text}")
        return {}
    images: Dict[str, str] = resp.json().get("images", {})
    if d2c_config.FIGMA_REQUEST_CACHE:
        write_image_json_cache(file_key, images)
    return images


def parse_figma_file(node_id: str, figma_token: str, figma_file_key: str):
    if d2c_config.FIGMA_REQUEST_CACHE:
        cached = read_json_cache(figma_file_key, node_id)
        if cached is not None:
            return purge_figma(cached)
    url = f"https://api.figma.com/v1/files/{figma_file_key}/nodes?ids={node_id}"
    headers = {
        "X-FIGMA-TOKEN": figma_token
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 429:
        retry_after = int(response.headers.get("Retry-After", 60))
        print(f"Rate limited (429) on {url} -> retry_after={retry_after}")
        raise Exception(f"Figma Api rate limited (429) on {url} -> retry_after={retry_after}")
    if not response.ok:
        tlogger().info("parse figma file failed: ", response.text)
        raise Exception("parse figma file to json failed")
    node_data = response.json()['nodes'][node_id.replace("-", ":")]
    if d2c_config.FIGMA_REQUEST_CACHE:
        write_json_cache(figma_file_key, node_id, node_data)
    return purge_figma(node_data)


def read_figma_json(figma_json: dict) -> list[dict]:
    document = figma_json['document']
    if not document:
        tlogger().info("no document")
        raise Exception("no document found")
    # check whether the document has children
    if not document.get("children"):
        tlogger().info("no children")
        raise Exception("no children found")
    return document["children"] # [1:], double check from the first or second child

def get_image_node(figma_json: dict) -> dict:
    refs = {}
    def walk(node):
        for fill in node.get("fills", []):
            if fill.get("type") == "IMAGE" and "imageRef" in fill:
                refs[node["id"]] = f"img_{fill['imageRef']}"
                break
        for child in node.get("children", []):
            walk(child)
    walk(figma_json)
    return refs

def read_component_knowledge():
    return {}
    with open("resources/component_knowledge.json", "r") as f:
        return json.load(f)

def is_valid_compose_code(compose_code: str) -> bool:
    """ensure the generatedcompose code is not empty and valid"""
    return len(compose_code) > d2c_config.MINValidComposeCodeLength and "@Preview" in compose_code

def clean_generated_code(compose_code: str) -> str:
    """clean the generated compose code to void the wrong format in Greeting.kt"""
    return compose_code.lstrip("```").lstrip("```kotlin").rstrip("```")

def compile(workspace_dir: str) -> tuple[bool, str]:
    """Compiles the project.
    
    Returns:
        tuple[bool, str]: A tuple containing a boolean indicating whether the compilation was successful,
        and a string containing the error message if the compilation failed.
    """
    tlogger().info("--- COMPILE CODE WITH GRADLEW ---")
    command = ["./gradlew", "updateDebugScreenshotTest"]
    
    try:
        result = subprocess.run(
            command,
            cwd=workspace_dir,
            capture_output=True,
            text=True,
            check=True
        )
        tlogger().info(result.stdout)
        return True, ""
    except subprocess.CalledProcessError as e:
        tlogger().info(f"Compilation failed with error: {e.stderr}")
        return False, e.stderr

def preview(workspace_dir: str) -> tuple[bool, str, str]:
    """Previews the project.
    
    Returns:
        tuple[bool, str]: A tuple containing a boolean indicating whether save screen shot was successful,
        a string containing the error message if the action failed,
        a string containing the path of the screenshot.
    """
    tlogger().info("--- PREVIEW PROJECT WITH GRADLEW ---")
    command = ["./gradlew", ":app:recordPaparazziDebug"]
    try:
        result = subprocess.run(
            command,
            cwd=workspace_dir,
            capture_output=True,
            text=True,
            check=True
        )
        tlogger().info(result.stdout)
        return True, "", os.path.join(workspace_dir, "app/src/test/snapshots/images/com.example.myapplication_ResourcesTest_compose[Default].png")
    except subprocess.CalledProcessError as e:
        tlogger().info(f"Preview failed with error: {e.stderr}")
        return False, e.stderr, ""

def find_used_icons(kotlin_code:str) -> list[str]:
    """
    extract all icons used in kotlin_code.

    icon format:  R.drawable.xxx
    """
    pattern = r"R\.drawable\.([a-zA-Z0-9_]+)"
    icons = re.findall(pattern, kotlin_code)
    return ["app/src/main/res/drawable-xxhdpi/" + icon + ".png" for icon in list(set(icons))]

def remove_useless_icon_files(exported_icons, used_icons, workspace_dir: str):
    need_delete_icons = set(exported_icons) - set(used_icons)
    for icon in need_delete_icons:
        icon_abs_path = os.path.join(workspace_dir, icon)
        if os.path.exists(icon_abs_path):
            os.remove(icon_abs_path)
            tlogger().info(f"remove useless icon {icon}")
        else:
            tlogger().info(f"icon not found: {icon_abs_path}")

def get_safe_filename(raw_name: str):
    safe_name = re.sub(r'[/\\* ]+', '_', raw_name)
    if safe_name != raw_name:
        tlogger().info(f"raw_name: {raw_name}, safe_name: {safe_name}")
    return safe_name

def get_unique_path(directory, base_name):
    """
    若 directory/base_name 已存在，自动加 _1、_2... 直到不冲突。
    返回最终可用的绝对路径。
    """
    name, ext = os.path.splitext(base_name)
    counter = 1
    unique = base_name
    while os.path.exists(os.path.join(directory, unique)):
        unique = f"{name}_{counter}{ext}"
        counter += 1
    return os.path.join(directory, unique)

def purge_figma(figma_json: Any) -> Any:
    document = figma_json.get("document", {})
    view_abb = document.get("absoluteBoundingBox", {})
    view_height = view_abb.get("y") + view_abb.get("height")
    view_width = view_abb.get("x") + view_abb.get("width")
    clear_list = []
    def collect(node):
        if node.get('visible') is False:
            clear_list.append(node.get("id"))
            tlogger().info(f"remove invisible node: {node.get('id')}")
        abb = node.get("absoluteBoundingBox", {})
        if abb:
            if abb.get("width") == 0 or abb.get("height") == 0:
                clear_list.append(node.get("id"))
                tlogger().info(f"remove size 0 node: {node.get('id')}, width: {abb.get('width')}, height: {abb.get('height')}")
                return
            if abb.get("y") >= view_height:
                tlogger().info(f"remove screen down node: {node.get('id')}")
                clear_list.append(node.get("id"))
                return
            if abb.get("x") >= view_width:
                tlogger().info(f"remove screen right node: {node.get('id')}")
                clear_list.append(node.get("id"))
                return
        children = node.get("children", [])
        for child in children:
            collect(child)
    def purge(obj: Any) -> Any:
        if isinstance(obj, dict):
            if obj.get("id") in clear_list:
                return None
            return {k: purge(v) for k, v in obj.items()
                    if purge(v) is not None}
        if isinstance(obj, list):
            return [i for i in map(purge, obj) if i is not None]
        return obj
    collect(document)
    figma_json["document"] = purge(document)
    return figma_json

def split_tree(figma_json: dict):
    abb = figma_json.get("absoluteBoundingBox", {})
    view_width, view_height  = abb.get("width"), abb.get("height")
    view_size = int(view_width) * int(view_height)
    split_size = view_size // 10
    root_node = deepcopy(figma_json)
    sub_figma_list = {}
    def clear_size(node: dict | None) -> dict | None:
        if not node:                       # 防御空节点
            return None
        node_abb = node.get("absoluteBoundingBox") or {}
        node_width  = node_abb.get("width")  or 0
        node_height = node_abb.get("height") or 0
        node_size = int(node_width) * int(node_height)   # 现在仅计算，不再用于过滤
        if node_size < split_size:
            sub_figma_list[node.get("id")] = node
            return None
        if "children" in node and node["children"]:
             node["children"] = [cleared for child in node["children"] if (cleared := clear_size(child)) is not None]
        return node
    clear_size(root_node)
    sub_figma_list[root_node.get("id")] = root_node
    return sub_figma_list


def download_and_save_icon(save_path: str, image_url: str, max_retries: int = 3) -> str:
    # 指数退避延迟（每次重试延迟时间：0.5s → 1s → 2s）
    retry_delays = [0.5, 1, 2]
    
    for retry in range(max_retries + 1):  # 0次（首次）+ 3次重试 = 共4次尝试
        try:
            # 1. 下载图片（设置超时：连接5s，读取10s）
            img_resp = requests.get(
                image_url,
                timeout=(5, 10),
                headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
            )
            img_resp.raise_for_status()  # 主动抛出HTTP错误
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, "wb") as f:
                f.write(img_resp.content)
            
            if retry > 0:
                tlogger().info(f"Save image success after {retry} retries, save_path: {save_path}")
            else:
                tlogger().info(f"Save image success, save_path: {save_path}")
            return True
        
        except Exception as e:
            # 最后一次重试失败，记录错误并返回None
            if retry == max_retries:
                if isinstance(e, requests.exceptions.Timeout):
                    tlogger().error(f"Download timeout after {max_retries} retries, image_url: {image_url}, save path: {save_path}")
                elif isinstance(e, requests.exceptions.HTTPError):
                    tlogger().error(f"Download failed (HTTP error) after {max_retries} retries, image_url: {image_url}, save path: {save_path}, error: {e}")
                else:
                    tlogger().error(f"Save image failed after {max_retries} retries, image_url: {image_url}, save path: {save_path}, error: {str(e)}")
                return False
            # 非最后一次重试，记录警告并延迟重试
            delay = retry_delays[retry]
            tlogger().warning(f"Attempt {retry + 1} failed, retry after {delay}s. image_url: {image_url}, error: {str(e)}")
            time.sleep(delay)
            
def purge_figma_size(figma_json: dict) -> dict:
    """把 Figma JSON 里所有图层信息清空，只保留骨架。"""
    LAYOUT_KEYS = ["componentId", "absoluteBoundingBox", "layoutMode", "primaryAxisAlignItems", "counterAxisAlignItems",
                       "constraints", "layoutGrow", "layoutAlign", "paddingTop", "paddingLeft", "paddingRight", "paddingBottom",
                       "layoutSizingVertical", "layoutSizingHorizontal", "clipsContent", "id", "name", "type",  "children"]
    doc = deepcopy(figma_json.get("document", {}))
    abb = doc.get("absoluteBoundingBox", {})
    view_width, view_height  = int(abb.get("width")), int(abb.get("height"))
    view_size = view_width * view_height
    split_size = view_size / 20
    def clear_size(node: dict | None) -> dict | None:
        if not node:                       # 防御空节点
            return None
        if "children" in node and node["children"]:
             node["children"] = [cleared for child in node["children"] if (cleared := clear_size(child)) is not None]
        node_abb = node.get("absoluteBoundingBox") or {}
        node_width, node_height= int(node_abb.get("width", 0)), int(node_abb.get("height", 0))
        node_size = node_width * node_height   # 现在仅计算，不再用于过滤
        if node_size < split_size and view_width > node_width and view_height > node_height:
            new_node = {}
            new_node.update({k: node[k] for k in LAYOUT_KEYS if k in node})
            if not new_node:
                tlogger().info(f"empty node: {node.get('id', '')}")
                return None
            return new_node
        return node
    figma_json["document"] = clear_size(doc)
    return figma_json