# coding: utf-8

import json
import os
import urllib.parse
import requests
from llm import chat_to_claude4

figma_token = "figd_rwuOMYJDUtN_BT7Xg-Lx5RVjZLv1fM7Q5eQAwjZk"


def parse_figma_file(figma_url: str, node_id: str):
    #"https://www.figma.com/design/lEIy4VXyF0rnimZnnfYqqB/D2C-figma-demo?node-id=1-465&t=jW3rBPeznhI23XZD-0",
    file_id = figma_url.split("/")[-2]
    url = f"https://api.figma.com/v1/files/{file_id}/nodes?ids={node_id}"
    headers = {
        "X-FIGMA-TOKEN": figma_token
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 429:
        retry_after = int(response.headers.get("Retry-After", 60))
        print(f"Rate limited (429) on {url} -> retry_after={retry_after}")
        raise Exception(f"Figma Api rate limited (429) on {url} -> retry_after={retry_after}")
    if not response.ok:
        print("parse figma file failed: ", response.text)
        return None
    return response.json()['nodes'][node_id]


figma_file_urls = [
    ("https://www.figma.com/design/lEIy4VXyF0rnimZnnfYqqB/D2C-figma-demo?node-id=1-465&t=jW3rBPeznhI23XZD-0", "1:465", "https://i.postimg.cc/Gmt3Cqzf/image1.png"),
    ("https://www.figma.com/design/lEIy4VXyF0rnimZnnfYqqB/D2C-figma-demo?node-id=1-700&t=jW3rBPeznhI23XZD-0", "1:700", ""),
    ("https://www.figma.com/design/4mA2iRrJRgfNIFL1l66yVk/D2C-test-case-2?node-id=1-1427&t=LhXxxjXmXXZLionl-0", "1:1427", "https://i.postimg.cc/gjcFK2T7/image2.png"),
    ("https://www.figma.com/design/4mA2iRrJRgfNIFL1l66yVk/D2C-test-case-2?node-id=1-1767&t=LhXxxjXmXXZLionl-0", "1:1767", "https://i.postimg.cc/4y8C2TCx/image3.png"),
    ("https://www.figma.com/design/4mA2iRrJRgfNIFL1l66yVk/D2C-test-case-2?node-id=1-460&t=LhXxxjXmXXZLionl-0", "1:460", "https://i.postimg.cc/1zN9gXkc/image4.png"),
]

if __name__ == "__main__":
    for page_index, (file_url, node_id, ui_image_url) in enumerate(figma_file_urls):
        # file_url, node_id = figma_file_urls[page_index]
        data = parse_figma_file(file_url, node_id)
        with open(f"figma_file{page_index}.json", "w") as f:
            f.write(json.dumps(data, indent=4, ensure_ascii=False))