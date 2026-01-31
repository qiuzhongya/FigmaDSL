# coding: utf-8

"""
使用 D2C OpenAPI 接口的结果作为中间表示，将 D2C 的中间表示转换为 Compose UI 代码。
"""

import json
import os
import urllib.parse
import requests
from llm import chat_to_claude4

figma_token = "figd_rwuOMYJDUtN_BT7Xg-Lx5RVjZLv1fM7Q5eQAwjZk"


def d2c_figma2code(figma_file_url: str, transform_mode: str = "jsx+tailwindcss"):
    url = "https://semiapi.bytedance.net/d2c/figma2code"
    headers = {
        "Content-Type": "application/json"
    }
    data = {
        "url": figma_file_url,
        "figmaToken": figma_token,
        "figmaOAuth2Token": "",
        "transformMode": "jsx+tailwindcss",
        "caller": "liaofeng",
    }
    response = requests.post(url, headers=headers, json=data)
    if not response.ok:
        print("d2c failed: ", response.text)
        return None
    return response.json()



figma_file_urls = [
    ("https://www.figma.com/design/lEIy4VXyF0rnimZnnfYqqB/D2C-figma-demo?node-id=1-465&t=jW3rBPeznhI23XZD-0", "1-465"),
    ("https://www.figma.com/design/lEIy4VXyF0rnimZnnfYqqB/D2C-figma-demo?node-id=1-700&t=jW3rBPeznhI23XZD-0", "1-700"),
]

if __name__ == "__main__":
    page_index = 1
    data = d2c_figma2code(
        figma_file_url=figma_file_urls[page_index],
        transform_mode="json"
    )
    # keys: dict_keys(['fileKey', 'nodeId', 'url', 'template', 'jsx', 'scss', 'imports', 'plugins', 'globalSettings', 'pageName', 'pageId', 'rootImageURL'])

    jsx = data['jsx']
    scss = data['scss']
    print("-----------jsx")
    print(jsx)
    print("-----------scss")
    print(scss)

    directory = f"my-app/d2c_result/page{page_index}"
    if not os.path.exists(directory):
        os.makedirs(directory)

    # save to file
    with open(f"{directory}/App.jsx", "w") as f:
        f.write(jsx)
    with open(f"{directory}/App.scss", "w") as f:
        f.write(scss)
    
    with open(f"{directory}/meta.json", "w") as f:
        f.write(json.dumps(data, indent=4))