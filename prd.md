下面是一份**可直接拿去拆解任务**的 PRD（按阶段写清楚，每阶段目标/范围/交付/验收都给了）。你可以先用它找人分工，后面再细化成 Jira/Issue。

---

# PRD：多角色 AI 架构评审会议系统（MVP→V1→V2）

## 1. 背景与目标

### 背景

团队需要一个“开会就能出结果”的系统：用多个 AI 角色（架构师/安全/基础设施/红队/书记员）对某个架构方案进行评审，产出可落地的 **ADR + Tasks + Risks**，并支持多轮讨论、用户随时插入新信息。

### 目标（必须）

* 10~20 分钟内跑完一次会议，产出结构化工件：

  * ADR（决策记录）
  * Tasks（行动项/里程碑）
  * Risks（风险清单/缓解/验证）
* 支持**多轮**（N 轮）讨论，但必须可收敛、有停止条件
* 支持两种上下文模式：

  * **共享上下文（默认）**
  * **分层上下文**（公共摘要 + 角色私有记忆，避免污染）
* 支持**暂停/继续**（缺信息/需人确认时暂停）

### 非目标（MVP 不做）

* 复杂 UI（先 CLI/简易 Web）
* 多会议串联（Roadmap→评审→变更评审）
* 复杂权限/组织管理（先单租户/单工作区）

---

## 2. 关键概念与术语

* **Meeting**：一次会议实体（议题、配置、角色、状态）
* **Run**：一次执行（Meeting 可多次 Run）
* **Round**：一轮发言周期
* **Public Context**：公共频道可见信息（用户输入、公共摘要、关键发言）
* **Private Memory**：每个角色私有笔记/假设/草稿/证据引用
* **Artifact**：结构化工件（ADR/Tasks/Risks/Minutes）
* **Gate**：门禁（缺信息/需确认/风险超阈触发暂停）

---

## 3. 用户故事（User Stories）

1. 作为发起人，我输入议题和背景材料，选择角色组合与轮次上限，点击“开始会议”，系统自动跑完并给我 ADR/Tasks/Risks。
2. 作为发起人，我在会议中途补充约束（例如 QPS/预算/必须本地化），系统能继续跑并更新结论（不中断追加或暂停后继续均可）。
3. 作为发起人，当系统缺关键信息时，它能明确提出问题并暂停，等我回答后继续。
4. 作为审阅者，我能回放会议过程（谁说了什么、为什么收敛到这个决策）。

---

## 4. 总体流程（会议状态机）

### 状态机

1. **Intake**：收集议题/材料/约束
2. **Briefing**：给每个角色下发角色卡与输出格式
3. **Discussion**：多轮发言（可并行或串行）
4. **Convergence**：书记员/收敛器生成候选结论、冲突点、未决问题
5. **Gate**：若缺信息/需确认 → Pause；否则继续
6. **Finalize**：生成 ADR/Tasks/Risks（结构化校验通过）
7. **Done / Paused**

### 讨论编排模式（MVP 先做一种，V1 再扩）

* **Group Chat（串行）**：Orchestrator 选择下一位 speaker，逐轮发言（对齐 Agent Framework Group Chat）
* **并行发散**（V1）：同一轮多个角色并行出观点，再收敛

---

## 5. 核心功能需求

## 5.1 会议创建与配置

* 输入：title、topic、background（文本/链接/粘贴）、constraints（可选）
* 配置项：

  * roles：角色列表（可选模板）
  * max_rounds：最大轮次（默认 6）
  * context_mode：shared / layered（默认 shared）
  * termination：终止策略（默认 “硬上限 + 收敛条件”）
  * output_schema：工件 schema 版本（默认 v1）

**验收**

* 创建会议成功，保存配置，生成 meeting_id

---

## 5.2 角色系统（Role Cards）

内置角色模板（MVP 至少 4 个）：

* Chief Architect（主持/总架构）
* Infra Architect（基础设施/部署/可观测/成本）
* Security Architect（威胁建模/权限/合规）
* Skeptic（红队质疑）
* Recorder（书记员/工件生成）

角色输出必须遵循统一 schema（用于收敛）：

```json
{
  "assumptions": ["..."],
  "proposal": "....",
  "tradeoffs": ["..."],
  "risks": [{"risk":"", "impact":"H/M/L", "mitigation":"", "verification":""}],
  "questions": ["..."],
  "decision_recommendation": "..."
}
```

**验收**

* 任意角色输出可通过 JSON schema 校验（失败则自动重试/纠错一次）

---

## 5.3 多轮讨论与调度（Orchestrator）

* 支持 round-robin 选择 speaker（MVP）
* 支持智能 orchestrator（V1，可选）：

  * 根据当前 open_questions / 冲突点选择下一位角色
* 每轮产物：

  * public_message（对外可见）
  * private_update（写入该角色私有记忆，layered 模式）

**验收**

* 会议能跑完 N 轮，产生完整事件日志与每轮发言记录

---

## 5.4 上下文策略（重点：shared vs layered）

### shared（MVP 默认）

* 参与者看到完整公共对话历史（等同 Group Chat 共享上下文）

### layered（V1 必做）

* 公共上下文只包含：

  * 用户输入（最新）
  * 书记员生成的“会议摘要”（长度上限）
  * 每轮各角色的“结论段”（不是全量）
* 每个角色有私有记忆：

  * 自己的 assumptions/草稿/待验证列表/偏好
* 吸收机制：

  * 角色输入包含 “公共摘要 + 与其相关的观点摘录 + 私有记忆”

**验收**

* layered 模式下公共上下文不会随轮次线性膨胀（有摘要压缩策略）
* 角色能引用他人观点，但不会直接拿到全量对话

---

## 5.5 暂停/继续（Pause/Resume）

触发条件（MVP 至少支持缺信息暂停）：

* open_questions >= 阈值 且属于“关键约束”
* 需要用户二选一确认（例如选 A/B 方案）
  暂停时输出：

```json
{
  "pause_reason": "missing_info|need_approval",
  "questions": [{"key":"qps", "ask":"峰值QPS是多少？", "why":"容量与缓存策略依赖"}],
  "resume_token": "..."
}
```

继续时：

* 用户提供 answers，系统写入事件并继续 Discussion

**验收**

* 能在任意轮暂停并继续，最终工件仍可生成

---

## 5.6 工件生成（Artifacts）

最终必须生成三件（MVP 必做）：

### ADR（v1）

* context
* decision
* alternatives_considered
* consequences
* risks_summary
* open_questions
* next_steps

### Tasks（v1）

* task_id
* title
* owner_role（可选）
* priority
* estimate（S/M/L）
* dependencies

### Risks（v1）

* risk
* impact/probability
* mitigation
* verification
* owner_role

**验收**

* 三件工件都通过 schema 校验
* Recorder 必须引用会议摘要或角色输出中的关键点（可用引用字段）

---

## 5.7 事件日志与回放（MVP 最小实现）

事件类型：

* MEETING_CREATED
* USER_MESSAGE_ADDED
* ROUND_STARTED
* SPEAKER_SELECTED
* AGENT_OUTPUT
* SUMMARY_WRITTEN
* PAUSED / RESUMED
* ARTIFACT_WRITTEN
* MEETING_FINISHED

最小字段：

* event_id, meeting_id, run_id, ts, type, actor, payload

**验收**

* 任意 run 可回放出“轮次 + 发言 + 摘要 + 最终工件”

---

## 6. 非功能需求（NFR）

* **可控成本**：支持 max_rounds、max_tokens（或摘要长度上限）
* **确定性**：同一配置允许“近似可复现”（至少事件完整、步骤一致）
* **容错**：单角色失败可重试；连续失败触发降级/暂停
* **可观测**：记录每轮耗时、token、失败原因、重试次数
* **安全**：默认不外发私有记忆；可配置脱敏/禁止敏感字段

---

## 7. API / 数据结构（建议稿）

### REST（MVP）

* `POST /meetings` 创建会议
* `POST /meetings/{id}/runs` 启动 run
* `POST /meetings/{id}/runs/{runId}/messages` 追加用户输入
* `POST /meetings/{id}/runs/{runId}/resume` 继续
* `GET /meetings/{id}/runs/{runId}` 获取状态/工件
* `GET /meetings/{id}/runs/{runId}/events` 回放事件

### 数据表（最小）

* meetings(id, title, config_json, created_at)
* runs(id, meeting_id, status, started_at, ended_at)
* events(id, run_id, type, actor, payload_json, ts)
* artifacts(id, run_id, type, version, content_json, created_at)
* memories(id, run_id, role_name, content_json, updated_at)（layered 模式用）

---

## 8. 阶段计划（重点：每阶段清晰可拆）

# 阶段 0：PoC（1~2 天）

**目标**：本地跑通 Group Chat 多轮 + 打印过程
**范围**

* 2 个角色（Researcher/Writer）或 4 角色最简
* round-robin 调度
* 固定轮次终止
  **交付**
* 可运行脚本（CLI）
* 输出完整对话与最终文本总结
  **验收**
* 能连续跑 6 轮不崩
* 输出包含每轮 speaker 与内容

---

# 阶段 1：MVP（可用会议）（建议 1 周）

**目标**：开会→收敛→交付 ADR/Tasks/Risks
**范围**

* 角色模板（至少 4+Recorder）
* shared 上下文
* Pause/Resume（missing_info）
* 工件 schema 校验
* 事件日志落库（append-only）
  **交付**
* REST API + CLI/简易 Web（任选其一）
* artifacts：ADR/Tasks/Risks（JSON）
* run 回放接口（events）
  **验收（硬性）**
* 任何会议输入都能在 ≤ max_rounds 内结束（Done 或 Paused）
* 工件三件套必出且 schema 通过
* 可暂停并继续后仍产出一致的工件结构

---

# 阶段 2：V1（产品化关键能力）（建议 2~3 周）

**目标**：多轮更稳、更像真实会议（独立思考 + 吸收观点）
**范围**

* layered 上下文：公共摘要 + 私有记忆
* Recorder 每轮摘要（长度上限、结构化）
* 更智能的终止策略（硬上限 + 收敛条件）
* 失败重试/降级策略
* 基本可观测指标（耗时/token/失败率）
  **交付**
* context 策略可配置
* 每轮摘要与私有记忆可查看（按权限/开关）
  **验收**
* 10 轮会议仍能保持上下文不爆（摘要有效）
* layered 模式下角色输出差异显著（不明显同质化）
* 收敛条件能提前终止（不总是跑满轮次）

---

# 阶段 3：V2（平台化/可扩展）（可选）

**目标**：可插拔角色与工具、并行发散、多人协作
**范围**

* 并行发散 + 收敛器（Consensus Engine）
* 智能 orchestrator（基于冲突点/问题选择发言者）
* 工件版本管理与 diff
* 多会议串联（Roadmap/变更评审）
* 权限与多租户（如需要）
  **验收**
* 并行模式下仍能在门禁策略下收敛
* 工件可版本化追踪，支持回滚/对比

---

## 9. 任务拆解建议（你可以直接分给不同同学）

* **Orchestrator/Workflow**：调度、轮次、终止、pause/resume
* **Role Cards & Schema**：角色模板、输出校验、纠错重试
* **Artifacts Pipeline**：ADR/Tasks/Risks 生成与校验
* **Storage & Replay**：events/artifacts/memories 数据模型与回放 API
* **Observability**：指标埋点、日志结构、失败分析
* **Client**：CLI 或简易 Web（流式展示每轮发言）
