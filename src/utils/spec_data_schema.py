from typing_extensions import TypedDict
from typing import List, Dict, Optional
from pydantic.v1 import BaseModel, Field



class ExportIcon(BaseModel):
    '''the icon need to be exported'''
    figma_node_id: str = Field(description="figma node id")
    icon_file_name: str = Field(description="icon file name, end with '.png'")

class ExportIcons(BaseModel):
    """export icons from figma file"""
    icons: List[ExportIcon]

class RecognizedComponents(BaseModel):
    """the components recognized from figma json"""
    components: List[str] = Field(description="list of component names that are used in the figma json")

class CoderOutput(BaseModel):
    """the output of the coder LLM"""
    thinking: str = Field(description="the thinking process of the LLM")
    compose_code: str = Field(description="the generated compose ui code")

class EvaluateResult(BaseModel):
    """
    The result of the evaluation, output the json string.
    """
    thinking: str = Field(description="the thinking process of the evaluation")
    result: str = Field(description="the result of the evaluation, a json string, key is the evaluation item, value is the evaluation result")

# Define the state for the graph
class AgentState(TypedDict):
    figma_url: str
    figma_token: str
    figma_json: dict = Field(default_factory=dict, description="figma json")
    figma_title: Optional[str]
    workspace_directory: str
    resource_directory: Optional[str]
    icon_list: set[str]
    components: list
    comp_knowledges: Dict[str, dict]
    coder_compose_code: str
    latest_compose_code: str
    compile_error: Optional[str]
    compile_success: bool
    preview_error: Optional[str]
    preview_success: bool
    icons_need_to_be_exported: List[ExportIcon]
    current_export_icon: ExportIcon
    figma_file_key: str
    recognize_icon_json_node: dict
    task_id: int
    current_node_name: str
    figma_screenshot: str
    runtime_screenshot: str
    evaluate_result: Optional[dict]
    coder_tree: dict = Field(default_factory=dict, description="figma simple structure and code")
    sub_figma_id: Optional[str]
    merge_success: Optional[bool]
    sub_figma_list: dict = Field(default_factory=dict, description="sub figma figma")