#!/usr/bin/env python3
from typing import List, Optional
from d2c_config import TaskStatus, MaxUserRunningTask


D2C_CREATE_OK_MSG = "Task created successfully, waiting for execution."
D2C_CREATE_UPGRADE_HINT_MSG = "Version upgrade in progress, please try again later!"
D2C_CREATE_MAXIMUM_MSG = "The number of running tasks exceeds the maximum limit %s." % MaxUserRunningTask

D2C_QUERY_ID_ERROR_MSG = "Task ID does not exist, please check."
D2C_QUERY_ID_USER_MISMATHCH_MSG = "You do not have permission to access this task."

D2C_QUERY_RUNNING_MSG = "d2c task is running, please wait."
D2C_QUERY_OK_MSG = "d2c execute ok, please download output from url."
D2C_QUERY_FAIL_MSG = "d2c execute failed, please download output log from url."
D2C_QUERY_ADMIN_STOP_MSG = "d2c task stop by admin, please retry."

D2C_SYSTEM_UPGRADE_ERROR_MSG = "Administrator verification failed! Please check your credentials."
D2C_SYSTEM_UPGRADE_OK_MSG = "Version upgrade triggered successfully. Please upgrade the version and restart the server manually"

D2C_INPUT_TASK_ID_ERROR_MSG = "task_id must be an int, please check input."


def get_msg_by_status(task_status: TaskStatus):
    msg_map = {
        TaskStatus.Creating : D2C_QUERY_RUNNING_MSG,
        TaskStatus.CreateFail : D2C_CREATE_MAXIMUM_MSG,
        TaskStatus.Running : D2C_QUERY_RUNNING_MSG,
        TaskStatus.Successed : D2C_QUERY_OK_MSG,
        TaskStatus.Failed : D2C_QUERY_FAIL_MSG,
        TaskStatus.AdminStop : D2C_QUERY_ADMIN_STOP_MSG
    }
    return msg_map.get(task_status, "")


D2C_STAGE_MSG_FIGMA_JSON = "导出Figma JSON数据"
D2C_STAGE_MSG_INIT_CONTAINER = "初始化容器"
D2C_STAGE_MSG_SAVE_FIGMA_SHOT = "保存Figma截图"
D2C_STAGE_MSG_FIGMA_ICON = "下载Figma图标"
D2C_STAGE_MSG_RECOGNIZE_COMPONENTS = "识别组件类型"
D2C_STAGE_MSG_GET_COMPONENTS = "获取组件知识库"
D2C_STAGE_MSG_CODER = "生成代码（第 %d 次）"
D2C_STAGE_MSG_REPLACE_CODE = "替换代码（第 %d 次）"
D2C_STAGE_MSG_COMPILER = "编译代码（第 %d 次）"
D2C_STAGE_MSG_BUGFIX = "修复错误（第 %d 次）"
D2C_STAGE_MSG_EVALUATOR = "效果评估中"

D2C_STAGE_MSG_REMOVE_USELESS_ICONS = "清理无用图标资源"
D2C_STAGE_MSG_PREVIEWER = "生成代码预览效果"
D2C_STAGE_MSG_COMMIT = "提交代码至版本仓库"
D2C_STAGE_MSG_COMPRESS_UPLOAD = "压缩资源并上传"
D2C_STAGE_MSG_DESTROY_CONTAINER = "销毁容器释放资源"

node_msg_mapping = {

    "export_figma_json": D2C_STAGE_MSG_FIGMA_JSON,
    "export_figma_screenshot": D2C_STAGE_MSG_SAVE_FIGMA_SHOT,
    "export_figma_icons": D2C_STAGE_MSG_FIGMA_ICON,

    "init_container": D2C_STAGE_MSG_INIT_CONTAINER,
    "get_component_knowledges": D2C_STAGE_MSG_GET_COMPONENTS,
    "recognize_components": D2C_STAGE_MSG_RECOGNIZE_COMPONENTS,

    "coder": D2C_STAGE_MSG_CODER, 
    "replace_tester": D2C_STAGE_MSG_REPLACE_CODE,
    "compiler": D2C_STAGE_MSG_COMPILER,
    "bugfix": D2C_STAGE_MSG_BUGFIX,
    "remove_useless_icons": D2C_STAGE_MSG_REMOVE_USELESS_ICONS,

    "previewer": D2C_STAGE_MSG_PREVIEWER,
    "evaluator": D2C_STAGE_MSG_EVALUATOR,
    "commit": D2C_STAGE_MSG_COMMIT,
    "compress_upload": D2C_STAGE_MSG_COMPRESS_UPLOAD,
    "destroy_container": D2C_STAGE_MSG_DESTROY_CONTAINER,
}



def get_last_stage_message(node_list: Optional[List[str]]) -> str:
    """
    获取节点列表最后一个节点对应的消息文本，带次数的消息自动补全次数
    
    参数:
        node_list: 从get_task_stage获取的节点名称列表（可能为None/空列表）
        
    返回:
        最后一个节点的补全消息文本，无有效节点时返回None
    """
    if not node_list:
        return "未知状态"
    
    # 统计目标节点的累计次数（用于补全消息）
    count_map = ["coder", "replace_tester", "compiler", "bugfix"]
    
    last_node = node_list[-1]
     # 获取最后一个节点的原始消息
    stage_msg = node_msg_mapping.get(last_node, "")
    if last_node in count_map:
        exec_count = node_list.count(last_node)
        return stage_msg % exec_count
    else:
        return stage_msg