import os
import json
from typing import Any, Dict, Optional, List
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
def image_json_cache_path(file_key: str) -> str:
    return f"{cache_dir}/{file_key}_image_link_cache.json"


def read_image_json_cache(file_key: str,
                          needed_nodes: List[str]) -> Optional[Dict[str, str]]:
    """返回 images 字段 dict；缓存必须包含所有 needed_nodes 才算命中"""
    path = image_json_cache_path(file_key)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            images: Dict[str, str] = json.load(f).get("images", {})
        if all(n in images for n in needed_nodes):
            tlogger().info(f"read image download link cache for figma key {file_key}")
            return images
        else:
            hit = {n: images[n] for n in needed_nodes if n in images}
            if not hit:                # 一个都没命中
                return None
            tlogger().info(f"partial hit: {len(hit)}/{len(needed_nodes)} images for {file_key}")
            return hit
    except Exception:
        pass
    return None


def write_image_json_cache(file_key: str, new_images: Dict[str, str]) -> None:
    """增量合并并落盘；失败不抛"""
    path = image_json_cache_path(file_key)
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