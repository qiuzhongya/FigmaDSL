from typing import List
from langchain_core.messages import AIMessage, AnyMessage
from langchain_openai.chat_models import base as openai_chat_base
from d2c_logger import tlogger


GEMINI_THOUGHT_SIGNATURES_KEY = "__gemini_function_call_thought_signatures__"


def _apply_monkey_patch():
    """Follow langchain-openai's message serializer to keep thoughtSignature."""
    original_convert = openai_chat_base._convert_message_to_dict

    def patched_convert_message_to_dict(message):
        # execute original convert
        result = original_convert(message)

        # check if message is AIMessage and has tool_calls
        if isinstance(message, AIMessage) and "tool_calls" in message.additional_kwargs:
            original_tool_calls = message.additional_kwargs["tool_calls"]
            result_tool_calls = result.get("tool_calls", [])
            
            # serialize tool_calls and add signature back
            for orig_tc, result_tc in zip(original_tool_calls, result_tool_calls):
                if "signature" in orig_tc:
                    result_tc["signature"] = orig_tc["signature"]
        
        return result

    # apply patch
    openai_chat_base._convert_message_to_dict = patched_convert_message_to_dict
    tlogger().info("Successfully monkey-patched langchain-openai for Gemini 3 support.")

def extract_and_store_thought_signatures(message: AIMessage) -> AIMessage:
    """Extract signature from tool_calls and store in additional_kwargs."""
    if not hasattr(message, "additional_kwargs") or not message.additional_kwargs.get("tool_calls"):
        return message

    tool_calls = message.additional_kwargs["tool_calls"]
    signatures = {}

    for tool_call in tool_calls:
        # default case
        if isinstance(tool_call, dict) and "signature" in tool_call:
            tool_call_id = tool_call.get("id", "")
            signature = tool_call.get("signature")
            if signature:
                signatures[tool_call_id] = signature

    if signatures:
        message.additional_kwargs[GEMINI_THOUGHT_SIGNATURES_KEY] = signatures
        tlogger().info(f"Stored {len(signatures)} thoughtSignatures.")

    return message

def restore_thought_signatures(messages: List[AnyMessage]) -> List[AnyMessage]:
    """Restore signatures from additional_kwargs back to tool_calls before sending."""
    restored_messages = []
    for message in messages:
        if isinstance(message, AIMessage) and hasattr(message, "additional_kwargs"):
            additional_kwargs = message.additional_kwargs
            signatures = additional_kwargs.get(GEMINI_THOUGHT_SIGNATURES_KEY)
            tool_calls = additional_kwargs.get("tool_calls")

            if signatures and tool_calls:
                restored_count = 0
                for tool_call in tool_calls:
                    if isinstance(tool_call, dict):
                        tool_call_id = tool_call.get("id", "")
                        if tool_call_id in signatures:
                            tool_call["signature"] = signatures[tool_call_id]
                            restored_count += 1
                if restored_count > 0:
                    tlogger().info(f"Restored {restored_count} thoughtSignatures.")
        
        restored_messages.append(message)
    return restored_messages