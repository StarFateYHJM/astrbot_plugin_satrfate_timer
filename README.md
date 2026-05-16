# Satrfate Timer — 极简定时问候插件

为 AstrBot 提供可配置的定时消息发送功能。支持私聊/群聊、固定文本或 LLM 动态生成、@全体成员。

## 核心特性

- 定时触发，HH:MM 格式
- 支持私聊和群聊（通过 UMO）
- 可选 LLM 动态生成内容（支持任意 OpenAI 兼容 API）
- 可选 @全体成员（仅群聊有效）
- 同日同任务只触发一次，自动防重复
- 使用系统时间，无需网络校准
- 配置面板友好，字段分开填写
- 代码极简，不到 100 行

## 快速配置

1. 在 AstrBot 面板中启用本插件。
2. 在插件配置中添加定时任务：
   - **触发时间**：HH:MM 格式（如 `08:00`）
   - **目标会话UMO**：`FriendMessage:QQ号`（私聊）或 `GroupMessage:群号`（群聊）
   - **发送内容**：固定文本或 LLM 提示词
   - **@全体成员**：仅群聊有效，开启后消息会自动 @全体
3. 如需 LLM 动态生成，开启 `use_llm` 并填写 API 信息。
4. 保存配置，插件自动生效。

## 配置项说明

| 配置项 | 类型 | 说明 | 默认值 |
| :--- | :--- | :--- | :--- |
| `use_llm` | bool | 开启 LLM 生成内容 | `false` |
| `api_base` | string | LLM API 地址 | `https://api.deepseek.com/v1` |
| `api_key` | string | LLM API 密钥 | 空 |
| `model` | string | 模型名称 | `deepseek-v4-flash` |
| `system_prompt` | text | 系统提示词（人格设定） | 空 |
| `tasks` | list | 定时任务列表 | `[]` |

### 任务字段

| 字段 | 类型 | 说明 | 默认值 |
| :--- | :--- | :--- | :--- |
| `time` | string | 触发时间（HH:MM） | `08:00` |
| `umo` | string | 目标会话 UMO | 空 |
| `prompt` | text | 发送内容或 LLM 提示词 | 空 |
| `at_all` | bool | 是否 @全体成员 | `false` |

## UMO 格式

- 私聊：`FriendMessage:QQ号`（如 `FriendMessage:123456789`）
- 群聊：`GroupMessage:群号`（如 `GroupMessage:987654321`）

## 日志输出

插件仅输出以下日志（由 AstrBot 全局日志等级控制）：

- `已加载 X 个任务`
- `触发 HH:MM`
- `发送成功`
- `发送失败`（含错误详情）
- `LLM生成失败`
- `缺少 api_key`

## 注意事项

- 群聊 UMO 格式为 `GroupMessage:群号`，不需要带 QQ 号前缀
- @全体成员 仅在群聊中有效，私聊无效
- LLM 生成需要正确配置 `api_base`、`api_key`、`model`
- 如果不开启 LLM，直接发送 `prompt` 中的固定文本

## 版本历史

- v1.7.2：精简代码，优化日志输出，修复异常信息显示
- v1.6.0：新增 @全体成员 功能
- v1.5.0：新增 LLM 动态生成内容
- v1.0.0：首次发布，支持定时发送固定文本

## 许可证

MIT License
Copyright (c) 2026 YHJM
