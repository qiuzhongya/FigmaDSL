import d2c_config
from copy import deepcopy
from d2c_logger import tlogger

def split_figma_json_size(figma_json: dict):
    abb = figma_json.get("absoluteBoundingBox", {})
    view_width, view_height  = int(abb.get("width")), int(abb.get("height"))
    view_size = view_width * view_height
    split_size = view_size / d2c_config.SegmentationNodeThreshold
    root_node = deepcopy(figma_json)
    sub_figma_list = {}
    def split_walk(node: dict | None) -> dict | None:
        if not node:                       # 防御空节点
            return None
        node_abb = node.get("absoluteBoundingBox", {})
        node_width, node_height = int(node_abb.get("width", 0)), int(node_abb.get("height", 0))
        node_size = node_width * node_height
        if node_size < split_size and view_width > node_width and view_height > node_height:
            sub_figma_list[node.get("id")] = node
            return None
        if "children" in node and node["children"]:
             node["children"] = [cleared for child in node["children"] if (cleared := split_walk(child)) is not None]
        return node
    split_walk(root_node)
    sub_figma_list[root_node.get("id")] = root_node
    return sub_figma_list