# CLUADE.md

## 1. 开发流程
### 1.1 需求分析与规划
- 需求明确： 开发前必须明确业务需求、核心链路与边界条件，梳理清楚开发要点和难点
- 技术方案设计 (Tech Spec)： 核心模块开发前必须输出技术方案文档，包含模块划分、接口定义（API Schema）、数据表设计、技术选型及风险预案。
- 使用 `plan agent` 输出详细的**代码编写计划**，包括模块划分、核心函数定义、技术选型及风险点评估。

### 1.2 环境配置与依赖管理
- 使用 **uv** 创建隔离的虚拟环境，确保环境一致性。
- 依赖管理采用 `pyproject.toml`（遵循 PEP 621 规范），并提交 `uv.lock` 锁定版本。
- 敏感配置（如 API Key、数据库地址）通过 **环境变量** 或 `.env` 文件管理，禁止硬编码。

### 1.3 代码结构设计
- 模块化与解耦： 采用模块化设计，遵循高内聚、低耦合原则
- 强制单一职责原则 (SRP)： 每个文件、类或函数只处理一件特定的事情。
- 面向接口/协议编程： 在实现核心逻辑前，优先定义清晰的数据结构（如 TypeScript 的 Interface、Go 的 Struct/Interface、Python 的 TypedDict/Protocol）。模块之间的通信只能通过这些公共接口进行，严禁直接访问其他模块的内部私有变量。
- 使用依赖注入 (Dependency Injection)： 模块不应该在内部自行实例化它的外部依赖
- 统一错误处理边界： 每个模块应捕获其内部的预期错误，并向外抛出标准化的自定义异常或错误码。

### 1.4 代码编写与文档注释
- 静态类型约束： 强制开启类型提示（Type Hinting），并在本地和 CI 环节使用严格的静态类型检查工具拦截潜在错误
- 代码格式化 (Linting)： 统一使用现代化的格式化和检查工具（如 Ruff、ESLint、Prettier）。代码提交前必须自动完成格式化
- 核心函数和复杂逻辑必须添加**英文文档字符串**（推荐 Google 风格），包含 `Args`、`Returns`、`Raises` 及 `Examples`。
- 代码遵循“简洁、可读、可维护”原则，避免过度封装，关键逻辑添加单行注释
- 规范化日志： 统一使用标准日志库，严禁使用 print()。按场景严格区分 DEBUG, INFO, WARNING, ERROR 级别

### 1.5 测试验证
- 单元测试：使用 `unittest` 覆盖核心函数，确保逻辑正确性。
- 集成测试：使用 `pytest` 覆盖 Agent 端到端流程，模拟真实调用场景。
- 边界测试：针对异常输入、模型超时、API 限流等场景进行测试。
- 测试覆盖率要求：核心模块覆盖率 ≥ 80%（使用 `pytest-cov` 检查）。

### 1.6 文档更新
- 代码有重大更新时，优先更新 `README.md`，确保**环境安装**和**运行入口**绝对正确。
- README.md 是项目的第一门面，必须保持绝对的准确性和精简性。当发生以下变更时，必须同步更新：

    - 依赖或环境变更： 新增了系统环境变量、修改了 Python/Node.js 版本要求、增加了必须安装的底层库（如 ffmpeg、redis），必须更新“环境安装”或“快速开始”章节。

    - 运行方式变更： 启动命令、构建脚本或打包方式发生改变时，必须提供可直接复制运行的最新命令。

    - 架构大换血： 核心技术栈替换时，需更新项目的简介与技术栈标识。

- 新增功能或变更接口时，同步更新 `docs/` 下的设计文档和 API 说明。
- 架构与设计文档规范 (docs/)
    docs/ 目录用于沉淀系统的长期知识，聚焦于“为什么这么设计”以及“内部是怎么运转的”。

    - 新增核心模块： 引入新的核心机制（如新加了消息队列机制、引入了 RAG 检索流程）时，必须在 docs/ 下新增设计文档，建议包含简单的系统交互时序图或架构图。

    - ADR (架构决策记录)： 发生重大技术选型变更（例如把 MySQL 换成了 PostgreSQL）时，应编写简短的 ADR 文档，记录当时的背景、对比方案以及最终决策的原因，避免后人重复踩坑。

    - 废弃与标注： 如果某部分设计已经过时，不要直接删除文档，而应在文档顶部添加明显的 [DEPRECATED] (已废弃) 标识，并指向新的设计文档。

- 更新日志 (CHANGELOG.md) 追踪
    项目必须维护一份面向开发者或使用者的更新日志，记录每次发版的足迹。

    版本隔离： 按版本号（如 v1.2.0）和发布日期倒序排列。

    分类记录： 变更内容需分类别列出，包含但不限于：
        - Added: 新功能。
        - Changed: 现有功能的变更。
        - Fixed: 修复的 Bug。
        - Security: 安全漏洞修复。
        - Removed: 移除的旧功能或接口（重要，需重点标注以防下游报错）。

### 1.7 代码评审
- 开发完成后进行自我评审，检查：
  - 测试是否全部通过；
  - 文档字符串是否符合规范（无中文）；
  - 代码是否简洁且符合生产环境规范；
  - 是否存在安全隐患（如敏感数据泄露、越权访问）。


## 2. 代码规范
### 2.1 代码风格
- Python 代码遵循 **PEP 8** 规范，使用 `black` 格式化、`isort` 排序导入、`flake8` 静态检查。
- 强制使用**类型提示**（Type Hints），函数参数和返回值必须明确类型（如 `def func(a: int, b: str) -> bool`）。

### 2.2 文档注释规范
- 模块级文档字符串：说明模块功能、作者、创建日期。
- 函数/类文档字符串（英文）示例：
  ```python
  def call_llm(prompt: str, temperature: float = 0.7) -> str:
      """Call LLM model to generate response.

      Args:
          prompt: Input prompt string.
          temperature: Sampling temperature, range [0.0, 1.0].

      Returns:
          Generated response string.

      Raises:
          TimeoutError: If model call exceeds timeout.
          ValueError: If temperature is out of range.

      Examples:
          >>> call_llm("Hello", temperature=0.5)
          "Hi there!"
      """
  ```

### 2.3 测试规范
- 测试文件命名：`test_*.py`，与被测试模块对应。
- 测试用例命名：`test_<function>_<scenario>`（如 `test_call_llm_timeout`）。
- 测试数据隔离：使用临时文件或 mock 外部依赖，避免影响真实环境。


## 3. 版本控制与提交规范
### 3.1 分支管理策略
- `main`：生产环境分支，保护分支，仅通过 PR 合并。
- `develop`：开发集成分支，新功能从 `develop` 切出，完成后合并回 `develop`。
- `feature/*`：功能分支（如 `feature/add-search-tool`），开发完成后删除。
- `hotfix/*`：紧急修复分支（如 `hotfix/fix-api-timeout`），修复后合并到 `main` 和 `develop`。

### 3.2 Commit Message 规范
- 所有 commit 前缀添加 `ADX-17470:`，格式为：
  ```
  ADX-17470: <type>: <subject>
  ```
- `type` 类型：
  - `feat`：新功能
  - `fix`：修复 bug
  - `docs`：文档更新
  - `test`：测试相关
  - `refactor`：重构（不影响功能）
  - `style`：代码格式调整
  - `chore`：构建/工具相关
- `subject`：英文，简洁明了，不超过 50 字符，必要时添加 body 说明细节。



