"""translate figma json to compose ui code"""
import os, sys
import json
import random
import string
import shutil
import subprocess
import requests
import re
from langgraph.graph import StateGraph, START, END
import time
from langgraph.prebuilt import create_react_agent
from llm import init_gemini_chat
from d2c_logger import tlogger
from utils.tos_manager import upload_zip_to_tos
import d2c_datautil
import d2c_config
from utils import llm_prompts, llm_tools
from utils.spec_data_schema import AgentState, ExportIcons, RecognizedComponents, CoderOutput, EvaluateResult
import utils.spec_tool_utils as d2c_utils
from utils.container_tools import prepare_container
from utils.retry_pool_tools import RetryPool


os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.getcwd())

# Step 1: Export Figma
def export_figma_json(state: AgentState):
    """
    Exports the Figma file to a JSON object.
    """
    tlogger().info("--- EXPORTING FIGMA FILE ---")
    d2c_datautil.update_task_stage(state["task_id"], "export_figma_json")
    # extract "node-id" parameter from figma_url
    figma_file_key = state["figma_url"].split("/")[-2]
    node_id = state["figma_url"].split("node-id=")[-1].split("&")[0]
    if not node_id:
        tlogger().info("figma url is invalid")
        raise ValueError("figma url is invalid, need node-id parameter")

    figma_title = re.search(r"/([^/]+)\?node-id", state["figma_url"]).group(1).replace("-", "_")
    state["figma_title"] = figma_title

    figma_json = d2c_utils.parse_figma_file(node_id, state["figma_token"], figma_file_key)
    document = figma_json.get("document")
    if document:
        page_title = document.get("name", d2c_config.FigmaDefaultTItle)
        d2c_datautil.update_page_title(state["task_id"], page_title, d2c_config.TaskStatus.Running.value)
    if not figma_json:
        tlogger().info("parse figma file failed")
        raise ValueError("parse figma file failed")
    return {"figma_json": figma_json, "figma_file_key": figma_file_key, "figma_title": figma_title}

# Step 2: Initialize Container
def init_container(state: AgentState):
    """
    Initializes the container environment.
    """
    tlogger().info("--- INITIALIZING CONTAINER ---")
    d2c_datautil.update_task_stage(state["task_id"], "init_container")
    task_id = state["task_id"]
    workspace_directory = os.path.join(d2c_config.OUTPUT_DIR, f"{task_id}")
    os.makedirs(workspace_directory, exist_ok=True)

    #workspace_directory = tempfile.mkdtemp()
    tlogger().info(f"project directory: {workspace_directory}")
    # Clone the repository
    prepare_container(workspace_directory)
    # Run gradlew command
    gradlew_command = ["./gradlew", "updateDebugScreenshotTest"]
    result = subprocess.run(gradlew_command, cwd=workspace_directory, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"Failed to run gradlew command: {result.stderr}")
    
    # create resource directory
    resource_directory = os.path.join(workspace_directory, "app/src/main/res/drawable-xxhdpi")
    os.makedirs(resource_directory, exist_ok=True)
    return {"workspace_directory": workspace_directory, "resource_directory": resource_directory}

tools = [llm_tools.export_figma_icon]
model = init_gemini_chat(streaming=False)
llm_with_tools = model.bind_tools(tools)

def recognize_icon_block(node_json: dict):
    tlogger().info("recognize iconblock")
    node_json_str = json.dumps(node_json, indent=4, ensure_ascii=False)
    user_prompt = f"node json is:\n```{node_json_str}\n```"

    chain = llm_with_tools.with_structured_output(ExportIcons, method="function_calling")
    export_icons_obj = llm_tools.safe_call_llm(chain, [
        ("system", llm_prompts.get_recognize_icon_system_prompt()),
        ("human", user_prompt),
    ])
    if export_icons_obj and export_icons_obj.icons:
        return export_icons_obj.icons
    else:
        return []

def export_icon_block(state: AgentState):
    icons_info = {}
    if "icon_list" not in state:
        state["icon_list"] = set()
    if "icons_need_to_be_exported" not in state or not state["icons_need_to_be_exported"]:
        tlogger().info("no icons need to be exported in state")
    else:
        for icon_info in state["icons_need_to_be_exported"]:
            icons_info[icon_info.figma_node_id] = icon_info.icon_file_name
    #Reduce API calls because Figma services number of calls
    main_node_id = state["figma_url"].split("node-id=")[-1].split("&")[0].replace("-", ":")
    icons_info[main_node_id] = f"figma_screenshot_{state['task_id']}"
    image_info = d2c_utils.get_image_node(state["figma_json"].get("document", {}))
    icons_info |= image_info
    saved_path = llm_tools.export_figma_icon.invoke({
        "figma_nodes": icons_info,
        "figma_file_key": state["figma_file_key"],
        "figma_token": state["figma_token"],
        "resource_directory": state["resource_directory"]
    })
    if saved_path:
        state["icon_list"].update(saved_path)
    tlogger().info(f"icon_list {state['icon_list']}")
    # Clear the list of icons to be exported after processing
    state["icons_need_to_be_exported"] = []
    return {"icon_list": state["icon_list"]}


# Step 3: Export Figma Icons
def export_figma_icons(state: AgentState):
    """
    Exports figma icons.
    """
    tlogger().info("--- EXPORTING FIGMA ICONS ---")
    if "icons_need_to_be_exported" not in state:
        state["icons_need_to_be_exported"] = []
    d2c_datautil.update_task_stage(state["task_id"], "export_figma_icons")
    sub_figma = d2c_utils.split_tree(state["figma_json"].get("document", {}))
    retry_pool = state.get("retry_pool", RetryPool())
    future_tasks = []
    for node_id, node_json in sub_figma.items():
        tlogger().info(f"Recognize node {node_id}: type={node_json.get('type')}, name={node_json.get('name')}")
        future_tasks.append(retry_pool.submit(recognize_icon_block, node_json))
        time.sleep(5)
    for f in future_tasks:
        state["icons_need_to_be_exported"].extend(f.result())
    builder_export = StateGraph(AgentState)
    builder_export.add_node("export_icon", export_icon_block)
    builder_export.add_edge(START, "export_icon")
    builder_export.add_edge("export_icon", END)
    export_graph = builder_export.compile()
    result = export_graph.invoke(state)
    state.update(result)
    return {"icon_list": state.get("icon_list", set())}

# Step 4: Export Figma Screenshot
def export_figma_screenshot(state: AgentState):
    """
    Export the figma screenshot.
    """
    tlogger().info("--- EXPORT FIGMA SCREENSHOT ---")
    d2c_datautil.update_task_stage(state["task_id"], "export_figma_screenshot")
    def parse(url):
        """from Figma url extrac node-id and node-id"""
        node = re.search(r"node-id=([\d\-]+)", url).group(1).replace("-", ":")
        name = re.search(r"/([^/]+)\?node-id", url).group(1).replace("-", "_")
        return node, name

    workspace = state["workspace_directory"]
    shot_directory = os.path.join(workspace, "app/src/test/snapshots/images")
    drawable_directory = os.path.join(workspace, "app/src/main/res/drawable-xxhdpi")
    screenshot_filename = f"figma_screenshot_{state['task_id']}.png"
    shot_path = os.path.join(shot_directory, screenshot_filename)

    if os.path.exists(shot_path):
        tlogger().info(f"Screenshot already exists at: {shot_path}, skipping.")
        return {
            "figma_screenshot": shot_path,
            "current_node_name": "export_figma_screenshot"
        }

    drawable_candidate = os.path.join(drawable_directory, f"{screenshot_filename}")
    if os.path.exists(drawable_candidate):
        tlogger().info(f"Found matching screen shot in drawable: {drawable_candidate}, moving to snapshot dir.")
        os.makedirs(shot_directory, exist_ok=True)
        shutil.move(drawable_candidate, shot_path)
        return {
            "figma_screenshot": shot_path,
            "current_node_name": "export_figma_screenshot"
        }

    node, name = parse(state["figma_url"])
    tlogger().info(f"No local file found in f{drawable_candidate}, downloading from Figma for node: {node}")
    api_url = f"https://api.figma.com/v1/images/{state['figma_file_key']}"
    params = {"ids": node, "format": "png", "scale": 2}
    r = requests.get(api_url, headers={"X-Figma-Token": state["figma_token"]}, params=params)
    if r.status_code != 200:
        tlogger().info(f"Get screenshot failed, name: {name}, status_code: {r.status_code}")
        raise Exception(f"Get screenshot failed, figma_url: {state['figma_url']}, status_code: {r.status_code}")

    img_url = r.json().get("images", {}).get(node)
    if not img_url:
         tlogger().info(f"Get screenshot failed, figma_url: {state['figma_url']}, not found image url")
         raise Exception(f"Get screenshot failed, figma_url: {state['figma_url']}, not found image url")
    img = requests.get(img_url)
    shot_directory = os.path.join(state["workspace_directory"], "app/src/test/snapshots/images")

    fname = f"{shot_directory}/figma_screenshot_{state['task_id']}.png"
    with open(fname, "wb") as f:
        f.write(img.content)
        tlogger().info(f"Save screenshot success, save_path: {fname}")
    return {"figma_screenshot": fname, "current_node_name": "export_figma_screenshot"}


Component_Knowledge_Map = d2c_utils.read_component_knowledge()
Components = Component_Knowledge_Map.keys()

# Step 5: Recognize Components
def recognize_components(state: AgentState):
    """
    Recongnizes components from figma json.
    """
    tlogger().info("--- RECOGNIZING COMPONENTS ---")
    d2c_datautil.update_task_stage(state["task_id"], "recognize_components")
    figma_json_str = json.dumps(state["figma_json"], indent=4, ensure_ascii=False)
    component_list = list()
    return {"components": component_list}
    system_prompt = f'''
You are an expert UI designer and developer.
Analyze the following Figma JSON and identify all the components from the provided list that are used in the design.

Component list:
{Components}

Respond with a JSON object containing a single key "components" which is a list of strings of the component names found.
'''
    user_prompt = f"Figma JSON:\n{figma_json_str}"
    
    llm_without_tools = model.bind_tools([])
    
    chain = llm_without_tools.with_structured_output(RecognizedComponents, method="function_calling")
    recognized = llm_tools.safe_call_llm(chain, [
        ("system", system_prompt.strip()),
        ("user", user_prompt.strip())
    ])
    
    component_list = list(set(recognized.components))
    tlogger().info(f"Recognized components: {component_list}")

    return {"components": component_list}


# Step 6: Get Component Knowledges
def get_component_knowledges(state: AgentState):
    """
    Gets component knowledges.
    """
    tlogger().info("--- GETTING COMPONENT KNOWLEDGES ---")
    d2c_datautil.update_task_stage(state["task_id"], "get_component_knowledges")
    components = set(state["components"])
    comp_knowledges = {}
    for component in components:
        if component in Component_Knowledge_Map:
            comp_knowledges[component] = Component_Knowledge_Map[component]
        else:
            tlogger().info(f"component {component} not found in component knowledge map")
    return {"comp_knowledges": comp_knowledges}

# Step 7: Coder
def coder(state: AgentState):
    """
    Generates or fixes compose ui code.
    """
    tlogger().info("--- CODING ---")
    d2c_datautil.update_task_stage(state["task_id"], "coder")
    workspace_dir = state["workspace_directory"]
    knowledges = []
    for component, knowledge_json in state["comp_knowledges"].items():
        knowledge_text = json.dumps(knowledge_json, indent=4, ensure_ascii=False)
        knowledges.append(f"## {component}\n```json\n{knowledge_text}\n```")
    component_knowledge_prompt = "\n".join(knowledges)
    system_prompt = llm_prompts.get_coder_system_prompt(component_knowledge_prompt)
    user_prompt = llm_prompts.get_coder_user_prompt(json.dumps(state["figma_json"], indent=4, ensure_ascii=False))
    exported_icons_prompt = ""
    if "icon_list" in state and state["icon_list"]:
        exported_icons_prompt += "The resource files in the app/src/main/res/drawable-xxhdpi directory are:\n"
        for icon in state["icon_list"]:
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
        if coder_output and coder_output.compose_code and d2c_utils.is_valid_compose_code(coder_output.compose_code.strip()):
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
    with open(os.path.join(workspace_dir, "app/src/main/java/com/example/myapplication/Greeting.kt"), "w") as f:
        f.write(generated_compose_code)
    return {"coder_compose_code": generated_compose_code, "latest_compose_code": generated_compose_code, "current_node_name": "coder"}


def bugfix(state: AgentState):
    """
    Fix compose ui code.
    """
    tlogger().info(f"--- BUGFIX: {state['current_node_name']} ---")
    d2c_datautil.update_task_stage(state["task_id"], "bugfix")
    workspace_dir = state["workspace_directory"]

    # switch the error message according to the current node name
    if state["current_node_name"] == "compiler":
        error_message = f"The compiler failed with the following error: {state['compile_error']}"
    elif state["current_node_name"] == "previewer":
        error_message = f"The previewer failed with the following error: {state['preview_error']}"
    else:
        error_message = "Go on fixing the current issue, and ensure the compose ui code is complete, free of syntax errors and runnable."

    system_prompt = llm_prompts.get_bugfix_system_prompt(workspace_dir)
    model_stream = init_gemini_chat(streaming=False)
    bugfix_agent = create_react_agent(
        model=model_stream,
        tools=[llm_tools.replace_all, llm_tools.read_file, llm_tools.edit_file, llm_tools.rename_icon, llm_tools.mock_icon, llm_tools.list_icons],
        prompt=system_prompt,
    )
    inputs = {"messages": [{"role": "user", "content": f"Current working directory is: {workspace_dir}\n"+error_message}]}
    time.sleep(10)
    for chunk in bugfix_agent.stream(inputs, stream_mode="updates"):
        tlogger().info(chunk)
        time.sleep(5)

    return {"current_node_name": "bugfix"}

# Step 8: Replace Tester
def replace_tester(state: AgentState):
    """
    Replace the tester file with the generated code.
    """
    tlogger().info("--- REPLACING TESTER ---")
    d2c_datautil.update_task_stage(state["task_id"], "replace_tester")
    workspace_dir = state["workspace_directory"]

    system_prompt = f"""You are an expert Android developer. You need to update the test file to test the composable function in the Greeting.kt file.

Workspace directory: {workspace_dir}

Two important files in the workspace::
1. {workspace_dir}/app/src/main/java/com/example/myapplication/Greeting.kt: the composable function to be tested
2. {workspace_dir}/app/src/test/java/com/example/myapplication/ResourcesTest.kt: you need to edit the `fun compose()` function in the ResourcesTest.kt file

Your task is to edit `ResourcesTest.kt` to correctly test the composable function provided in `Greeting.kt`.
The function signature of the composable in `Greeting.kt` might be different from the one currently being tested in the test files. You need to handle this.

You can use the following tools:
- `replace_all`: to replace all occurrences of a string in a file
- `read_file`: to read the content of a file
"""

    replace_tester_agent = create_react_agent(
        model=model,
        tools=[llm_tools.replace_all, llm_tools.read_file],
        prompt=system_prompt.strip(),
    )
    inputs = {"messages": [{"role": "user", "content": "please begin"}]}
    for chunk in replace_tester_agent.stream(inputs, stream_mode="updates"):
        tlogger().info(chunk)
        time.sleep(5)
    return {}

# Step 9: Compiler
def compiler(state: AgentState):
    """
    Compile the compose ui code and checks for errors.
    """
    tlogger().info("--- COMPILING ---")
    d2c_datautil.update_task_stage(state["task_id"], "compiler")
    workspace_dir = state["workspace_directory"]
    success, error_message = d2c_utils.compile(workspace_dir)
    return {"compile_success": success, "compile_error": error_message, "current_node_name": "compiler"}


# Step 10: Previewer
def previewer(state: AgentState):
    """
    Preview the compose ui code and checks for errors.
    """
    tlogger().info("--- PREVIEWING ---")
    d2c_datautil.update_task_stage(state["task_id"], "previewer")
    workspace_dir = state["workspace_directory"]
    success, error_message, screenshot_path = d2c_utils.preview(workspace_dir)
    return {"preview_success": success, "preview_error": error_message, "runtime_screenshot": screenshot_path, "current_node_name": "previewer"}

def remove_useless_icons(state: AgentState):
    """
    Removes useless icons.
    """
    tlogger().info("--- REMOVING USELESS ICONS ---")
    d2c_datautil.update_task_stage(state["task_id"], "remove_useless_icons")
    compose_code = llm_tools.read_file.invoke({"abs_path": os.path.join(state["workspace_directory"], "app/src/main/java/com/example/myapplication/Greeting.kt")})
    used_icons = d2c_utils.find_used_icons(compose_code)
    d2c_utils.remove_useless_icon_files(state["icon_list"], used_icons, state["workspace_directory"])
    return {"latest_compose_code": compose_code, "current_node_name": "remove_useless_icons"}

# step 11: evaluator
def evaluator(state: AgentState):
    """
    Evaluates the current project.
    """
    tlogger().info("--- EVALUATING CURRENT PROJECT ---")
    d2c_datautil.update_task_stage(state["task_id"], "evaluator")
    figma_screenshot = state["figma_screenshot"]
    runtime_screenshot = state["runtime_screenshot"]
    if not figma_screenshot or not runtime_screenshot:
        raise Exception("figma_screenshot or runtime_screenshot is not set, please export figma screenshot and preview first")

    system_prompt = llm_prompts.get_evaluate_system_prompt()
    user_prompt = f"""
figma设计稿: {figma_screenshot}
runtime运行截图: {runtime_screenshot}
请严格遵循设计的规则对两张图片, 并按照输出格式输出结果
    """

    llm_for_evaluate = model.bind_tools([llm_tools.encode_image])
    
    evaluate_result = llm_for_evaluate.with_structured_output(EvaluateResult, method="function_calling").invoke([
        ("system", system_prompt.strip()),
        ("user", user_prompt.strip())
    ])
    
    tlogger().info(f"Evaluate result: {evaluate_result.result}")

    return {"evaluate_result": evaluate_result.result, "current_node_name": "evaluator"}

# step 12: Commit
def commit(state: AgentState):
    """
    Commits the code and resource files.
    """
    tlogger().info("--- COMMITTING ---")
    d2c_datautil.update_task_stage(state["task_id"], "commit")
    workspace_dir = state["workspace_directory"]
    # generate random 5 digits
    random_digits = ''.join(random.choices(string.digits, k=5))
    branch_name = f"d2c_{random_digits}"

    try:
        subprocess.run(["git", "checkout", "-b", branch_name], cwd=workspace_dir, check=True, capture_output=True, text=True)

        # git add .
        subprocess.run(["git", "add", "."], cwd=workspace_dir, check=True, capture_output=True, text=True)

        # git commit -m "compose ui"
        subprocess.run(["git", "commit", "-m", "compose ui"], cwd=workspace_dir, check=True, capture_output=True, text=True)

        # git push origin HEAD
        subprocess.run(["git", "push", "origin", "HEAD"], cwd=workspace_dir, check=True, capture_output=True, text=True)

    except subprocess.CalledProcessError as e:
        # If git commit fails because there are no changes, we can ignore it.
        if "nothing to commit" in e.stdout or "nothing to commit" in e.stderr:
            tlogger().info("No changes to commit.")
        else:
            tlogger().info(f"Git command failed: {e.stderr}")
            raise

    return {"current_node_name": "commit"}


# step 13: compress output to upload
def compress_upload(state: AgentState):
    """
    compress output to upload
    """
    tlogger().info("--- COMPRESS ---")
    d2c_datautil.update_task_stage(state["task_id"], "compress_upload")
    workspace_dir = state["workspace_directory"]
    compress_dir = d2c_config.OUTPUT_DIR
    # generate random 5 digits
    task_id = state["task_id"]
    figma_title = state["figma_title"]
    logfile = os.path.join(compress_dir, f"{task_id}.log")
    if os.path.isfile(logfile):            # 只移动文件
        shutil.copy(logfile, workspace_dir)   
    try:
        subprocess.run(["zip", "-r", f"{figma_title}_{task_id}.zip", f"{task_id}"], cwd=compress_dir, check=True, capture_output=True, text=True)
        """ add upload to url here. """
        output_zip_file_path = os.path.join(compress_dir, f"{figma_title}_{task_id}.zip")
        output_folder_path = os.path.join(compress_dir, f"{figma_title}_{task_id}")
        os.rename(state["workspace_directory"], f"{output_folder_path}")
        d2c_datautil.set_task_output(task_id, state["latest_compose_code"])
        tlogger().info(f"latest_compose_code: \n{state['latest_compose_code']}")
        upload_zip_to_tos(output_zip_file_path)
        d2c_datautil.update_task_complete(task_id, d2c_config.TaskStatus.Successed.value, output_folder_path)
    except subprocess.CalledProcessError as e:
            tlogger().info(f"tar command failed: {e.stderr}")
            raise
    return {"current_node_name": "compress_upload", "workspace_directory": output_folder_path}

# step 14: Destroy Container
def destroy_container(state: AgentState):
    """
    Destroys the container environment.
    """
    tlogger().info("--- DESTROYING CONTAINER ---")
    d2c_datautil.update_task_stage(state["task_id"], "destroy_container")
    os.remove(f"{state['workspace_directory']}.zip")
    return {"current_node_name": "destroy_container"}

def compiler_status_checker(state: AgentState):
    """
    Check the compiler status is success or failed. 
    If the compiler is success, check the compose code is valid, if valid, return to previewer, if not valid, return to coder.
    If the compiler is failed, return to bugfix.
    """
    if state["compile_success"]:
        # check the compose code is valid
        compose_code = llm_tools.read_file.invoke({"abs_path": os.path.join(state["workspace_directory"], "app/src/main/java/com/example/myapplication/Greeting.kt")})
        if d2c_utils.is_valid_compose_code(compose_code.strip()):
            return "previewer"
        else:
            return "coder"
    else:
        return "bugfix"

def previewer_status_checker(state: AgentState):
    """
    Check the previewer status is success or failed.
    If the previewer is success, return to remove_useless_icons.
    If the previewer is failed, return to bugfix.
    """
    if state["preview_success"]:
        return "remove_useless_icons"
    else:
        return "bugfix"

def evaluator_status_checker(state: AgentState):
    """
    Check the evaluator status
    """
    if state["evaluate_result"]:
        evaluate_result = json.loads(state["evaluate_result"].replace("'", '"'))
        for key, value in evaluate_result.items():
            if value < d2c_config.EvaluateThreshold:
                return "coder"
        return "compress_upload"
    else:
        return "coder"

def create_workflow():
    # Define the workflow
    workflow = StateGraph(AgentState)

    # Add the nodes
    workflow.add_node("export_figma_json", export_figma_json)
    workflow.add_node("init_container", init_container)
    workflow.add_node("export_figma_screenshot", export_figma_screenshot)
    workflow.add_node("export_figma_icons", export_figma_icons)
    workflow.add_node("recognize_components", recognize_components)
    workflow.add_node("get_component_knowledges", get_component_knowledges)
    workflow.add_node("coder", coder)
    workflow.add_node("replace_tester", replace_tester)
    workflow.add_node("compiler", compiler)
    workflow.add_node("remove_useless_icons", remove_useless_icons)
    workflow.add_node("previewer", previewer)
    workflow.add_node("commit", commit)
    workflow.add_node("compress_upload", compress_upload)
    workflow.add_node("destroy_container", destroy_container)
    workflow.add_node("bugfix", bugfix)
    workflow.add_node("evaluator", evaluator)

    # Add the edges
    workflow.add_edge(START, "export_figma_json")
    workflow.add_edge("export_figma_json", "init_container")
    workflow.add_edge("init_container", "export_figma_icons")
    workflow.add_edge("export_figma_icons", "export_figma_screenshot")
    workflow.add_edge("export_figma_screenshot", "recognize_components")
    workflow.add_edge("recognize_components", "get_component_knowledges")
    workflow.add_edge("get_component_knowledges", "coder")
    workflow.add_edge("coder", "replace_tester")
    workflow.add_edge("replace_tester", "compiler")
    workflow.add_edge("bugfix", "compiler")

    workflow.add_conditional_edges(
       "compiler",
        compiler_status_checker,
    )
    workflow.add_conditional_edges(
        "previewer",
        previewer_status_checker,
    )
    
    workflow.add_edge("remove_useless_icons", "evaluator")

    workflow.add_conditional_edges(
        "evaluator",
        evaluator_status_checker,
    )
    #workflow.add_edge("commit", "compress_upload")
    workflow.add_edge("compress_upload", "destroy_container")
    workflow.add_edge("destroy_container", END)

    # Compile the app
    app = workflow.compile()
    return app

# Run the agent
if __name__ == "__main__":
    figma_url = input("figma url: ")
    if not figma_url:
        figma_url = d2c_config.FigmaSampleUrl
    if not figma_url.strip().startswith("https://www.figma.com/design/"):
        raise Exception("figma url format error!")

    figma_token = input("figma token: ")
    if not figma_token:
        figma_token = d2c_config.FigmaSampleToken
    task_id = input("task id:")
    if not task_id:
        from d2c_datautil import id_generator
        task_id = id_generator()
        tlogger().info(f"task_id:{task_id}")

    state = {
        "task_id": task_id,
        "figma_url": figma_url.strip(),
        "figma_token": figma_token.strip(),
    }
    app = create_workflow()
    for output in app.stream(state, config={"recursion_limit": d2c_config.RecursionLimit}):
        for key, value in output.items():
            tlogger().info(f"Finished running: {key}")
        tlogger().info("---")
