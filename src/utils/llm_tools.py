from langchain_core.tools import tool
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type, before_sleep_log
from openai import RateLimitError
import base64
import os
import shutil
import base64
from typing import Dict, List
from d2c_logger import tlogger
from utils.figma_tools import figma_resource_url

@tool
def export_figma_icon(figma_nodes: Dict[str, str], image_refs: List[str], figma_file_key: str,
                      figma_token: str, resource_directory: str) -> dict:
    """通过 Figma API 导出 icon png 资源"""
    tlogger().info(f"image ref id: {image_refs}")
    return figma_resource_url(figma_nodes, image_refs, figma_file_key, figma_token, resource_directory)


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