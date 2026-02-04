import os
import requests
import d2c_config
from copy import deepcopy
from d2c_logger import tlogger, logger_task_id
from typing import Dict, List
from utils.figma_request_cache import read_image_json_cache, write_image_json_cache
from utils.spec_tool_utils import get_unique_path, get_safe_filename, download_and_save_icon
from utils.retry_pool_tools import RetryPool


def fetch_ref_image_links(file_key: str,
                          image_refs: List[str],
                          token: str) -> Dict[str, str]:
    if d2c_config.FIGMA_REQUEST_CACHE:
        cached = read_image_json_cache(file_key, image_refs)
        if cached is not None:
           return cached
    url = f"https://api.figma.com/v1/files/{file_key}/images"
    headers = {"X-Figma-Token": token}
    resp = requests.get(url, headers=headers, timeout=30)

    if resp.status_code == 429:
        retry_after = int(resp.headers.get("Retry-After", 60))
        tlogger().error(f"Rate limited (429) -> retry_after={retry_after}")
        raise Exception(f"Figma API rate limited (429) -> retry_after={retry_after}")
    if resp.status_code != 200:
        tlogger().info(f"Get ref image urls failed, code={resp.status_code}, text={resp.text}")
        return {}
    resp.raise_for_status()
    all_images: Dict[str, str] = resp.json().get("meta", {}).get("images", {})
    if not all_images:
            tlogger().info("未找到任何图片")
            return {}
    tlogger().info(f"找到 {len(all_images)} 个图片资源")
    if d2c_config.FIGMA_REQUEST_CACHE:
        write_image_json_cache(file_key, all_images)
    filtered_images = {
        ref: url for ref, url in all_images.items() 
        if ref in image_refs
    }
    missing_refs = set(image_refs) - set(filtered_images.keys())
    if missing_refs:
        tlogger().info(f"以下 image_refs 未找到: {missing_refs}")
    else:
        tlogger().info(f"以下 image_refs 找到: {filtered_images}")
    return filtered_images


def fetch_render_image_links(file_key: str,
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
        tlogger().info(f"Get render image urls failed, code={resp.status_code}, text={resp.text}")
        return {}
    images: Dict[str, str] = resp.json().get("images", {})
    if d2c_config.FIGMA_REQUEST_CACHE:
        write_image_json_cache(file_key, images)
    return images


def figma_resource_url(figma_nodes: Dict[str, str], image_refs: List[str], figma_file_key: str,
                       figma_token: str, resource_directory: str) -> dict:
    """通过 Figma API 导出 icon png 资源"""

    if not figma_file_key:
        raise Exception("请设置 figma_file_key")
    tlogger().info(f"export figma icons:{figma_nodes.values()}, image: {image_refs} ")
    # 1. 获取图片下载链接
    figma_node_ids = figma_nodes.keys()
    render_image_links_map = fetch_render_image_links(figma_file_key, figma_node_ids, figma_token) 
    ref_image_links_map = fetch_ref_image_links(figma_file_key, image_refs, figma_token) 

    download_tasks = {}
    saved_paths = dict() 
    for figma_node_id in figma_nodes.keys():
        render_image_url = render_image_links_map.get(figma_node_id)
        if not render_image_url:
            tlogger().info(f"Get image url failed, node id: {figma_node_id}, icon_name: {figma_nodes[figma_node_id]}")
            continue
        filename = get_unique_path(resource_directory, get_safe_filename(figma_nodes[figma_node_id]))
        if not filename.endswith(".png"):
            filename = figma_nodes[figma_node_id] + ".png"
        save_path = os.path.join(resource_directory, filename)
        saved_paths[figma_node_id] = f"app/src/main/res/drawable-xxhdpi/{filename}"
        download_tasks[render_image_url] = save_path


    for image_ref_id, image_ref_url in ref_image_links_map.items():
        if not image_ref_url:
            tlogger().info(f"Get ref image url failed, node id: {image_ref_id}")
            continue
        image_file_name = f"img_{image_ref_id}.png"
        save_path = os.path.join(resource_directory, image_file_name)
        saved_paths[image_ref_id] = f"app/src/main/res/drawable-xxhdpi/{image_file_name}"
        download_tasks[image_ref_url] = save_path

    if len(download_tasks) > 0:
        max_download_workers = min(30, len(download_tasks))  # 控制并发数，避免触发Figma API限流
        retry_pool = RetryPool(max_workers=max_download_workers, task_id=logger_task_id())
        future_download_task = {}
        for image_url, save_image_path in download_tasks.items():
            download_task = retry_pool.submit(download_and_save_icon, save_image_path, image_url, task_id=logger_task_id())
            future_download_task[download_task] = [image_url, save_image_path]

        for future_task in future_download_task:
            if not future_task.result():
                download_image_url = future_download_task[future_task][0]
                save_local_path = future_download_task[future_task][1]
                tlogger().info(f"down load from: {download_image_url}, save in: {save_local_path} failed")
        tlogger().info(f"down load icon over!!!")
        retry_pool.shutdown()
    return saved_paths

def split_figma_json_size(figma_json: dict):
    abb = figma_json.get("absoluteBoundingBox", {})
    view_width, view_height  = int(abb.get("width")), int(abb.get("height"))
    view_size = view_width * view_height
    split_size = view_size / d2c_config.SegmentationNodeThreshold
    if view_size == 0:
        tlogger().warning("view_size is 0, cannot split")
        return {figma_json.get("id"): figma_json}

    root_node = deepcopy(figma_json)
    sub_figma_list = {}
    def split_walk(node: dict | None) -> dict | None:
        if not node:                       # 防御空节点
            return None
        node_abb = node.get("absoluteBoundingBox", {})
        node_width, node_height = int(node_abb.get("width", 0)), int(node_abb.get("height", 0))
        node_size = node_width * node_height
        if node_size < split_size and view_width > node_width and view_height > node_height:
            sub_figma_list[node.get("id")] = fix_sub_figma_fullscreen(node, view_width, view_height)
            return None
        if "children" in node and node["children"]:
             node["children"] = [cleared for child in node["children"] if (cleared := split_walk(child)) is not None]
        return node
    def split_walk2(node: dict | None) -> dict | None:
        if not node:                       # 防御空节点
            return None
        if "children" in node and node["children"]:
             node["children"] = [cleared for child in node["children"] if (cleared := split_walk2(child)) is not None]
        node_abb = node.get("absoluteBoundingBox", {})
        node_width, node_height = int(node_abb.get("width", 0)), int(node_abb.get("height", 0))
        node_size = node_width * node_height
        if node_size >= view_size // 3:
            sub_figma_list[node.get("id")] = fix_sub_figma_fullscreen(node, view_width, view_height)
            return None
        return node
    split_walk(root_node)
    split_walk2(root_node)
    sub_figma_list[root_node.get("id")] = fix_sub_figma_fullscreen(root_node, view_width, view_height) 
    tlogger().info(f"sub figma length: {len(sub_figma_list)}")
    return sub_figma_list


def fix_sub_figma_fullscreen(figma_json: dict, view_width: int, view_height:int):
    root_node = deepcopy(figma_json)
    def fix_walk(node: dict | None) -> dict | None:
        if not node:                       # 防御空节点
            return None
        node_abb = node.get("absoluteBoundingBox", {})
        node_width, node_height = int(node_abb.get("width", 0)), int(node_abb.get("height", 0))
        if view_width >= node_width:
            node["layoutSizingHorizontal"] ="FILL"
            node["layoutAlign"]= "STRETCH"
        if view_height == node_height:
            node["layoutSizingVertical"] ="FILL"
            node["layoutAlign"]= "STRETCH"
        if "children" in node and node["children"]:
             node["children"] = [cleared for child in node["children"] if (cleared := fix_walk(child)) is not None]
        return node
    return fix_walk(root_node)


def get_node_id(figma_json: dict) -> set[str]:
    node_ids = set()
    def walk(node: dict | None) -> None:
        if not node or not isinstance(node, dict):
            return
        node_id = node.get("id")
        if node_id:
            node_ids.add(node_id)
        for child in node.get("children", []):
            walk(child)

    walk(figma_json)
    return node_ids


def get_image_ref(figma_json: dict) -> dict:
    refs = set()
    def walk(node):
        for fill in node.get("fills", []):
            if fill.get("type") == "IMAGE" and "imageRef" in fill:
                refs.add(fill['imageRef'])
                break
        for child in node.get("children", []):
            walk(child)
    walk(figma_json)
    return refs


def get_component_id(figma_json: dict) -> set[str]:
    component_ids = set()

    def walk(node: dict | None) -> None:
        if not node or not isinstance(node, dict):
            return
        component_id = node.get("componentId")
        if component_id:
            component_ids.add(component_id)
        for child in node.get("children", []):
            walk(child)

    walk(figma_json)
    return component_ids


def get_component_id_map(figma_json: dict, target_node_ids: set[str]) -> dict[str, str]:
    component_id_map = {}

    def walk(node: dict | None) -> None:
        if not node or not isinstance(node, dict):
            return
        node_id = node.get("id")
        component_id = node.get("componentId")
        if component_id and node_id in target_node_ids:
            component_id_map[component_id] = node_id
        for child in node.get("children", []):
            walk(child)

    walk(figma_json)
    return component_id_map



def sub_figma_used_icons(figma_json: dict, sub_figma_json: dict, 
                         all_icon_list: dict[str, str]) -> dict[str, str]:

    main_component_map = get_component_id_map(figma_json, set(all_icon_list.keys()))
    tlogger().info(f"all icon and component id: {main_component_map}")
    sub_node_ids = get_node_id(sub_figma_json)
    sub_component_ids = get_component_id(sub_figma_json)
    sub_image_ids = get_image_ref(sub_figma_json)
    tlogger().info(f"sub figma node id: {sub_node_ids}, component ids: {sub_component_ids}, sub image ids: {sub_image_ids}")
    used_icons = dict()
    for node_id, icon_path in all_icon_list.items():
        if node_id in sub_node_ids and icon_path:  
            used_icons[node_id] = icon_path
        if node_id in sub_image_ids and icon_path:  
            used_icons[node_id] = icon_path

    for comp_id in sub_component_ids:
        if comp_id in main_component_map:
            node_id = main_component_map[comp_id]
            icon_path = all_icon_list.get(node_id)
            if icon_path:
                used_icons[comp_id] = icon_path
    tlogger().info(f"sub figma: {sub_figma_json.get('id')} use icon: {used_icons}")
    return used_icons
