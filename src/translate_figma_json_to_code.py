# coding: utf-8
"""
将 figma json 翻译为 compose ui 代码
- 识别并导出icon
- 使用组件
"""
import subprocess
import os
import re
import json
import tempfile

from pydantic.v1 import BaseModel
from llm import chat_to_genimi25_pro
from export_figma_icons import export_figma_icons

figma_token = "figd_rwuOMYJDUtN_BT7Xg-Lx5RVjZLv1fM7Q5eQAwjZk"


def get_system_prompt():
    return """# 角色
你是一个经验丰富的 Android 工程师，擅长 Compose 开发和还原设计稿。

# 任务
根据输入的 figma json 和期望的 ui 效果图，生成 compose ui 代码，高度还原设计效果。

# 约束
- 仅输出代码，不要有任何解释，不要省略代码
- 翻译后的代码要完整、没有语法错误，能够直接运行。比如需要 import 依赖的包
- 使用 Material design 3 的组件和 api，即 `androidx.compose.material3`
- 使用 Image 来替代 Icon
- 高度还原设计效果，做到像素级的还原
- 如果 Icon 有父节点，应该尽量使用父节点，以保证图标的占位大小、阴影部分被保留下来
- 优先使用组件库中的组件实现，而不是自定义组件
- 翻译后的文件，package 使用 com.example.myapplication
"""

components = [
    "DuxButton",
    "DuxText",
    "DuxIcon",
    "DuxTitleBar",
    "DuxHorizontalDivider",
    "DuxBadge",
    "DuxCheckBox",
    "DuxBasicPanel",
]

def get_component_knowledge_prompt() -> str:
    return """# 组件知识库
## DuxButton
```json
{
    "DuxButton": {
        "description": "DuxButton是DUX设计语言中的基础按钮组件，用于响应用户的点击操作。",
        "interfaces": [
            {
                "description": "标准的DuxButton组件。具体指南请参考",
                "params": {
                    "onClick": {
                        "type": "() -> Unit",
                        "required": true,
                        "description": "按钮的点击事件回调。"
                    },
                    "text": {
                        "type": "String",
                        "required": false,
                        "description": "按钮上显示的文本。",
                        "default": "null"
                    },
                    "textFontWeight": {
                        "type": "FontWeight",
                        "required": false,
                        "description": "按钮文本的字体粗细。",
                        "default": "null"
                    },
                    "enabled": {
                        "type": "Boolean",
                        "required": false,
                        "description": "按钮是否可用。",
                        "default": "true"
                    },
                    "modifier": {
                        "type": "Modifier",
                        "required": false,
                        "description": "应用于按钮的Modifier。",
                        "default": "Modifier"
                    },
                    "startIcon": {
                        "type": "DrawableResource",
                        "required": false,
                        "description": "在文本前显示的图标。",
                        "default": "null"
                    },
                    "endIcon": {
                        "type": "DrawableResource",
                        "required": false,
                        "description": "在文本后显示的图标。",
                        "default": "null"
                    },
                    "variant": {
                        "type": "DuxButtonVariant",
                        "required": false,
                        "description": "按钮的视觉样式变体。",
                        "default": "DuxButtonVariantDefault.primary()"
                    },
                    "size": {
                        "type": "DuxButtonSize",
                        "required": false,
                        "description": "按钮的尺寸。",
                        "default": "DuxButtonSizeDefault.large()"
                    },
                    "isLoading": {
                        "type": "Boolean",
                        "required": false,
                        "description": "按钮是否处于加载状态。",
                        "default": "false"
                    }
                }
            }
        ],
        "attributes": {
            "variant": {
                "description": "按钮的视觉样式，决定了按钮的背景色、内容颜色、边框和阴影等。DuxButtonVariantDefault提供了多种预设样式：primary, secondaryHighlight, secondary, tertiary。",
                "params": {
                    "value": {
                        "type": "DuxButtonVariant",
                        "required": false,
                        "description": "按钮的样式变体。",
                        "default": "DuxButtonVariantDefault.primary()"
                    }
                }
            },
            "size": {
                "description": "按钮的尺寸，决定了按钮的最小宽高、内边距、圆角、图标大小和字体样式。DuxButtonSizeDefault提供了多种预设尺寸：large, medium, small, tiny。",
                "params": {
                    "value": {
                        "type": "DuxButtonSize",
                        "required": false,
                        "description": "按钮的尺寸。",
                        "default": "DuxButtonSizeDefault.large()"
                    }
                }
            }
        },
        "events": {
            "onClick": {
                "description": "当用户点击按钮时触发。",
                "params": {}
            }
        },
        "examples": [
            {
                "description": "创建一个包含主要和次要按钮的行布局，用于确认和取消操作。",
                "code": "Row(modifier = Modifier.fillMaxWidth().padding(16.dp),\n    horizontalArrangement = Arrangement.spacedBy(10.dp)) {\n    DuxButton(\n        modifier = Modifier.weight(1f),\n        onClick = {},\n        text = \"取消\",\n        variant = DuxButtonVariantDefault.secondary()\n    )\n    DuxButton(\n        onClick = {},\n        modifier = Modifier.weight(1f),\n        text = \"确定\",\n        variant = DuxButtonVariantDefault.primary()\n    )\n}"
            }
        ]
    }
}
```

## DuxText
```json
{
  "DuxTextTag": {
    "description": "纯展示型文本标签，可带左侧图标，不可点击。它是对 DuxTag 的封装，简化了用于纯文本展示场景的 API。",
    "interfaces": [
      {
        "description": "DuxTextTag 的可组合函数接口。",
        "params": {
          "text": {
            "type": "String",
            "required": true,
            "description": "标签显示的文本。"
          },
          "modifier": {
            "type": "Modifier",
            "required": false,
            "description": "组件的修饰符。",
            "default": "Modifier"
          },
          "iconRes": {
            "type": "DrawableResource?",
            "required": false,
            "description": "标签左侧的图标资源。",
            "default": "null"
          },
          "variant": {
            "type": "DuxTagVariant",
            "required": false,
            "description": "标签的视觉样式，决定了颜色等。",
            "default": "DuxTagVariantDefault.primary()"
          },
          "size": {
            "type": "DuxTagSize",
            "required": false,
            "description": "标签的尺寸，决定了字体大小、内边距等。",
            "default": "DuxTagSizeDefault.large()"
          }
        }
      }
    ],
    "attributes": {
      "variant": {
        "description": "定义标签的视觉样式，包括内容颜色、背景颜色、边框颜色等。可以通过 `DuxTagVariantDefault` 对象中的预设方法创建。",
        "params": {
          "value": {
            "type": "DuxTagVariant",
            "required": false,
            "description": "标签的视觉样式。"
          }
        }
      },
      "size": {
        "description": "定义标签的尺寸，包括内边距、字体样式、圆角和图标大小。可以通过 `DuxTagSizeDefault` 对象中的预设方法创建。",
        "params": {
          "value": {
            "type": "DuxTagSize",
            "required": false,
            "description": "标签的尺寸。"
          }
        }
      }
    },
    "events": {},
    "examples": [
      {
        "description": "创建一个主要样式的文本标签。",
        "code": "DuxTextTag(\n    text = \"Primary Tag\",\n    variant = DuxTagVariantDefault.primary()\n)"
      }
    ]
  },
  "DuxActionTag": {
    "description": "可交互的操作标签，可带右侧图标，并响应点击事件。它是对 DuxTag 的封装，简化了用于交互场景的 API。",
    "interfaces": [
      {
        "description": "DuxActionTag 的可组合函数接口。",
        "params": {
          "text": {
            "type": "String",
            "required": true,
            "description": "标签显示的文本。"
          },
          "modifier": {
            "type": "Modifier",
            "required": false,
            "description": "组件的修饰符。",
            "default": "Modifier"
          },
          "iconRes": {
            "type": "DrawableResource?",
            "required": false,
            "description": "标签右侧的图标资源。",
            "default": "null"
          },
          "enable": {
            "type": "Boolean",
            "required": false,
            "description": "是否启用点击事件。",
            "default": "true"
          },
          "variant": {
            "type": "DuxTagVariant",
            "required": false,
            "description": "标签的视觉样式。",
            "default": "DuxTagVariantDefault.primary()"
          },
          "size": {
            "type": "DuxTagSize",
            "required": false,
            "description": "标签的尺寸。",
            "default": "DuxTagSizeDefault.large()"
          },
          "onClick": {
            "type": "() -> Unit",
            "required": true,
            "description": "点击事件的回调。"
          }
        }
      }
    ],
    "attributes": {
      "enable": {
        "description": "控制标签是否可以响应点击事件。",
        "params": {
          "value": {
            "type": "Boolean",
            "required": false,
            "description": "是否启用。",
            "default": "true"
          }
        }
      }
    },
    "events": {
      "onClick": {
        "description": "当 `DuxActionTag` 被点击时触发。",
        "params": {}
      }
    },
    "examples": [
      {
        "description": "创建一个可点击的、带有删除图标的操作标签。",
        "code": "DuxActionTag(\n    text = \"Deletable Tag\",\n    iconRes = R.drawable.ic_delete, // 假设有这个资源\n    onClick = { /* handle delete */ },\n    variant = DuxTagVariantDefault.secondaryNormal()\n)"
      }
    ]
  },
  "DuxMediaTag": {
    "description": "媒体标签，用于视频等场景，有亮色和暗色两种模式。它是对 DuxTag 的封装，提供了特定于媒体场景的样式。",
    "interfaces": [
      {
        "description": "DuxMediaTag 的可组合函数接口。",
        "params": {
          "text": {
            "type": "String",
            "required": true,
            "description": "标签显示的文本。"
          },
          "modifier": {
            "type": "Modifier",
            "required": false,
            "description": "组件的修饰符。",
            "default": "Modifier"
          },
          "iconRes": {
            "type": "DrawableResource?",
            "required": false,
            "description": "标签左侧的图标资源。",
            "default": "null"
          },
          "isLight": {
            "type": "Boolean",
            "required": false,
            "description": "是否为亮色模式。`true` 为亮色（白字黑底），`false` 为暗色（黑字白底）。",
            "default": "true"
          }
        }
      }
    ],
    "attributes": {
      "isLight": {
        "description": "切换亮色和暗色模式。",
        "params": {
          "value": {
            "type": "Boolean",
            "required": false,
            "description": "是否为亮色模式。",
            "default": "true"
          }
        }
      }
    },
    "events": {},
    "examples": [
      {
        "description": "创建一个用于视频时间戳的亮色媒体标签。",
        "code": "DuxMediaTag(\n    text = \"01:23\",\n    iconRes = R.drawable.ic_play, // 假设有这个资源\n    isLight = true\n)"
      }
    ]
  },
  "DuxTag": {
    "description": "通用的基础标签组件，是其他 Dux 标签组件的底层实现。它提供了最全面的配置选项，包括左右图标、点击事件等，适用于需要高度自定义的场景。",
    "interfaces": [
      {
        "description": "DuxTag 的可组合函数接口。",
        "params": {
          "text": {
            "type": "String",
            "required": true,
            "description": "标签显示的文本。"
          },
          "modifier": {
            "type": "Modifier",
            "required": false,
            "description": "组件的修饰符。",
            "default": "Modifier"
          },
          "rightIconRes": {
            "type": "DrawableResource?",
            "required": false,
            "description": "标签右侧的图标资源。",
            "default": "null"
          },
          "leftIconRes": {
            "type": "DrawableResource?",
            "required": false,
            "description": "标签左侧的图标资源。",
            "default": "null"
          },
          "variant": {
            "type": "DuxTagVariant",
            "required": false,
            "description": "标签的视觉样式。",
            "default": "DuxTagVariantDefault.primary()"
          },
          "size": {
            "type": "DuxTagSize",
            "required": false,
            "description": "标签的尺寸。",
            "default": "DuxTagSizeDefault.large()"
          },
          "onClick": {
            "type": "() -> Unit",
            "required": true,
            "description": "点击事件的回调。"
          },
          "enable": {
            "type": "Boolean",
            "required": false,
            "description": "是否启用点击事件。",
            "default": "false"
          }
        }
      }
    ],
    "attributes": {},
    "events": {
      "onClick": {
        "description": "当标签被点击且 `enable` 为 `true` 时触发。",
        "params": {}
      }
    },
    "examples": [
      {
        "description": "使用 DuxTag 创建一个自定义的、可点击的标签，同时带有左右图标。",
        "code": "DuxTag(\n    text = \"Custom Tag\",\n    leftIconRes = R.drawable.ic_left,\n    rightIconRes = R.drawable.ic_right,\n    onClick = { /* handle click */ },\n    enable = true,\n    variant = DuxTagVariantDefault.tertiaryHighlight(),\n    size = DuxTagSizeDefault.medium()\n)"
      }
    ]
  }
}
```

## DuxIcon
```json
{
  "DuxIcon": {
    "description": "基础图标组件，用于显示矢量图标。",
    "interfaces": [
      {
        "description": "标准图标组件",
        "params": {
          "iconRes": {
            "type": "DrawableResource",
            "required": true,
            "description": "图标资源。"
          },
          "contentDescription": {
            "type": "String?",
            "required": false,
            "description": "无障碍描述文本。"
          },
          "modifier": {
            "type": "Modifier",
            "required": false,
            "description": "布局修饰符。",
            "default": "Modifier"
          },
          "tint": {
            "type": "Color",
            "required": false,
            "description": "图标颜色。",
            "default": "Color.Unspecified"
          },
          "size": {
            "type": "Dp",
            "required": false,
            "description": "图标尺寸。",
            "default": "Dp.Unspecified"
          }
        }
      }
    ],
    "attributes": {
      "defaultSize": {
        "description": "默认图标尺寸。",
        "params": {
          "value": {
            "type": "Dp",
            "required": false,
            "description": "默认尺寸值。",
            "default": "24.dp"
          }
        }
      },
      "contentScale": {
        "description": "内容缩放模式。",
        "params": {
          "value": {
            "type": "ContentScale",
            "required": false,
            "description": "缩放模式。",
            "default": "ContentScale.Fit"
          }
        }
      }
    },
    "events": {},
    "examples": [
      {
        "description": "基础图标示例",
        "code": "DuxIcon(iconRes = Res.drawable.ic_close, contentDescription = \"关闭\")"
      },
      {
        "description": "自定义颜色和大小的图标示例",
        "code": "DuxIcon(iconRes = Res.drawable.ic_close, tint = Color.Red, size = 32.dp)"
      }
    ]
  }
}
```

## DuxTitleBar
```json
{
  "DuxTitleBar": {
    "description": "抖音标题栏组件，包含左右操作按钮和标题区域。",
    "interfaces": [
      {
        "description": "标准标题栏组件",
        "params": {
          "modifier": {
            "type": "Modifier",
            "required": false,
            "description": "布局修饰符",
            "default": "Modifier"
          },
          "startAction": {
            "type": "@Composable DuxTitleBarScope.() -> Unit",
            "required": false,
            "description": "左侧操作区域"
          },
          "endAction": {
            "type": "@Composable DuxTitleBarScope.() -> Unit",
            "required": false,
            "description": "右侧操作区域"
          },
          "titleAction": {
            "type": "DuxTitleAction",
            "required": false,
            "description": "标题区域配置",
            "default": "DuxTitleAction()"
          },
          "showSpacer": {
            "type": "Boolean",
            "required": false,
            "description": "是否显示底部分隔线",
            "default": "true"
          }
        }
      }
    ],
    "attributes": {
      "titleAction": {
        "description": "标题区域配置",
        "params": {
          "title": {
            "type": "String",
            "required": false,
            "description": "主标题文本",
            "default": ""
          },
          "subTitle": {
            "type": "String",
            "required": false,
            "description": "副标题文本",
            "default": ""
          },
          "iconRes": {
            "type": "DrawableResource",
            "required": false,
            "description": "标题图标"
          },
          "onClick": {
            "type": "() -> Unit",
            "required": false,
            "description": "点击回调",
            "default": "{}"
          },
          "alpha": {
            "type": "Float",
            "required": false,
            "description": "透明度",
            "default": "1f"
          }
        }
      }
    },
    "events": {},
    "examples": [
      {
        "description": "基本标题栏使用示例",
        "code": "DuxTitleBar(
  startAction = {
    ActionIcon(iconRes = Icons.Default.ArrowBack) { /* 返回操作 */ }
  },
  endAction = {
    ActionButton(text = "完成", onClick = { /* 完成操作 */ })
  },
  titleAction = DuxTitleAction(
    title = "标题",
    subTitle = "副标题",
    onClick = { /* 标题点击 */ }
  )
)"
      }
    ]
  },
}
```

## DuxHorizontalDivider
```json
{
  "DuxHorizontalDivider": {
    "description": "一个水平分割线，用于在布局中分隔内容。",
    "interfaces": [
      {
        "description": "创建一个填满宽度并高度为 0.5dp 的水平分割线。",
        "params": {}
      }
    ],
    "attributes": {},
    "events": {},
    "examples": [
      {
        "description": "展示一个水平分割线。",
        "code": "@Composable\nfun HorizontalDividerExample() {\n    DuxHorizontalDivider()\n}"
      }
    ]
  },
  "DuxVerticalDivider": {
    "description": "一个垂直分割线，用于在布局中分隔内容。",
    "interfaces": [
      {
        "description": "创建一个填满高度并宽度为 0.5dp 的垂直分割线。",
        "params": {}
      }
    ],
    "attributes": {},
    "events": {},
    "examples": [
      {
        "description": "展示一个垂直分割线。",
        "code": "@Composable\nfun VerticalDividerExample() {\n    DuxVerticalDivider()\n}"
      }
    ]
  }
}
```

## DuxBadge
```json
{
  "DuxBadge": {
    "description": "抖音徽章组件，支持点状、数字和文本三种样式。",
    "interfaces": [
      {
        "description": "标准徽章组件",
        "params": {
          "content": {
            "type": "String?",
            "required": false,
            "description": "徽章内容，null或空字符串显示点状徽章，数字显示数字徽章，其他显示文本徽章",
            "default": "null"
          },
          "modifier": {
            "type": "Modifier",
            "required": false,
            "description": "布局修饰符",
            "default": "Modifier"
          }
        }
      }
    ],
    "attributes": {
      "badgeState": {
        "description": "徽章状态，根据内容自动判断",
        "params": {
          "Dot": {
            "type": "DuxBadgeState",
            "required": false,
            "description": "点状徽章",
            "default": "当content为null或空字符串时"
          },
          "NumberSingle": {
            "type": "DuxBadgeState",
            "required": false,
            "description": "单个数字徽章(1-9)",
            "default": "当content为1-9时"
          },
          "NumberMulti": {
            "type": "DuxBadgeState",
            "required": false,
            "description": "多个数字徽章(10-99)",
            "default": "当content为10-99时"
          },
          "NumberPlus": {
            "type": "DuxBadgeState",
            "required": false,
            "description": "带加号的数字徽章(100+)",
            "default": "当content≥100时"
          },
          "Text": {
            "type": "DuxBadgeState",
            "required": false,
            "description": "文本徽章",
            "default": "当content为非数字文本时"
          }
        }
      },
      "size": {
        "description": "徽章尺寸",
        "params": {
          "DefaultDotSize": {
            "type": "Dp",
            "required": false,
            "description": "点状徽章尺寸",
            "default": "8.dp"
          },
          "DefaultLargeSize": {
            "type": "Dp",
            "required": false,
            "description": "非点状徽章尺寸",
            "default": "16.dp"
          }
        }
      },
      "fontSize": {
        "description": "徽章文字大小",
        "params": {
          "DefaultNumberFontSize": {
            "type": "Int",
            "required": false,
            "description": "数字徽章字体大小",
            "default": "11"
          },
          "DefaultTextFontSize": {
            "type": "Int",
            "required": false,
            "description": "文本徽章字体大小",
            "default": "10"
          }
        }
      },
      "color": {
        "description": "徽章颜色",
        "params": {
          "BadgeColor": {
            "type": "Color",
            "required": false,
            "description": "徽章背景色",
            "default": "Color(0xFFFE2355)"
          }
        }
      }
    },
    "events": {},
    "examples": [
      {
        "description": "点状徽章示例",
        "code": "DuxBadge()"
      },
      {
        "description": "数字徽章示例",
        "code": "DuxBadge(content = \"5\")"
      },
      {
        "description": "大数字徽章示例",
        "code": "DuxBadge(content = \"99\")"
      },
      {
        "description": "带加号的大数字徽章示例",
        "code": "DuxBadge(content = \"100\")"
      },
      {
        "description": "文本徽章示例",
        "code": "DuxBadge(content = \"New\")"
      }
    ]
  }
}
```

## DuxCheckBox
```json
{
    "DuxCheckBox": {
        "description": "DuxCheckBox是DUX设计语言中的复选框组件，允许用户从一组选项中选择一个或多个。",
        "interfaces": [
            {
                "description": "标准的DuxCheckBox组件。具体指南请参考",
                "params": {
                    "checked": {
                        "type": "Boolean",
                        "required": true,
                        "description": "复选框是否被选中。"
                    },
                    "onCheckedChange": {
                        "type": "((Boolean) -> Unit)?",
                        "required": true,
                        "description": "当复选框的选中状态改变时调用的回调函数。"
                    },
                    "modifier": {
                        "type": "Modifier",
                        "required": false,
                        "description": "应用于复选框的Modifier。",
                        "default": "Modifier"
                    },
                    "enabled": {
                        "type": "Boolean",
                        "required": false,
                        "description": "复选框是否可用。",
                        "default": "true"
                    },
                    "colors": {
                        "type": "CheckboxColors",
                        "required": false,
                        "description": "复选框的颜色配置。",
                        "default": "DuxCheckboxDefaults.colors()"
                    }
                }
            }
        ],
        "attributes": {
            "colors": {
                "description": "复选框的颜色配置，决定了选中、未选中和禁用状态下的颜色。DuxCheckboxDefaults.colors()提供了默认的颜色配置。",
                "params": {
                    "value": {
                        "type": "CheckboxColors",
                        "required": false,
                        "description": "复选框的颜色。",
                        "default": "DuxCheckboxDefaults.colors()"
                    }
                }
            }
        },
        "events": {
            "onCheckedChange": {
                "description": "当复选框的选中状态改变时触发。",
                "params": {
                    "checked": {
                        "type": "Boolean",
                        "description": "新的选中状态。"
                    }
                }
            }
        },
        "examples": [
            {
                "description": "创建一个简单的复选框，并根据其状态更新文本。",
                "code": "var checked by remember { mutableStateOf(true) }\nColumn {\n    DuxCheckBox(checked = checked, onCheckedChange = { checked = it })\n    Text(text = if (checked) \"Checked\" else \"Unchecked\")\n}"
            }
        ]
    }
}
```

## DuxBasicPanel
```json
{
  "DuxBasicPanel": {
    "description": "一个基本的面板容器，包含一个页眉和内容区域。",
    "interfaces": [
      {
        "description": "创建一个DuxBasicPanel",
        "params": {
          "modifier": {
            "type": "Modifier",
            "required": false,
            "description": "用于自定义面板外观的Modifier",
            "default": "Modifier"
          },
          "header": {
            "type": "@Composable () -> Unit",
            "required": true,
            "description": "面板的页眉内容"
          },
          "content": {
            "type": "@Composable () -> Unit",
            "required": true,
            "description": "面板的主体内容"
          }
        }
      }
    ],
    "attributes": {},
    "events": {},
    "examples": [
      {
        "description": "显示一个带文本页眉和简单内容的面板。",
        "code": "DuxBasicPanel(\n    header = { \n        DuxBasicPanelHeader(\n            leftTitle = \"取消\", \n            middleTitle = \"标题\", \n            rightTitle = \"完成\",\n            onLeftClick = {},\n            onRightClick = {}\n        ) \n    },\n    content = { \n        Text(\"这是面板内容\") \n    }\n)"
      }
    ]
  },
  "DuxBasicPanelHeader": {
    "description": "DuxBasicPanel的页眉，支持文本或图标。",
    "interfaces": [
      {
        "description": "创建带文本标题的页眉",
        "params": {
          "leftTitle": {
            "type": "String",
            "required": true,
            "description": "左侧标题"
          },
          "rightTitle": {
            "type": "String",
            "required": true,
            "description": "右侧标题"
          },
          "middleTitle": {
            "type": "String",
            "required": true,
            "description": "中间标题"
          },
          "onLeftClick": {
            "type": "() -> Unit",
            "required": false,
            "description": "左侧点击事件"
          },
          "onRightClick": {
            "type": "() -> Unit",
            "required": false,
            "description": "右侧点击事件"
          }
        }
      },
      {
        "description": "创建带图标的页眉",
        "params": {
          "iconLeft": {
            "type": "DrawableResource",
            "required": true,
            "description": "左侧图标"
          },
          "middleTitle": {
            "type": "String",
            "required": true,
            "description": "中间标题"
          },
          "iconRight": {
            "type": "DrawableResource",
            "required": true,
            "description": "右侧图标"
          },
          "onLeftClick": {
            "type": "() -> Unit",
            "required": false,
            "description": "左侧图标点击事件"
          },
          "onRightClick": {
            "type": "() -> Unit",
            "required": false,
            "description": "右侧图标点击事件"
          }
        }
      }
    ],
    "attributes": {},
    "events": {
        "onLeftClick": {
            "description": "当用户点击左侧标题或图标时触发。",
            "params": {}
        },
        "onRightClick": {
            "description": "当用户点击右侧标题或图标时触发。",
            "params": {}
        }
    },
    "examples": [
      {
        "description": "显示一个带文本标题的页眉。",
        "code": "DuxBasicPanelHeader(\n    leftTitle = \"返回\",\n    middleTitle = \"设置\",\n    rightTitle = \"保存\",\n    onLeftClick = { /* 返回逻辑 */ },\n    onRightClick = { /* 保存逻辑 */ }\n)"
      },
      {
        "description": "显示一个带图标的页眉。",
        "code": "DuxBasicPanelHeader(\n    iconLeft = Res.drawable.ic_back,\n    middleTitle = \"个人信息\",\n    iconRight = Res.drawable.ic_edit,\n    onLeftClick = { /* 返回逻辑 */ },\n    onRightClick = { /* 编辑逻辑 */ }\n)"
      }
    ]
  }
}
```
"""

def get_user_prompt(figma_json_str: str):
    return f"""以下是你需要还原的figma的json文件。

    ```json
    {figma_json_str}
    ```
"""


def translate_figma_json_to_code(figma_file_url: str, image_filepath: str = None, page_index: int = 0):
    exported_icons = export_figma_icons(figma_file_url)
    exported_icons_prompt = ""
    if exported_icons:
        exported_icons_prompt += "从 figma 文件中导出的 icon 有：\n"
        for icon in exported_icons:
            exported_icons_prompt += icon + "\n"
    with open(figma_file_url, "r") as f:
        figma_json = json.load(f)
    figma_json_str = json.dumps(figma_json, indent=4)
    
    system_prompt = get_system_prompt()
    component_knowledge_prompt = get_component_knowledge_prompt()
    system_prompt += "\n" + component_knowledge_prompt

    user_prompt = get_user_prompt(figma_json_str)
    if exported_icons_prompt:
        user_prompt += "\n" + exported_icons_prompt
    compose_code = chat_to_genimi25_pro(system_prompt, user_prompt, image_filepath)
    write_page_code(compose_code, page_index)
    used_icons = find_used_icons(compose_code)
    remove_useless_icons(exported_icons, used_icons)
    zip_icons(page_index)
    return compose_code


def write_page_code(kotlin_code: str, page_index: int):
    filepath = "dataset/page" + str(page_index) + ".kt"
    with open(filepath, "+a") as f:
        f.write(kotlin_code)


def zip_icons(page_index: int):
    # 定义命令
    command = ["zip", "-r", "res_drawable-xxhdpi-page" + str(page_index) + ".zip", "res/drawable-xxhdpi", "-x", "*.DS_Store"]

    # 执行命令
    try:
        subprocess.run(command, check=True)
        print("ZIP 压缩成功！")
    except subprocess.CalledProcessError as e:
        print(f"压缩失败: {e}")


def remove_useless_icons(exported_icons, used_icons):
    need_delete_icons = set(exported_icons) - set(used_icons)
    for icon in need_delete_icons:
        if os.path.exists(icon):
            os.remove(icon)
            print(f"remove useless icon {icon}")
        else:
            print(f"icon not found: {icon}")


figma_file_urls = [
    ("https://www.figma.com/design/lEIy4VXyF0rnimZnnfYqqB/D2C-figma-demo?node-id=1-465&t=jW3rBPeznhI23XZD-0", "1:465", "dataset/publish_video.png"),
    # ("https://www.figma.com/design/lEIy4VXyF0rnimZnnfYqqB/D2C-figma-demo?node-id=1-700&t=jW3rBPeznhI23XZD-0", "1:700", "dataset/messages.png"),
    ("https://www.figma.com/design/4mA2iRrJRgfNIFL1l66yVk/D2C-test-case-2?node-id=1-1427&t=LhXxxjXmXXZLionl-0", "1:1427", "dataset/album.png"),
    ("https://www.figma.com/design/4mA2iRrJRgfNIFL1l66yVk/D2C-test-case-2?node-id=1-1767&t=LhXxxjXmXXZLionl-0", "1:1767", "dataset/edit_video.png"),
    ("https://www.figma.com/design/4mA2iRrJRgfNIFL1l66yVk/D2C-test-case-2?node-id=1-460&t=LhXxxjXmXXZLionl-0", "1:460", "dataset/continue_video.png"),
]


def find_used_icons(kotlin_code:str) -> list[str]:
    """
    extract all icons used in kotlin_code.

    icon format:  R.drawable.xxx
    """
    pattern = r"R\.drawable\.([a-zA-Z0-9_]+)"
    icons = re.findall(pattern, kotlin_code)
    return ["res/drawable-xxhdpi/" + icon + ".png" for icon in list(set(icons))]


def init_d2c_container()->str:
  workspace_dir = tempfile.mkdtemp()
  original_cwd = os.getcwd()
  try:
      os.chdir(workspace_dir)
      
      # Clone the repository
      clone_command = ["git", "clone", "git@code.byted.org:ugc-android/kmp-d2c-evaluate.git"]
      result = subprocess.run(clone_command, capture_output=True, text=True)
      if result.returncode != 0:
          raise Exception(f"Failed to clone repository: {result.stderr}")
    
      # Run gradlew command
      project_dir = "kmp-d2c-evaluate"
      gradlew_command = ["./gradlew", "updateDebugScreenshotTest"]
      result = subprocess.run(gradlew_command, cwd=project_dir, capture_output=True, text=True)
      if result.returncode != 0:
          raise Exception(f"Failed to run gradlew command: {result.stderr}")
  finally:
      os.chdir(original_cwd)
        
  return workspace_dir


class TranslationFigmaState(BaseModel):
    figma_file_key: str
    figma_node_json: dict
    workspace_dir: str = None

def translate_node():
  return

def translate_figma_agent(figma_file_url: str):
  builder = StateGraph(TranslationFigmaState)
  builder.add_node("init_workspace", init_d2c_container)
  builder.add_node("export_icon", export_icon_block)
  builder.add_node("export_icon", export_icon_block)
  builder.add_node("export_icon", export_icon_block)
  builder.add_edge(START, "init_workspace")
  builder.add_edge("init_workspace", "recognize_icon")
  builder.add_edge("recognize_icon", "export_icon")
  builder.add_edge("export_icon", END)
  builder.set_entry_point("recognize_icon")
  builder.set_finish_point("export_icon")
  graph = builder.compile()
  result = graph.invoke({
      "figma_file_key": FIGMA_FILE_KEY,
      "figma_node_json": node_json
  })

  exported_icons = export_figma_icons(figma_file_url)
  exported_icons_prompt = ""
  if exported_icons:
      exported_icons_prompt += "从 figma 文件中导出的 icon 有：\n"
      for icon in exported_icons:
          exported_icons_prompt += icon + "\n"
  with open(figma_file_url, "r") as f:
      figma_json = json.load(f)
  figma_json_str = json.dumps(figma_json, indent=4)
  
  system_prompt = get_system_prompt()
  component_knowledge_prompt = get_component_knowledge_prompt()
  system_prompt += "\n" + component_knowledge_prompt

  user_prompt = get_user_prompt(figma_json_str)
  if exported_icons_prompt:
      user_prompt += "\n" + exported_icons_prompt
  compose_code = chat_to_genimi25_pro(system_prompt, user_prompt, image_filepath)
  write_page_code(compose_code, page_index)
  used_icons = find_used_icons(compose_code)
  remove_useless_icons(exported_icons, used_icons)
  zip_icons(page_index)
  return compose_code


if __name__ == "__main__":
    page_index = 2
    figma_json_filepath = f"dataset/figma_file{page_index}.json"
    image_filepath = figma_file_urls[page_index][2]
    result = translate_figma_json_to_code(figma_json_filepath, image_filepath, page_index)
    print(result)