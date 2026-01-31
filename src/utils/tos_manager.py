import os
import uuid
from datetime import datetime

import bytedtos

# PSM、Cluster、Idc、Accesskey 和 Bucket 可在 TOS 用户平台 > Bucket 详情 > 概览页中查找。具体查询方式详见方式二：通过 “psm+idc” 访问 TOS 桶 。
ak = "9Y99FV8IGG8S6ONUNH65"
bucket_name = "atk"
endpoint = "tos-cn-north.byted.org"
tos_idc = "lf"
obj_key = "test/test"


def get_tos_url(task_start_time: int, task_id: str, step: str) -> str:
    date_str = datetime.fromtimestamp(task_start_time / 1000).strftime("%Y%m%d")
    return get_full_tos_url(f"{date_str}/{task_id}/{step}")


def get_full_tos_url(tos_name: str) -> str:
    return f"http://tosv.byted.org/obj/atk/{tos_name}"


def upload_zip_to_tos(zip_file_path: str, custom_name: str = None) -> str:
    """
    上传zip文件到TOS，文件路径包含日期和UUID
    
    Args:
        zip_file_path: 本地zip文件路径
        custom_name: 自定义文件名前缀，如果不提供则使用原文件名
    
    Returns:
        str: 上传成功返回TOS文件路径，失败返回空字符串
    """
    try:
        # 生成日期字符串
        date_str = datetime.now().strftime("%Y%m%d")

        # 生成UUID
        file_uuid = str(uuid.uuid4())

        # 获取文件名
        if custom_name:
            filename = f"{custom_name}_{file_uuid}.zip"
        else:
            base_name = os.path.splitext(os.path.basename(zip_file_path))[0]
            filename = f"{base_name}_{file_uuid}.zip"

        # 构建TOS文件路径：d2c/日期/UUID/文件名
        tos_file_path = f"d2c/{date_str}/{filename}"

        # 读取zip文件内容
        with open(zip_file_path, 'rb') as f:
            file_content = f.read()

        # 创建TOS客户端并上传
        client = bytedtos.Client(bucket_name, ak, endpoint=endpoint)
        resp = client.put_object(tos_file_path, file_content)

        print("upload_zip_to_tos succ. code: {}, request_id: {}, file_path: {}".format(
            resp.status_code,
            resp.headers[bytedtos.consts.ReqIdHeader],
            get_full_tos_url(tos_file_path)
        ))

        return get_full_tos_url(tos_file_path)

    except bytedtos.TosException as e:
        print("upload_zip_to_tos failed. code: {}, request_id: {}, message: {}".format(e.code, e.request_id, e.msg))
        return ""
    except FileNotFoundError:
        print("upload_zip_to_tos failed. File not found: {}".format(zip_file_path))
        return ""
    except Exception as e:
        print("upload_zip_to_tos failed. Unexpected error: {}".format(str(e)))
        return ""


if __name__ == "__main__":
    # get_content_from_tos("https://tosv.byted.org/obj/atk/kmpilot_Aweme/rc/develop/zhouxingyu.zoe@bytedance.com/1755587268228/business_modules/IM/Business/douyin_ability_impl/src/main/java/com/im/platform/basic/MobEventAbilityImpl.kt")

    upload_zip_to_tos("/Users/deskid/git/compose_d2c/current_workflow.svg")

    # try:
    #
    #     client = bytedtos.Client(bucket_name, ak, endpoint=endpoint)
    #     resp = client.put_object(obj_key, "Hello World")
    #     print("action succ. code: {}, request_id: {}".format(resp.status_code, resp.headers[bytedtos.consts.ReqIdHeader]))
    # except bytedtos.TosException as e:
    #     # 操作失败，捕获异常，可从返回信息中获取详细错误信息
    #     # request id 可定位具体问题，强烈建议日志中保存
    #     print("action failed. code: {}, request_id: {}, message: {}".format(e.code, e.request_id, e.msg))
