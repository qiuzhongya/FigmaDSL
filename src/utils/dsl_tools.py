import d2c_config
from copy import deepcopy
from d2c_logger import tlogger


def build_dsl_tree(figma_json: dict):
    root_node = deepcopy(figma_json)
    def walk(node):
        coder_tree = {}
        LAYOUT_KEYS = ["id", "name", "type", "componentId", 
                       "absoluteBoundingBox", "layoutMode", "primaryAxisAlignItems", "counterAxisAlignItems", "constraints", 
                       "layoutGrow", "layoutAlign", "paddingTop", "paddingLeft", "paddingRight", "paddingBottom",
                       "layoutSizingVertical", "layoutSizingHorizontal", "clipsContent"]
        coder_tree.update({k: node[k] for k in LAYOUT_KEYS if k in node})
        coder_tree["children"] = []
        children = node.get("children", [])
        for child in children:
            sub_coder_tree = walk(child)
            coder_tree["children"].append(sub_coder_tree)
        return coder_tree
    coder_tree = walk(root_node)
    return coder_tree

def update_dsl_tree(dsl_tree: dict, update_node_id: str, coder_content: str):
    node_id = dsl_tree.get("id")
    if node_id == update_node_id:
        dsl_tree["code_content"] = coder_content
        return True
    for child in dsl_tree.get("children", []):
        if update_dsl_tree(child, update_node_id, coder_content):
            return True
    return False