# CodeGraph 源码与原理分析

本文档记录对 `colbymchenry/codegraph` 项目的初步源码分析，重点关注它的代码地图构建原理、核心模块、依赖技术，以及它对 OnCallAgent / MES 代码分析场景的参考价值。

## 1. 项目定位

CodeGraph 是一个本地优先的代码知识图谱工具。

它的核心目标不是让 LLM 每次直接读取整个仓库，而是先把代码仓库结构化成一个本地代码图谱，然后让 Agent 通过 CLI、Node API 或 MCP 工具快速查询相关代码、调用链、影响范围和上下文。

可以把它理解为：

- 代码索引引擎
- 代码地图生成器
- 静态分析工具
- Agent 的代码上下文检索工具

它本身不是一个完整的 LLM Agent，但非常适合作为 Code Analysis Agent 的底层能力。

## 2. 核心工作流程

CodeGraph 的整体流程如下：

1. 扫描项目目录，识别需要索引的代码文件。
2. 根据扩展名和内容识别编程语言。
3. 使用 Tree-sitter 解析源码 AST。
4. 从 AST 中抽取代码符号，例如 class、method、function、field、route。
5. 抽取符号之间的关系，例如 contains、calls、imports、extends、implements、references。
6. 将文件、符号、关系、未解析引用写入本地 SQLite 数据库。
7. 执行跨文件引用解析，补全调用关系、继承关系、框架关系。
8. 查询时通过 SQLite FTS5 全文检索和图遍历找到相关代码。
9. 将相关源码片段、调用路径、关系说明组装成适合 Agent 使用的上下文。

这套机制的关键价值是：先把大代码仓库压缩成结构化图谱，再让 LLM 只读取和问题相关的少量代码。

## 3. 核心数据模型

CodeGraph 的数据主要存在本地 SQLite 中，核心表包括：

| 表名 | 作用 |
| --- | --- |
| `nodes` | 存储代码符号，例如文件、类、方法、函数、字段、路由、组件 |
| `edges` | 存储符号之间的关系，例如调用、包含、继承、引用 |
| `files` | 存储文件索引信息，例如路径、hash、语言、大小、索引时间 |
| `unresolved_refs` | 存储暂时无法解析的引用，后续由 resolver 尝试补全 |
| `nodes_fts` | SQLite FTS5 全文索引，用于符号搜索 |
| `name_segment_vocab` | 存储标识符拆词结果，用于自然语言和模糊检索 |
| `project_metadata` | 存储项目级元数据 |

`nodes` 和 `edges` 是最核心的两张表。

例如一个 Java 项目中可能会生成如下图关系：

```text
UserController.list()
  calls
UserService.list()
  calls
UserMapper.selectUserList()
  references
UserMapper.xml::selectUserList
```

这类结构对排查 MES 报错、追踪 Rule 执行链路、定位 SQL 和业务代码非常有价值。

## 4. 代码符号与关系类型

CodeGraph 支持的节点类型包括：

- file
- module
- class
- interface
- function
- method
- field
- variable
- constant
- enum
- import
- export
- route
- component

支持的边类型包括：

- contains：包含关系，例如文件包含类，类包含方法
- calls：调用关系
- imports：导入关系
- exports：导出关系
- extends：继承关系
- implements：接口实现关系
- references：普通引用关系
- type_of：类型关系
- returns：返回类型关系
- instantiates：实例化关系
- overrides：方法重写关系
- decorates：注解 / 装饰器关系

这说明 CodeGraph 不只是文件级索引，而是符号级图谱。

## 5. 主要源码模块

### 5.1 `src/index.ts`

这是主入口，核心类是 `CodeGraph`。

它负责串联：

- 数据库连接
- 代码抽取器
- 引用解析器
- 图查询器
- 上下文构建器
- 增量同步

常见能力包括：

- `init`
- `indexAll`
- `sync`
- `searchNodes`
- `getCallers`
- `getCallees`
- `getImpactRadius`
- `findPath`
- `buildContext`

### 5.2 `src/extraction`

这是代码抽取模块。

主要职责：

- 扫描文件
- 识别语言
- 调用 Tree-sitter 解析源码
- 抽取符号节点
- 抽取初步关系
- 写入 SQLite
- 支持增量更新

它会跳过常见无价值目录，例如：

- `node_modules`
- `dist`
- `build`
- `target`
- `.venv`
- `vendor`
- `.git`

也会处理 `.gitignore` 和 `codegraph.json` 配置。

### 5.3 `src/extraction/languages/java.ts`

这是 Java 语言抽取器。

它支持解析：

- Java 类
- 方法
- 构造器
- 字段
- 返回类型
- 注解
- Lombok 生成方法

比较有价值的是它对 Lombok 做了特殊处理，会模拟生成：

- `@Getter`
- `@Setter`
- `@Data`
- `@Value`
- `@Builder`
- `@SuperBuilder`
- `@Slf4j`

这对 Java 企业项目很重要，因为很多方法源码里并不存在，但编译后实际可用。

### 5.4 `src/extraction/mybatis-extractor.ts`

这是 MyBatis / iBatis XML Mapper 抽取器。

它会解析：

- `<select>`
- `<insert>`
- `<update>`
- `<delete>`
- `<sql>`
- `<include refid="...">`

并把 XML SQL 语句抽象成 method 节点。

例如：

```xml
<mapper namespace="com.demo.UserMapper">
  <select id="selectUserList">
    select * from user
  </select>
</mapper>
```

会被抽成类似：

```text
com.demo.UserMapper::selectUserList
```

后续 resolver 可以把 Java Mapper 接口方法和 XML SQL 关联起来。

这对 MES 老系统很有价值，因为很多业务链路最终落在 Mapper XML 中。

### 5.5 `src/resolution`

这是跨文件引用解析模块。

初次 AST 抽取时，很多引用只能知道名字，不能马上确定目标符号。

例如：

```java
userService.list();
```

抽取阶段可能只能知道调用了 `list`，但目标是哪个类里的 `list`，需要结合 import、类型、字段、框架规则进一步解析。

`resolution` 模块就是做这件事的。

### 5.6 `src/resolution/frameworks/java.ts`

这是 Java / Spring 框架解析逻辑。

它支持识别：

- Spring Boot 项目
- Controller
- Service
- Repository
- Entity / Model
- Component / Config
- Spring 配置文件
- `@Value`
- `@ConfigurationProperties`
- HTTP Route 映射

它会额外抽取 route 节点，并把 route 和对应 Controller 方法关联起来。

### 5.7 `src/context`

这是上下文构建模块。

它的职责是把用户的问题转换成适合 LLM 阅读的代码上下文。

大致流程：

1. 从自然语言中提取可能的符号名、文件名、关键词。
2. 使用 FTS 搜索找到入口节点。
3. 沿着图谱扩展相关节点。
4. 选出高价值文件和代码片段。
5. 控制上下文大小。
6. 输出 Markdown 或 JSON。

这部分对 Agent 很关键，因为它决定了大模型看到哪些代码。

### 5.8 `src/mcp`

这是 MCP 服务模块。

CodeGraph 可以作为 MCP Server 暴露工具给 AI Agent。

主要工具包括：

- `codegraph_explore`
- `codegraph_search`
- `codegraph_node`
- `codegraph_callers`
- `codegraph_callees`
- `codegraph_impact`
- `codegraph_files`
- `codegraph_status`

其中默认最核心的是 `codegraph_explore`。

它的设计目标是：一次调用返回足够的相关代码和关系，减少 Agent 反复 grep / read 文件的成本。

## 6. 依赖技术与组件

CodeGraph 的主要技术栈如下：

| 技术 | 作用 |
| --- | --- |
| Node.js | 运行环境 |
| TypeScript | 主要开发语言 |
| SQLite | 本地代码图谱存储 |
| SQLite FTS5 | 全文检索 |
| Tree-sitter | 多语言 AST 解析 |
| web-tree-sitter | Tree-sitter WASM 运行时 |
| tree-sitter-wasms | 多语言 grammar 包 |
| MCP | 给 AI Agent 暴露工具 |
| commander | CLI 命令行框架 |
| ignore | 处理 `.gitignore` |
| picomatch | 文件 glob 匹配 |
| jsonc-parser | 解析 JSONC 配置 |
| Vitest | 测试框架 |

它的 npm 包名是：

```text
@colbymchenry/codegraph
```

当前本地源码版本为：

```text
1.4.1
```

## 7. 对 OnCallAgent 的价值

对当前 OnCallAgent 来说，CodeGraph 的最大价值是提升 Code Analysis Agent 的速度和准确度。

我们现在的 Code Analysis Agent 如果只依赖 LLM + readFile / searchFile，会有几个问题：

- MES 项目文件太多，搜索成本高。
- 公共组件和框架封装复杂，LLM 需要多轮读文件。
- 调用链跨 Controller、Service、Rule、DAO、Mapper XML，手动追踪慢。
- 同名方法很多，容易定位错误。
- 每次分析都从零开始，没有复用代码结构索引。

CodeGraph 可以先建立代码地图，让子 Agent 查询：

- 某个类 / 方法在哪
- 谁调用了这个方法
- 这个方法调用了谁
- 某个接口有哪些实现
- 某个 Mapper 方法对应哪个 XML SQL
- 改一个方法可能影响哪些代码
- 某个报错堆栈对应的调用链附近有哪些代码

这正好可以作为 Code Analysis Agent 的底层工具。

## 8. 和 MES 场景的适配点

CodeGraph 对 MES 代码分析有明显价值，尤其是以下场景：

### 8.1 Java + Spring 项目

如果 MES 系统是 Java / Spring / Spring Boot，它可以识别 Controller、Service、Repository、配置项和路由。

### 8.2 MyBatis / iBatis

如果 MES 系统大量使用 Mapper XML，它可以把 XML SQL 纳入代码图谱。

这对定位 LotHistory、Rule、Lot、Module 等查询逻辑很重要。

### 8.3 Lombok

如果项目使用 Lombok，它能模拟常见 Lombok 生成方法，避免调用链断裂。

### 8.4 大仓库检索

对于文件非常多的 MES 项目，CodeGraph 可以显著减少 Agent 的文件读取次数。

## 9. 风险与限制

CodeGraph 不是万能的，特别是在复杂企业系统里要注意以下限制。

### 9.1 静态分析无法完全覆盖动态机制

以下场景可能无法准确解析：

- 反射调用
- 动态类加载
- 自定义 Rule Engine
- 自定义插件机制
- EventBus
- MQ 消息驱动
- Job 调度
- 数据库配置驱动流程
- XML / properties / DB 混合配置的执行链

这些场景可能需要我们额外开发自定义 resolver。

### 9.2 自研框架需要适配

MES / CIM / R2R 系统通常会有公司内部框架。

例如：

- RuleName 到 Java Class 的映射
- Module 到 Server 的映射
- Operation 到 Handler 的映射
- LotId 到流程上下文的映射
- DB 配置表驱动代码执行

这些不是通用开源工具能自动识别的，需要我们结合业务规则补充。

### 9.3 大文件跳过

README 中提到，CodeGraph 默认会跳过大于 1MB 的文件。

如果 MES 项目里有超大 Java 类、超大 XML、超大配置文件，需要关注这个限制。

### 9.4 Node.js / SQLite 部署限制

CodeGraph 是 Node.js / TypeScript 项目。

如果作为 npm library 嵌入使用，README 提到可能需要 Node 22.5+，因为依赖 `node:sqlite`。

如果使用独立 CLI 包，部署可能更简单。

### 9.5 和 Python Agent 的集成方式要设计好

我们当前 OnCallAgent 主要是 Python 代码。

如果集成 CodeGraph，可能有三种方式：

1. Python 调用 CodeGraph CLI。
2. Python 通过 MCP 调用 CodeGraph。
3. 直接读取 `.codegraph` SQLite 数据库。

短期最稳妥的是调用 CLI 或 MCP，不建议一开始直接读内部 SQLite 表，因为内部表结构后续可能变化。

## 10. 建议集成方式

短期建议采用“外部工具集成”模式。

也就是：

```text
Parent Agent
  -> Code Analysis Agent
    -> CodeGraph CLI / MCP
    -> readFile / grep fallback
    -> LLM 分析与总结
```

Code Analysis Agent 可以先调用 CodeGraph 找入口代码和调用链，再根据需要读取原始文件，最后交给 LLM 总结。

推荐流程：

1. 在目标 MES 项目根目录执行 `codegraph init`。
2. 生成 `.codegraph` 本地索引。
3. Code Analysis Agent 收到问题后，优先调用 `codegraph_explore`。
4. 如果 CodeGraph 找不到，再 fallback 到原有文件搜索逻辑。
5. 对业务规则、RuleName、LotId、Module 等 MES 特有链路，后续逐步补充自定义解析器。

## 11. 对我们自研 CodeMapAgent 的参考

如果未来不直接依赖 CodeGraph，而是自己做 CodeMapAgent，可以参考它的架构：

```text
代码扫描器
  -> 语言识别器
  -> AST 解析器
  -> Symbol Extractor
  -> Edge Extractor
  -> Reference Resolver
  -> Graph Store
  -> Graph Query
  -> Context Builder
  -> Agent Tool API
```

数据库可以从 SQLite 起步，也可以用 Postgres。

如果用 Postgres，可以设计类似这些表：

- code_files
- code_symbols
- code_edges
- unresolved_refs
- code_index_jobs
- code_symbol_search
- project_metadata

但从工程投入看，短期直接验证 CodeGraph 更划算。

## 12. 当前结论

CodeGraph 是一个成熟度较高的代码图谱工具，核心能力符合我们之前讨论的“代码地图”方向。

它最值得借鉴的地方有三点：

1. 用 Tree-sitter 做多语言结构化抽取。
2. 用 SQLite + FTS5 存储和检索本地代码图谱。
3. 用 MCP / CLI 给 Agent 提供高密度代码上下文。

对 OnCallAgent 来说，它可以先作为 Code Analysis Agent 的加速组件使用。

后续重点不是重新造一个完整 CodeGraph，而是验证它对公司 MES 代码的识别效果，然后补齐 MES 特有的业务解析规则。
