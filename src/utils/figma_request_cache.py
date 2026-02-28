import os
import json
from typing import Any, Dict, Optional, List, Set
from d2c_logger import tlogger

cache_dir = "/tmp/d2c_json_cache"

# ------------- 缓存工具 -------------
def json_cache_path(file_key: str, node_id: str) -> str:
    """本地缓存文件路径"""
    os.makedirs(cache_dir, exist_ok=True)
    # 与 Figma 内部 ID 格式保持一致
    sanitized_node = node_id.replace("-", ":")
    return os.path.join(cache_dir, f"{file_key}_{sanitized_node}.json")


def read_json_cache(file_key: str, node_id: str) -> Optional[Dict[str, Any]]:
    """返回缓存的 dict，失败或不存在返回 None"""
    path = json_cache_path(file_key, node_id)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            tlogger().info(f"read json {file_key}_{node_id} from cache")
            return json.load(f)   # 直接反序列化成 dict
    except Exception:
        return None


def write_json_cache(file_key: str, node_id: str, data: Dict[str, Any]) -> None:
    """把 dict 落盘，失败不抛异常"""
    path = json_cache_path(file_key, node_id)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        # 这里可以接日志系统
        pass


# ------------- 缓存工具 -------------
def image_json_cache_path(file_key: str, root_node_id: str) -> str:
    return f"{cache_dir}/{file_key}_image_link_cache_{root_node_id}.json"


def read_image_json_cache(file_key: str, root_node_id: str,
                          needed_nodes: Set[str]) -> Optional[Dict[str, str]]:
    """
    返回 needed_nodes 对应的 images 字段 dict；缓存必须包含所有 needed_nodes 且值不为 null 才算命中
    """
    path = image_json_cache_path(file_key, root_node_id)
    if not os.path.isfile(path):
        tlogger().info(f"link cache file {path} for figma not exist")
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            images: Dict[str, str] = json.load(f).get("images", {})

        # 只提取 needed_nodes 中值不为 null 的条目
        result = {}
        for n in needed_nodes:
            if n not in images:
                tlogger().info(f"link cache not find key {n} for figma not exist")
                return None  # 缺少某个节点，缓存未命中
            if images[n] is None:
                tlogger().info(f"link cache not find key {n} for figma is None")
                return None  # 值为 null，缓存未命中
            result[n] = images[n]
        tlogger().info(f"read image download link cache for figma key {file_key}, nodes: {len(result)}")
        return result
    except Exception:
        pass
    return None


def write_image_json_cache(file_key: str, root_node_id: str, new_images: Dict[str, str]) -> None:
    """增量合并并落盘；失败不抛"""
    path = image_json_cache_path(file_key, root_node_id)
    try:
        # 读旧缓存
        old = {}
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                old = json.load(f).get("images", {})
        # 合并
        old.update(new_images)
        # 写回
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"images": old}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
