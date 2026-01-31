import requests
import json
from typing import Optional, Dict, List, Tuple
from datetime import datetime
import d2c_config

# ------------------------------
# 全局配置（根据你的服务实际情况修改）
# ------------------------------
BASE_URL = "http://localhost:8000"  # 你的 FastAPI 服务地址（IP+端口）
ADMIN_NAME = "admin"               # 管理员账号（用于 upgrade_version 接口）
ADMIN_VERIFY = "admin123"          # 管理员验证密钥（需与服务端配置一致）
TIMEOUT = 10                       # 接口请求超时时间（秒）


def create_task(figma_url: str, figma_token: str, user_name: str) -> Tuple[bool, Dict]:
    """
    调用 /d2c/task 接口，创建D2C任务
    :param figma_url: Figma 文件的URL（如 https://www.figma.com/file/xxx/xxx）
    :param figma_token: Figma 访问令牌（需有文件读取权限）
    :param user_name: 提交任务的用户名
    :return: (是否成功, 响应数据字典)
    """
    # 1. 接口参数校验（避免无效请求）
    if not figma_url.startswith("https://www.figma.com/"):
        return False, {"error": "Invalid Figma URL! Must start with 'https://www.figma.com/'"}
    if not figma_token.strip():
        return False, {"error": "Figma token cannot be empty!"}
    if not user_name.strip():
        return False, {"error": "User name cannot be empty!"}

    # 2. 构造请求
    url = f"{BASE_URL}/d2c/task"
    headers = {"Content-Type": "application/json"}  # 声明JSON格式请求体
    payload = {
        "figma_url": figma_url,
        "figma_token": figma_token,
        "user_name": user_name
    }

    # 3. 发送请求并处理响应
    try:
        response = requests.post(
            url=url,
            data=json.dumps(payload),  # 将字典转为JSON字符串
            headers=headers,
            timeout=TIMEOUT
        )
        response.raise_for_status()  # 自动捕获4xx/5xx状态码错误
        result = response.json()     # 解析JSON响应
        return True, result

    except requests.exceptions.RequestException as e:
        # 捕获网络异常（超时、连接失败等）或HTTP错误
        error_msg = f"Request failed: {str(e)}"
        if response:  # 若有响应，补充响应内容
            error_msg += f" | Response: {response.text[:200]}"  # 截取前200字符避免过长
        return False, {"error": error_msg}


def query_task(task_id: str, user_name: str) -> Tuple[bool, Dict]:
    """
    调用 /d2c/task 接口，查询单个任务详情
    :param task_id: 任务唯一标识（创建任务时返回的task_id）
    :param user_name: 任务所属用户名（需与创建时一致）
    :return: (是否成功, 响应数据字典)
    """
    # 1. 参数校验
    if not task_id.strip():
        return False, {"error": "Task ID cannot be empty!"}
    if not user_name.strip():
        return False, {"error": "User name cannot be empty!"}

    # 2. 构造请求（GET请求用params传参）
    url = f"{BASE_URL}/d2c/task"
    params = {
        "task_id": task_id,
        "user_name": user_name
    }

    # 3. 发送请求并处理响应
    try:
        response = requests.get(
            url=url,
            params=params,
            timeout=TIMEOUT
        )
        response.raise_for_status()
        result = response.json()
        return True, result

    except requests.exceptions.RequestException as e:
        error_msg = f"Request failed: {str(e)}"
        if response:
            error_msg += f" | Response: {response.text[:200]}"
        return False, {"error": error_msg}


def query_tasks(user_name: str, offset: int = 0, limit: int = 10) -> Tuple[bool, Dict]:
    """
    调用 /d2c/tasks 接口，分页查询用户的所有任务
    :param user_name: 用户名
    :param offset: 起始位置（默认0，从第1个任务开始）
    :param limit: 每页数量（默认10，最大100，需符合服务端限制）
    :return: (是否成功, 响应数据字典)
    """
    # 1. 参数校验（符合服务端Query参数限制：offset≥0，1≤limit≤100）
    if not user_name.strip():
        return False, {"error": "User name cannot be empty!"}
    if offset < 0:
        return False, {"error": "Offset cannot be negative!"}
    if not (1 <= limit <= 100):
        return False, {"error": "Limit must be between 1 and 100!"}

    # 2. 构造请求
    url = f"{BASE_URL}/d2c/tasks"
    params = {
        "user_name": user_name,
        "offset": offset,
        "limit": limit
    }

    # 3. 发送请求并处理响应
    try:
        response = requests.get(
            url=url,
            params=params,
            timeout=TIMEOUT
        )
        response.raise_for_status()
        result = response.json()
        # 补充分页信息（方便前端展示）
        result["current_page"] = (offset // limit) + 1 if limit != 0 else 1
        result["total_pages"] = (result.get("total_task_count", 0) + limit - 1) // limit
        return True, result

    except requests.exceptions.RequestException as e:
        error_msg = f"Request failed: {str(e)}"
        if response:
            error_msg += f" | Response: {response.text[:200]}"
        return False, {"error": error_msg}


def upgrade_version(admin_name: Optional[str] = None, admin_verify: Optional[str] = None) -> Tuple[bool, Dict]:
    """
    调用 /d2c/task/upgrade_version 接口，触发管理员版本升级（停止所有运行中任务）
    :param admin_name: 管理员账号（默认使用全局配置的ADMIN_NAME）
    :param admin_verify: 管理员验证密钥（默认使用全局配置的ADMIN_VERIFY）
    :return: (是否成功, 响应数据字典)
    """
    # 1. 使用默认管理员信息（若未传入）
    admin_name = admin_name or "ByteD2CAdmin"
    admin_verify = admin_verify or "ByteD2CAdminVerify"

    # 2. 参数校验
    if not admin_name.strip():
        return False, {"error": "Admin name cannot be empty!"}
    if not admin_verify.strip():
        return False, {"error": "Admin verify code cannot be empty!"}

    # 3. 构造请求（POST请求用params传参，因服务端接口定义为路径参数外的普通参数）
    url = f"{BASE_URL}/d2c/task/upgrade_version"
    params = {
        "admin_name": admin_name,
        "admin_verify": admin_verify
    }

    # 4. 发送请求并处理响应（升级操作不可逆，添加二次确认提示）
    #confirm = input(f"WARNING: This operation will stop all running tasks and start version upgrade. Continue? (y/n): ")
    #if confirm.lower() != "y":
    #    return False, {"error": "Operation cancelled by user"}
    #
    try:
        response = requests.post(
            url=url,
            params=params,
            timeout=TIMEOUT
        )
        response.raise_for_status()
        result = response.json()
        return True, result

    except requests.exceptions.RequestException as e:
        error_msg = f"Request failed: {str(e)}"
        if response:
            error_msg += f" | Response: {response.text[:200]}"
        return False, {"error": error_msg}


# ------------------------------
# 测试代码（执行脚本时自动运行）
# ------------------------------
if __name__ == "__main__":
    # 测试参数（根据你的实际数据修改）
    TEST_USER = "test_user_qiuzhongya"          # 测试用户名
    TEST_FIGMA_URL = d2c_config.FigmaSampleUrl  # 测试Figma URL
    TEST_FIGMA_TOKEN = d2c_config.FigmaSampleToken   # 测试Figma Token（需替换为有效Token）

    print("=" * 50)
    print(f"Start testing D2C API (Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
    print("=" * 50)


    # 1. 测试创建任务

    print("\n1. Testing create_task...")
    create_success, create_result = create_task(
        figma_url=TEST_FIGMA_URL,
        figma_token=TEST_FIGMA_TOKEN,
        user_name=TEST_USER
    )
    if create_success:
        print(f"Create task success! Result: {json.dumps(create_result, indent=2)}")
        TEST_TASK_ID = create_result.get("task_id")  # 保存任务ID，用于后续查询
    else:
        print(f"Create task failed! Error: {create_result['error']}")
        TEST_TASK_ID = None  # 若创建失败，后续查询任务跳过


    if not TEST_TASK_ID:
        TEST_TASK_ID = "74cbe307-7a4d-4af8-a852-c2fcba2643b9"
    # 2. 测试查询单个任务（若创建任务成功）
    if TEST_TASK_ID:
        print(f"\n2. Testing query_task (Task ID: {TEST_TASK_ID})...")
        query_single_success, query_single_result = query_task(
            task_id=TEST_TASK_ID,
            user_name=TEST_USER
        )
        if query_single_success:
            print(f"Query task success! Result: {json.dumps(query_single_result, indent=2)}")
        else:
            print(f"Query task failed! Error: {query_single_result['error']}")
    else:
        print("\n2. Skip query_task (create task failed)")

    TEST_TASK_ID = "74cbe307-7a4d-4af8-a852-c2fcba2643b9"
    if TEST_TASK_ID:
        print(f"\n2. Testing query_task (Task ID: {TEST_TASK_ID})...")
        query_single_success, query_single_result = query_task(
            task_id=TEST_TASK_ID.split("-")[0],
            user_name=TEST_USER
        )
        if query_single_success:
            print(f"Query task success! Result: {json.dumps(query_single_result, indent=2)}")
        else:
            print(f"Query task failed! Error: {query_single_result['error']}")
    else:
        print("\n2. Skip query_task (create task failed)")

    if not TEST_TASK_ID:
        TEST_TASK_ID = "354531172585443328"
    if TEST_TASK_ID:
        print(f"\n2. Testing query_task (Task ID: {TEST_TASK_ID})...")
        query_single_success, query_single_result = query_task(
            task_id=TEST_TASK_ID,
            user_name=TEST_USER+"."
        )
        if query_single_success:
            print(f"Query task success! Result: {json.dumps(query_single_result, indent=2)}")
        else:
            print(f"Query task failed! Error: {query_single_result['error']}")
    else:
        print("\n2. Skip query_task (create task failed)")

    #import sys; sys.exit()
    # 3. 测试查询任务列表
    print(f"\n3. Testing query_tasks (User: {TEST_USER})...")
    query_list_success, query_list_result = query_tasks(
        user_name=TEST_USER,
        offset=0,
        limit=5  # 每页查5个任务
    )
    if query_list_success:
        print(f"Query tasks success! Result: {json.dumps(query_list_result, indent=2)}")
    else:
        print(f"Query tasks failed! Error: {query_list_result['error']}")
    #sys.exit()
    # 4. 测试版本升级（谨慎执行！会停止所有运行中任务）
    print("\n4. Testing upgrade_version (Admin operation)...")
    upgrade_success, upgrade_result = upgrade_version("wrong_admin_name")
    if upgrade_success:
        print(f"Upgrade version success! Result: {json.dumps(upgrade_result, indent=2)}")
    else:
        print(f"Upgrade version failed! Error: {upgrade_result['error']}")
    upgrade_success, upgrade_result = upgrade_version()
    if upgrade_success:
        print(f"Upgrade version success! Result: {json.dumps(upgrade_result, indent=2)}")
    else:
        print(f"Upgrade version failed! Error: {upgrade_result['error']}")

    print("\n" + "=" * 50)
    print("All tests completed!")
    print("=" * 50)