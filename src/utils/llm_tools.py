from langchain_core.tools import tool
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type, before_sleep_log
from openai import RateLimitError
import base64
import os
import shutil
import base64
from typing import Dict, Set, Any
from d2c_logger import tlogger
from utils.spec_tool_utils import fetch_image_links, fetch_ref_image_links, get_safe_filename, get_unique_path, download_and_save_icon
from utils.retry_pool_tools import RetryPool

@tool
def export_figma_icon(figma_nodes: Dict[str, str], image_refs: Set[str],
                      figma_file_key: str, root_node_id: str, figma_token: str, resource_directory: str) -> set:
    """通过 Figma API 导出 icon png 资源"""

    # todo: 优化，加速，每个 figma 文件只导出一次
    if not figma_file_key:
        raise Exception("请设置 figma_file_key")
    tlogger().info(f"export figma icons:f{figma_nodes.values()} ")
    # 1. 获取图片下载链接
    figma_node_ids = figma_nodes.keys()
    tlogger().info(f"Get icon url")
    image_links_map = fetch_image_links(figma_file_key, figma_node_ids, figma_token, root_node_id)
    tlogger().info(f"Get icon url")
    ref_image_links_map = fetch_ref_image_links(figma_file_key, image_refs, figma_token, root_node_id)

    download_tasks = {}
    saved_paths = set() 
    for figma_node_id in figma_nodes.keys():
        image_url = image_links_map.get(figma_node_id)
        if not image_url:
            tlogger().info(f"Get image url failed, node id: {figma_node_id}, icon_name: {figma_nodes[figma_node_id]}")
            continue
        filepath = get_unique_path(resource_directory, get_safe_filename(figma_nodes[figma_node_id]))
        if not filepath.endswith(".png"):
            filepath = figma_nodes[figma_node_id] + ".png"
        save_path = os.path.join(resource_directory, filepath)
        saved_paths.add(f"app/src/main/res/drawable-xxhdpi/{filepath}")
        download_tasks[image_url] = save_path

    for image_ref_id, image_ref_url in ref_image_links_map.items():
        if not image_ref_url:
            tlogger().info(f"Get ref image url failed, node id: {image_ref_id}")
            continue
        image_file_name = f"img_{image_ref_id}.png"
        save_path = os.path.join(resource_directory, image_file_name)
        saved_paths.add(f"app/src/main/res/drawable-xxhdpi/{image_file_name}")
        download_tasks[image_ref_url] = save_path
    
    max_download_workers = min(5, len(download_tasks))  # 控制并发数，避免触发Figma API限流
    retry_pool = RetryPool(max_workers=max_download_workers)
    future_download_task = {}
    for image_url, save_image_path in download_tasks.items():
        download_task = retry_pool.submit(download_and_save_icon, save_image_path, image_url)
        future_download_task[download_task] = [image_url, save_image_path]

    for future_task in future_download_task:
        if not future_task.result():
            download_image_url = future_download_task[future_task][0]
            save_local_path = future_download_task[future_task][1]
            tlogger().info(f"down load from: {download_image_url}, save in: {save_local_path} failed")
    tlogger().info(f"down load all image over!!!")
    return saved_paths


@tool
def list_icons(resource_dir: str):
    """List the icon files in the resource folder.
    
    Args:
        resource_dir (str): the resource folder path.
    """
    if not os.path.exists(resource_dir):
        raise Exception(f"icon directory is empty")
    return os.listdir(resource_dir)

@tool
def rename_icon(resource_dir: str, old_name: str, new_name: str):
    """Rename the icon file in the resource folder.
    
    Args:
        resource_dir (str): the resource folder path.
        old_name (str): The old name of the icon file that has wrong name or absolute issue.
        new_name (str): The new name of the icon file that is correct.
    """
    if not os.path.exists(resource_dir) or not os.path.exists(os.path.join(resource_dir, old_name)):
        raise Exception(f"icon file not found: {resource_dir} or {os.path.join(resource_dir, old_name)}")
    os.rename(os.path.join(resource_dir, old_name), os.path.join(resource_dir, new_name))

@tool
def mock_icon(workspace_dir: str, resource_dir: str, icon_name: str):
    """Mock the placeholder icon in the resource folder.

    Args:
        workspace_dir (str): the workspace folder path.
        resource_dir (str): the resource folder path.
        icon_name (str): The name of the icon file that need to be mocked, copied from the placeholder icon.
    """
    if not os.path.exists(resource_dir):
        os.makedirs(resource_dir, exist_ok=True)
    
    # search the placeholder icon in the other default folder
    possible_densities = ["mipmap-mdpi", "mipmap-hdpi", "mipmap-xhdpi", "mipmap-xxhdpi", "mipmap-xxxhdpi"]
    source = None
    for density in possible_densities:
        candidate = os.path.join(workspace_dir, f"app/src/main/res/{density}/ic_launcher.webp")
        if os.path.exists(candidate):
            source = candidate
            break
    if source is None:
        raise FileNotFoundError("No placeholder icon found in any density")
    target_name = icon_name.rsplit('.', 1)[0] + '.png' if '.' in icon_name else icon_name + '.png'
    target = os.path.join(resource_dir, target_name)
    shutil.copyfile(source, target)

@tool
def read_file(abs_path: str) -> str:
    """Reads the content of a file from the workspace.
    
    Args:
        abs_path (str): The absolute path of the file to read.
    
    Returns:
        str: The content of the file.
    """
    with open(abs_path, "r") as f:
        return f.read().strip()


@tool
def edit_file(file_path: str, old_string: str, new_string: str, replace_all: bool = True):
    """Performs exact string replacements in files. 
    
    Usage:
    - You must use your `read_file` tool at least once in the conversation before editing. This tool will error if you attempt an edit without reading the file. 
    - ALWAYS prefer editing existing files in the codebase. NEVER write new files unless explicitly required.
    - Only use emojis if the user explicitly requests it. Avoid adding emojis to files unless asked.
    - The edit will FAIL if `old_string` is not unique in the file. Either provide a larger string with more surrounding context to make it unique or use `replace_all` to change every instance of `old_string`. 
    - Use `replace_all` for replacing and renaming strings across the file. This parameter is useful if you want to rename a variable for instance.",
    - the old string to be replaced must be explicit code (empty, spaces, newlines, etc. are not allowed).

    Args:
    file_path (str): The absolute path to the file to modify
    old_string (str): The text to replaced must be explicit code (empty, spaces, newlines, etc. are not allowed).
    new_string (str): The text to replace it with (must be different from old_string)
    replace_all (bool): Replace all occurences of old_string (default false)
    """
    content = read_file.invoke({"abs_path": file_path})
    if old_string.strip() not in content:
        raise Exception(f"old_string not found in file {file_path}")
    if old_string.strip() == new_string.strip():
        raise Exception("old_string and new_string must be different")
    old_string_count = content.count(old_string.strip())
    if not replace_all and old_string_count > 1:
        raise Exception("old_string is not unique in file, use replace_all=True to replace all occurrences")
    tlogger().info(f"edit file: {file_path}, replace_all: {replace_all}, length: {len(old_string)}, strip length: {len(old_string.strip())}, count: {old_string_count}\n, old string: {old_string.strip()};\n, replace string:{new_string.strip()};")
    if len(old_string) < 3:
        tlogger().info(f"edit file: {file_path}, old string: {old_string} is too short, {len(old_string)}, strip length: {len(old_string.strip())}")
        raise Exception(f"The string {old_string} to be replaced is too short to match precisely; please provide more context.")
    content = content.replace(old_string.strip(), new_string.strip())
    with open(file_path, "w") as f:
        f.write(content)

@tool
def replace_all(abs_path: str, old_string: str, new_string: str):
    """Replace all occurrences of a string in a file.

    Usage:
    - the old string to be replaced must be explicit code (empty, spaces, newlines, etc. are not allowed).

    Args:
        abs_path (str): The absolute path of the file to modify.
        old_string (str): The string to replaced must be explicit code (empty, spaces, newlines, etc. are not allowed).
        new_string (str): The string to replace with.
    """
    with open(abs_path, "r") as f:
        content = f.read().strip()
    if len(old_string.strip()) == 0:
        raise Exception("old_string is empty, use replace_all=True will create big file")
    replace_cnt = content.count(old_string.strip())
    if replace_cnt > 200:
        tlogger().info(f"replace file: {abs_path};\n, old string: {old_string.strip()};\n, replace string:{new_string.strip()};\n, replace count: {replace_cnt} will cause big file")
    content = content.replace(old_string.strip(), new_string.strip())
    with open(abs_path, "w") as f:
        f.write(content)

@tool
def encode_image(image_path: str) -> str:
    """
    Encodes an image to base64 string.
    """
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        tlogger().error(f"encode image failed {image_path}: {str(e)}")
        raise Exception(f"encode image failed {image_path}: {str(e)}")


# ========== 1. 全局退避参数 ==========
MAX_RETRY = 7               # 最多 7 次
MULTIPLIER  = 2             # 退避倍数
MIN_WAIT    = 1             # 最少等 1 秒
MAX_WAIT    = 60            # 最多等 60 秒


def llm_retry(func):
    return retry(
        wait=wait_exponential(multiplier=MULTIPLIER, min=MIN_WAIT, max=MAX_WAIT),
        stop=stop_after_attempt(MAX_RETRY),
        retry=retry_if_exception_type(RateLimitError),
        reraise=True,
        before_sleep=before_sleep_log(tlogger(), tlogger().level)
    )(func)

# ========== 3. 通用 safe invoke ==========
@llm_retry
def safe_call_llm(chain, messages):
    """
    chain: 任意 LangChain Runnable（bind_tools 后的 ChatModel 也行）
    messages: 列表格式的消息
    """
    return chain.invoke(messages)
