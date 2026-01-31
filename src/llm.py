# coding: utf-8

import openai
import anthropic
import base64
from langchain_openai import AzureChatOpenAI
from langchain_core.rate_limiters import InMemoryRateLimiter
from utils.llm_tools import llm_retry
import gemini_adapter, gemini_wrapper
from d2c_logger import tlogger

def chat_to_claude(system_prompt, user_prompt):
    key = ""
    client = anthropic.Anthropic(
        api_key=key
    )
    message = client.messages.create(
        model="claude-opus-4-20250514",  # claude 4
        max_tokens=8000,
        system=system_prompt,
        messages=[
            {"role": "user", "content": user_prompt}
        ]
    )
    return message.content[0].text

def chat_to_claude4(system_prompt, user_prompt, ui_image_url=None):
    base_url = "https://gpt-i18n.byteintl.net/gpt/openapi/online/v2/crawl"
    api_version = "2023-07-01-preview"
    ak = ""
    model_name = "gcp-claude37-sonnet"
    rate_limiter = InMemoryRateLimiter(
        requests_per_second=0.83,  # <-- Can only make a request once every 1/requests_per_second seconds!! 3 requests per minute.
        check_every_n_seconds=0.05,  # Wake up every 100 ms to check whether allowed to make a request,
        max_bucket_size=10,  # Controls the maximum burst size.
    )
    client = openai.AzureOpenAI(
        azure_endpoint=base_url,
        api_version=api_version,
        api_key=ak,
        rate_limiter=rate_limiter,
    )

    # 构造多模态 messages
    if ui_image_url:
        user_content = [
            {"type": "text", "text": user_prompt},
            {"type": "image_url", "image_url": {"url": ui_image_url}}
        ]
    else:
        user_content = user_prompt

    completion = client.chat.completions.create(
        model=model_name,
        messages=[
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_content
            }
        ],
        extra_headers={"X-TT-LOGID": "liaofeng"},
        max_tokens=20000,
        timeout=60*10,
        temperature=0,
    )
    return completion.choices[0].message.content


def chat_to_deepseek(system_prompt, user_prompt):
    api_key = ""
    model_name = "deepseek-reasoner"
    # model_name = "deepseek-chat"
    client = openai.OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com"
    )


    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        stream=False,
        temperature=0,
    )

    print(response.choices[0].message.content)
    return response.choices[0].message.content


def chat_to_genimi25_pro(system_prompt, user_prompt, image_filepath:str=None):
    base_url = "https://search.bytedance.net/gpt/openapi/online/v2/crawl"
    api_version = "2024-03-01-preview"
    ak = "Z5Yr0stNmxF8yFfcekeRxV3dpxXhYqkz_GPT_AK"
    model_name = "gemini-2.5-pro"
    client = openai.AzureOpenAI(
        azure_endpoint=base_url,
        api_version=api_version,
        api_key=ak,
    )

    # 构造多模态 messages
    if image_filepath:
        image_base64 = image_to_base64(image_filepath)
        user_content = [
            {"type": "text", "text": user_prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}", "detail": "high"}},
        ]
    else:
        user_content = user_prompt

    completion = client.chat.completions.create(
        model=model_name,
        messages=[
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_content
            }
        ],
        extra_headers={"X-TT-LOGID": "liaofeng"},
        max_tokens=20000,
        timeout=60*10,
        temperature=0,
    )
    return completion.choices[0].message.content


def chat_to_openai_gpt4(system_prompt, user_prompt=None, user_messages=None):
    base_url = "https://gpt-i18n.byteintl.net/gpt/openapi/online/v2/crawl"
    api_version = "2023-07-01-preview"
    ak = ""
    model_name = "gpt-4.1-2025-04-14"
    client = openai.AzureOpenAI(
        azure_endpoint=base_url,
        api_version=api_version,
        api_key=ak,
    )

    user_contents = []
    if len(user_prompt) > 0:
        user_contents = [
            {"type": "text", "text": user_prompt},
        ]
        if user_messages and len(user_messages) > 0:
            user_contents.extend(user_messages)
    else:
        if len(user_messages) > 0:
            user_contents = user_messages
        else:
            raise Exception("user_prompt or user_messages required!")

    completion = client.chat.completions.create(
        model=model_name,
        messages=[
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_contents
            }
        ],
        extra_headers={"X-TT-LOGID": "liaofeng"},
        max_tokens=20000,
        timeout=60*10,
        temperature=0,
    )
    return completion.choices[0].message.content


def image_to_base64(image_path):
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


class SafeAzureChatOpenAI(AzureChatOpenAI):
    """Azure 版 ChatOpenAI，自动重试 429"""
    @llm_retry
    def _generate(self, *args, **kwargs):
        return super()._generate(*args, **kwargs)


def init_gpt_gemini_model(streaming: bool = True):
    base_url = "https://search.bytedance.net/gpt/openapi/online/v2/crawl"
    api_version = "2024-03-01-preview"
    model_name = "gemini-2.5-pro"
    max_tokens = 16000
    api_type = "azure"
    ak = "Z5Yr0stNmxF8yFfcekeRxV3dpxXhYqkz_GPT_AK"

    rate_limiter = InMemoryRateLimiter(
        requests_per_second=0.7,  # <-- Can only make a request once every 1/requests_per_second seconds!! 3 requests per minute.
        check_every_n_seconds=0.05,  # Wake up every 100 ms to check whether allowed to make a request,
        max_bucket_size=5,  # Controls the maximum burst size.
    )

    gemini_model = SafeAzureChatOpenAI(
        streaming=streaming,
        azure_endpoint=base_url,
        openai_api_version=api_version,
        model=model_name,
        openai_api_key=ak,
        openai_api_type=api_type,
        max_tokens=max_tokens,
        max_retries=2,
        temperature=0,
        rate_limiter=rate_limiter,
    )
    return gemini_model


def init_gemini_chat(streaming: bool = True):
    gemini_adapter._apply_monkey_patch()
    base_url = "https://search.bytedance.net/gpt/openapi/online/v2/crawl"
    api_version = "2024-03-01-preview"
    model_name = "gemini-3-pro-preview-new"
    max_tokens = 16000
    api_type = "azure"
    ak = "Z5Yr0stNmxF8yFfcekeRxV3dpxXhYqkz_GPT_AK"
    thinking_level = "high"
    include_thoughts = True
    temperature = 0

    rate_limiter = InMemoryRateLimiter(
        requests_per_second=0.7,  # <-- Can only make a request once every 1/requests_per_second seconds!! 3 requests per minute.
        check_every_n_seconds=0.05,  # Wake up every 100 ms to check whether allowed to make a request,
        max_bucket_size=5,  # Controls the maximum burst size.
    )

    gemini_model = SafeAzureChatOpenAI(
        streaming=streaming,
        azure_endpoint=base_url,
        openai_api_version=api_version,
        model=model_name,
        openai_api_key=ak,
        openai_api_type=api_type,
        max_tokens=max_tokens,
        max_retries=2,
        temperature=0,
        rate_limiter=rate_limiter,
    )
    return gemini_wrapper.Gemini3Wrapper(gemini_model)