import csv
import requests
import json
import base64


def read_csv_with_reader(file_path):
    """
    使用 csv.reader 读取 CSV 文件
    :param file_path: CSV 文件的路径
    :return: 包含 CSV 文件所有行数据的列表
    """
    data = []
    try:
        with open(file_path, mode='r', encoding='utf-8') as file:
            csv_reader = csv.reader(file)
            for row in csv_reader:
                data.append(row)
    except FileNotFoundError:
        print(f"文件 {file_path} 未找到。")
    except Exception as e:
        print(f"读取文件时出错: {e}")
    return data

import json

def parser_data(reader_data):
    parsed_data = []
    cnt = 0
    for item in reader_data:
        if cnt == 0:
            cnt += 1
            continue
        # 提取第一列的 traceId
        json_data = json.loads(item[0])
        trace_id = json_data.get('traceId', '')

        # 提取第二列的 screenshotURL
        json_data = json.loads(item[1])
        screenshot_url = json_data.get('screenshotURL', '')

        # 提取第五列中 DanceUI 和 SwiftUI 里的 screenshotURL
        json_data = json.loads(item[4])
        code_quality_check = json_data.get('codeQualityCheck', {})
        danceui_screenshot_url = code_quality_check.get('DanceUI', {}).get('data', {}).get('screenshotURL', '')
        swiftui_screenshot_url = code_quality_check.get('SwiftUI', {}).get('data', {}).get('screenshotURL', '')

        print(f"第一列的 traceId: {trace_id}")
        print(f"第二列的 screenshotURL: {screenshot_url}")
        print(f"第五列中 DanceUI 的 screenshotURL: {danceui_screenshot_url}")
        print(f"第五列中 SwiftUI 的 screenshotURL: {swiftui_screenshot_url}")

        parsed_data.append({
                "traceId": trace_id,
                "screenshotURL": screenshot_url,
                "danceui_screenshotURL": danceui_screenshot_url,
                "swiftui_screenshotURL": swiftui_screenshot_url
        })
    return parsed_data

def download_image_to_base64(url):
    """
    下载图片并将其转换为 Base64 编码
    :param url: 图片的下载链接
    :return: 图片的 Base64 编码字符串，如果下载失败则返回空字符串
    """
    if not url:
        return ''
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # 检查请求是否成功
        return base64.b64encode(response.content).decode('utf-8')
    except requests.RequestException as e:
        print(f"下载图片 {url} 时出错: {e}")
        return ''
    
def read_jsonl_and_download(file_path):
    """
    读取 jsonl 文件，调用下载图片函数下载其中的 URL
    :param file_path: jsonl 文件的路径
    """
    result = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                data = json.loads(line)
                base64_dict = {}
                for key in ["screenshotURL", "danceui_screenshotURL", "swiftui_screenshotURL"]:
                    if key in data and data[key]:
                        base64_data = download_image_to_base64(data[key])
                        print(f"URL: {data[key]}, Base64 编码结果长度: {len(base64_data)}")
                        base64_dict[key] = base64_data
                        base64_dict[key + "_raw"] = data[key]
                result.append(base64_dict)
    except FileNotFoundError:
        print(f"文件 {file_path} 未找到。")
    except Exception as e:
        print(f"读取 jsonl 文件时出错: {e}")
    return result

def save_file(data, output_path, file_format='jsonl'):
    """
    保存数据到文件，支持 jsonl 和 json 格式
    :param data: 要保存的数据
    :param output_path: 输出文件路径
    :param file_format: 文件格式，支持 'jsonl' 和 'json'，默认为 'jsonl'
    """
    try:
        if file_format == 'jsonl':
            with open(output_path, 'w', encoding='utf-8') as f:
                for item in data:
                    f.write(json.dumps(item, ensure_ascii=False) + '\n')
            print(f"数据已以 jsonl 格式保存到 {output_path}")
        elif file_format == 'json':
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"数据已以 json 格式保存到 {output_path}")
        else:
            print("不支持的文件格式，请使用 'jsonl' 或 'json'")
    except Exception as e:
        print(f"保存文件时出错: {e}")

import argparse
if __name__ == "__main__":
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(description='读取CSV文件并显示内容')
    parser.add_argument('--file', nargs='?', default='your_file.csv', 
                       help='CSV文件的路径 (默认: your_file.csv)')
    parser.add_argument('--output', nargs='?', default='output.jsonl', 
                       help='输出的jsonl文件路径 (默认: output.jsonl)')
    parser.add_argument('--img', nargs='?', default='img.jsonl', 
                       help='输出的jsonl文件路径 (默认: output.jsonl)')
    
    # 解析命令行参数
    args = parser.parse_args()
    file_path = args.file
    output_path = args.output

    # 使用 csv.reader 读取
    reader_data = read_csv_with_reader(file_path)
    print("使用 csv.reader 读取的数据:")
    all_parsed_data = parser_data(reader_data)

   # Filter out data containing empty values
    non_empty_data = [
        item for item in all_parsed_data 
        if all(item.values())
    ]

    save_file(non_empty_data, output_path)
    
    img_data = read_jsonl_and_download(output_path)
    save_file(img_data, args.img)