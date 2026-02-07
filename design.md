好，那我直接把你 PRD 里最关键、**决定后期切换是否痛苦**的《技术设计附录》补齐：**Runner 接口 + Event/Message/Artifact schema + AF 映射表 + 上下文拼装规则 + 存储表结构 + 终止/暂停协议 + 最小目录结构**。你拿去就能拆任务开干。

---

# 技术设计附录（面向可替换框架的会议系统）

## A. 核心原则（Scope Lock）

1. **Domain 不依赖任何 agent 框架**（不 import agent_framework / langgraph 等）
2. **唯一框架耦合点 = Runner 层**
3. 对外与存储只用你自家的 **Message/Event/Artifact** 三套 schema
4. 上下文策略（shared/layered）属于 **Domain**，不是框架

---

## B. 目录结构（最小可落地）

```
meeting/
  domain/
    models.py              # Message/Event/Artifact dataclasses + schema
    state_machine.py        # meeting 状态机 & round 控制
    context_builder.py      # shared/layered 上下文拼装
    termination.py          # 终止条件（硬上限+收敛）
    pause_resume.py         # Pause/Resume 协议
    artifacts.py            # ADR/Tasks/Risks 生成与校验
  runners/
    base.py                # Runner 接口（框架无关）
    af_groupchat_runner.py  # Agent Framework 实现（唯一依赖 AF）
  storage/
    repo.py                # 写 events/artifacts/memories
    schema.sql             # sqlite/postgres 表结构
  api/
    server.py              # REST (FastAPI)
  cli/
    run_meeting.py
```

---

## C. 你的三套稳定协议（以后换框架不变）

### C1) Message（对话消息）

用于：输入给 Runner、回放展示、生成摘要/工件的基础素材。

```python
from dataclasses import dataclass
from typing import Literal, Optional, Dict, Any

Role = Literal["system", "user", "assistant", "tool"]

@dataclass
class Message:
    role: Role
    content: str
    name: Optional[str] = None          # 角色名，如 "ChiefArchitect"
    ts_ms: Optional[int] = None
    meta: Optional[Dict[str, Any]] = None  # 引用、证据链接、评分等
```

### C2) Event（事件流：UI/日志/回放统一）

用于：流式展示、多轮执行记录、调试、审计。

```python
EventType = Literal[
    "round_started",
    "speaker_selected",
    "token",
    "agent_message",
    "summary_written",
    "artifact_written",
    "pause",
    "resume",
    "metric",
    "error",
    "finished",
]

@dataclass
class Event:
    type: EventType
    run_id: str
    ts_ms: int
    actor: str              # "orchestrator" / "agent:ChiefArchitect" / "system"
    payload: Dict[str, Any] # 强约束的结构
```

**Event payload 约定（常用）**

* `token`: `{ "text": "...", "message_id": "...", "role": "ChiefArchitect" }`
* `agent_message`: `{ "message": Message, "message_id": "...", "round": 3 }`
* `artifact_written`: `{ "artifact_type": "ADR|TASKS|RISKS", "version": "v1", "content": {...} }`
* `pause`: `{ "pause_reason": "...", "questions": [...], "resume_token": "..." }`

### C3) Artifact（工件：最终交付物）

用于：产出与验收。

```python
ArtifactType = Literal["ADR", "TASKS", "RISKS", "MINUTES", "SUMMARY"]

@dataclass
class Artifact:
    run_id: str
    type: ArtifactType
    version: str            # "v1"
    content: Dict[str, Any] # 严格 schema 校验
    created_ts_ms: int
```

---

## D. Runner 接口（唯一可替换点）

### D1) 输入：ExecutionContext

Domain 负责把“这一轮应该给角色看的东西”拼装好，然后交给 Runner。

```python
from typing import AsyncIterator, Protocol, List

@dataclass
class ExecutionContext:
    meeting_id: str
    run_id: str
    round: int
    speaker: str                    # "ChiefArchitect"
    context_mode: Literal["shared", "layered"]
    public_messages: List[Message]  # 公共上下文（可能是摘要后的）
    private_memory: Dict[str, Any]  # 该 speaker 的私有记忆（layered 才有）
    system_instructions: str        # 角色卡+输出约束
    user_task: str                  # 当前议题/用户最新追加
    limits: Dict[str, Any]          # max_tokens/max_time/retry 等
```

### D2) 接口：RoleRunner

```python
class RoleRunner(Protocol):
    async def run(self, ctx: ExecutionContext) -> AsyncIterator[Event]:
        ...
```

**保证**：Domain/Storage/UI 只消费 Event，不知道 AF 存在。

---

## E. Agent Framework Group Chat → 你的 Event 映射表

AF Group Chat 会给你两类关键事件：

* `AgentResponseUpdateEvent`（流式 token）
* `WorkflowOutputEvent`（最终对话历史）
  （这些都在 AF 内部事件流里体现，Domain 不接触。）

**映射规则（在 af_groupchat_runner.py 里做）**

| AF 事件                         | 你发出的 Event.type    | payload                        |
| ----------------------------- | ------------------ | ------------------------------ |
| 选 speaker（你自己做）               | `speaker_selected` | `{speaker, round, strategy}`   |
| AgentResponseUpdateEvent      | `token`            | `{text, message_id, role}`     |
| 一轮 speaker 输出完成（可由 runner 组装） | `agent_message`    | `{message, message_id, round}` |
| WorkflowOutputEvent（全历史）      | 只用来“对齐/补齐”         | 不直接透出；用于构建对话记录                 |

> 关键：**别把 AF 的 message 类型直接存库**，都转成你的 Message/Event。

---

## F. 上下文策略（shared vs layered）——Domain 拼装输入

### F1) shared（MVP）

`speaker_input = [system(role_card), public_history(full), user_task]`

* public_messages = 全量对话（或限制长度的滑窗）
* 不使用 private_memory（可为空）

### F2) layered（V1 必做）

`speaker_input = [system(role_card), public_summary, relevant_quotes, private_memory_summary, user_task]`

**公共部分（PublicContext）只包含：**

1. 用户最新输入/约束
2. Recorder 每轮摘要（长度上限，如 300~600 字）
3. 每个角色“对外结论段”（不是推理草稿）

**私有部分（PrivateMemory）每角色独立：**

* assumptions / TODO 验证 / 个人偏好 / 草稿 / 风险池

**相关摘录（relevant_quotes）怎么选？（先简单）**

* 从最近 1~2 轮里抽取每个角色的 “decision_recommendation / top risks” 片段
* 或基于关键词（QPS、成本、合规）做轻量匹配

> 这样你就实现了：**独立上下文 + 吸收他人观点**（吸收的是“摘要/摘录”）。

---

## G. 终止条件与“多聊几轮但能收敛”

建议终止策略 = **硬上限 + 收敛条件**（两者取先达成）。

### G1) 硬上限（避免跑飞）

* `round >= max_rounds` → stop

### G2) 收敛条件（像开会）

任一满足即可 stop：

1. Recorder 已产出 ADR/Tasks/Risks 且 schema 校验通过
2. open_questions ≤ K（比如 2）且分歧点 ≤ K（比如 1）
3. 连续两轮“决策建议不再变化”（简单 diff）

实现建议：Domain 每轮结束做一次 `ConvergenceCheck`，生成事件：

* `metric`: `{open_questions_count, disagreements_count, convergence_score}`

---

## H. Pause/Resume 协议（强烈建议固定化）

### H1) Pause 事件（Domain 发出）

```json
{
  "type": "pause",
  "actor": "system",
  "payload": {
    "pause_reason": "missing_info|need_approval|budget_limit",
    "questions": [
      {"key":"qps_peak","ask":"峰值QPS？","why":"容量与缓存策略依赖","required":true}
    ],
    "resume_token": "opaque_token",
    "suggested_next": "answer_questions|choose_option_A_or_B"
  }
}
```

### H2) Resume 事件（用户触发）

```json
{
  "type": "resume",
  "actor": "user",
  "payload": {
    "resume_token": "...",
    "answers": {"qps_peak": 1200, "must_onprem": true}
  }
}
```

Domain 收到 resume 后：

* 把 answers 写入公共上下文（以及必要的角色私有记忆）
* 回到 Discussion 继续跑

---

## I. 存储表结构（MVP 可用，V1 扩展）

### I1) runs

* run_id (pk)
* meeting_id
* status: RUNNING/PAUSED/DONE/FAILED
* config_json
* started_at, ended_at

### I2) events（append-only）

* id (pk)
* run_id (idx)
* ts_ms
* type
* actor
* payload_json

### I3) artifacts

* id (pk)
* run_id (idx)
* type
* version
* content_json
* created_ts_ms

### I4) memories（layered）

* id (pk)
* run_id (idx)
* role_name (idx)
* content_json
* updated_ts_ms

> MVP 你甚至可以先 SQLite；后面切 PG 不影响，因为 schema 都是你自家的。

---

## J. 质量门禁（让输出“能用”而不是“好看”）

### J1) 角色输出 schema 校验

* 每个角色输出必须能 parse 成 JSON 并通过 schema
* 失败：自动触发一次 “repair prompt” 重试（最多 1 次）

### J2) Recorder 工件校验

* ADR/Tasks/Risks 全部 schema 通过才 `finished`
* 不通过：让 Recorder 进行修复，不要让会议 silently 结束

---

## K. 拆解任务清单（可直接分给同事）

### K1) Domain（会议引擎）

* 状态机（Intake/Discussion/Convergence/Gate/Finalize）
* termination & pause/resume
* context_builder(shared/layered)
* artifacts + schema 校验

### K2) Runner（AF 适配）

* `af_groupchat_runner.py`：把 AF 的流式事件映射为你的 Event
* 支持 N 轮：每轮调用/或一次 workflow 内部跑（你选一种，但对外都一样）

### K3) Storage

* events/artifacts/memories 落库
* replay API

### K4) API / CLI

* start run / append message / resume / get artifacts / stream events

---

如果你愿意，我下一步可以直接把 **“af_groupchat_runner.py 的实现骨架”** 和 **“Recorder/Chief/Skeptic 的最短角色卡（每个 8~12 行）”** 一并给你，这样你们团队基本可以当天把 MVP 跑起来。
