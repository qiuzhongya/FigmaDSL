import d2c_config
import json
from d2c_logger import tlogger
import utils.spec_tool_utils as d2c_utils
from utils import llm_prompts, llm_tools
from llm import init_gemini_chat
from utils.spec_data_schema import CoderOutput

tools = [llm_tools.export_figma_icon]
model = init_gemini_chat(streaming=False)
llm_with_tools = model.bind_tools(tools)
def sub_figma_2_coder(sub_figma_json: dict, icon_list: set[str]) -> str:
    """
    Generates or fixes compose ui code.
    """
    tlogger().info("---SUB FIGMA CODING ---")
    system_prompt = llm_prompts.get_coder_system_prompt("")
    user_prompt = llm_prompts.get_coder_user_prompt(json.dumps(sub_figma_json, indent=4, ensure_ascii=False))
    exported_icons_prompt = ""
    if icon_list:
        exported_icons_prompt += "The resource files in the app/src/main/res/drawable-xxhdpi directory are:\n"
        for icon in icon_list:
            exported_icons_prompt += f"- {icon}\n"
        user_prompt += "\n# Icon List\n" + exported_icons_prompt
    tlogger().info("generate code start")
    llm_without_tools = model.bind_tools([])
    chain = llm_without_tools.with_structured_output(CoderOutput, method="function_calling")
    messages = [
        ("system", system_prompt),
        ("user", user_prompt)
    ]
    for retry_time in range(d2c_config.MAXCoderRetry):
        coder_output = llm_tools.safe_call_llm(chain, messages)
        # ensure the compose code is not empty and valid
        if coder_output and coder_output.compose_code and d2c_utils.is_valid_sub_compose_code(coder_output.compose_code.strip()):
            tlogger().info(f"generate code as follows: \n{coder_output.compose_code}")
            break
        else:
            tlogger().info(f"generate code failed, retry {retry_time + 1} times")
    else:
        tlogger().info(f"generate code failed, retry {d2c_config.MAXCoderRetry} times, output is empty")
        raise Exception("coder output is empty, please retry later")

    # clean the compose code format to avoid the code is not valid for kotlin file
    generated_compose_code = d2c_utils.clean_generated_code(coder_output.compose_code.strip())
    idx = generated_compose_code.find(d2c_config.Package_Declaration)
    if idx > 0:
        tlogger().info(f"remove from {idx} extra code : {generated_compose_code[:idx]}")
        generated_compose_code = generated_compose_code[idx:]
    return generated_compose_code
