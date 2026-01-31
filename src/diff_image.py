# coding: utf-8

"""
input two images, using OpenAI api to find the differences.
"""
import base64
import openai
from llm import chat_to_openai_gpt4


def image_to_base64(image_path):
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def find_picture_differences(picture_a_path, picture_b_path, base64=False):
    if not base64:
        # 将图片转为 base64
        picture_a_path = image_to_base64(picture_a_path)
        picture_b_path = image_to_base64(picture_b_path)

    # 构造多模态输入
    user_prompt = "请帮我找出这两张图片的不同点，并用简洁的中文列出所有差异。"
    user_content = [
        {"type": "text", "text": user_prompt},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{picture_a_path}", "detail": "high"}},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{picture_b_path}", "detail": "high"}},
    ]
    system_prompt = "你是一个专业的图片分析师，善于找出两张图片的所有不同点。"
    # chat_to_openai_o3 的第三个参数支持多图
    result = chat_to_openai_gpt4(system_prompt, user_prompt, user_content)
    return result

import argparse
from utils.data_process import save_file

def main():
    # 初始化参数解析器
    parser = argparse.ArgumentParser(description='找出两张图片的不同点')
    parser.add_argument('--mode', type=str, choices=['pair', 'jsonl'], default='pair',
                        help='运行模式，pair 表示对比两张图片，jsonl 表示读取 img.jsonl 文件')
    parser.add_argument('--pica', type=str, help='第一张图片的路径，仅在 pair 模式下需要')
    parser.add_argument('--picb', type=str, help='第二张图片的路径，仅在 pair 模式下需要')
    parser.add_argument('--jsonl_path', type=str, help='img.jsonl 文件的路径，仅在 jsonl 模式下需要')
    parser.add_argument('--output', nargs='?', default='output.jsonl',  help='输出的jsonl文件路径 (默认: output.jsonl)')
    args = parser.parse_args()

    if args.mode == 'pair':
        if not args.pica or not args.picb:
            parser.error("在 pair 模式下，--pica 和 --picb 参数是必需的")
        picture_a_path = args.pica
        picture_b_path = args.picb
        diff = find_picture_differences(picture_a_path, picture_b_path)
        print("图片差异:\n", diff)
    elif args.mode == 'jsonl':
        if not args.jsonl_path:
            parser.error("在 jsonl 模式下，--jsonl_path 参数是必需的")
        import json
        # 假设 img.jsonl 每行是一个包含 "image_a" 和 "image_b" 字段的 JSON 对象
        with open(args.jsonl_path, 'r', encoding='utf-8') as f:
            diff_list = []
            cnt = 1
            for line in f:
                diff_dict = {}
                data = json.loads(line)
                picture_a_raw = data.get('screenshotURL_raw')
                picture_a_path = data.get('screenshotURL')

                picture_b_raw = data.get('danceui_screenshotURL_raw')
                picture_b_path = data.get('danceui_screenshotURL')

                if picture_a_path and picture_b_path:
                    diff = find_picture_differences(picture_a_path, picture_b_path, base64=True)
                    print(f"图片 {picture_a_raw} 和 {picture_b_raw} 的差异:\n", diff)

                    diff_dict['id'] = cnt
                    diff_dict['a'] = picture_a_raw
                    diff_dict['b'] = picture_b_raw
                    diff_dict['diff'] = diff

                    cnt = cnt + 1
                else:
                    print("img.jsonl 文件中的行缺少 'image_a' 或 'image_b' 字段")
                
                diff_list.append(diff_dict)
                break
        save_file(diff_list, args.output, file_format='json')

if __name__ == '__main__':
    main()