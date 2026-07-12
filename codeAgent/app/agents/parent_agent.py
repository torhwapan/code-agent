from app.agents.code_analysis_agent import CodeAnalysisChildAgent
from app.agents.db_investigation_agent import DBInvestigationAgent
from app.agents.input_parse_agent import InputParseAgent
from app.agents.intent_agent import IntentAgent
from app.agents.knowledge_router_agent import KnowledgeRouterAgent
from app.agents.log_retrieval_agent import LogRetrievalAgent
from app.agents.report_agent import ReportAgent


class OnCallParentAgent:
    def __init__(self, code_agent=None, code_agent_url=None):
        self.intent_agent = IntentAgent()
        self.input_agent = InputParseAgent()
        self.db_agent = DBInvestigationAgent()
        self.log_agent = LogRetrievalAgent()
        self.knowledge_agent = KnowledgeRouterAgent()
        self.code_agent = CodeAnalysisChildAgent(code_agent=code_agent, service_url=code_agent_url)
        self.report_agent = ReportAgent()

    def handle(self, payload):
        context = self._new_context(payload)
        self._record(context, "ParentAgent", "收到用户输入，开始判断意图。")

        intent = self.intent_agent.decide(payload)
        context["intent"] = intent["intent"]
        context["log_source"] = intent["log_source"]
        context["task_type"] = intent.get("task_type") or intent["intent"]
        self._record(context, "IntentAgent", intent["reason"])

        context["parsed"] = self.input_agent.run(payload)
        self._record(context, "InputParseAgent", "完成 lot/fab/env/module/ruleName 和日志关键词解析。")

        missing = self._missing_fields(context)
        if missing:
            context["status"] = "need_more_info"
            context["missing_fields"] = missing
            context["question"] = self._build_question(missing)
            context["answer"] = context["question"]
            context["report"] = self.report_agent.run(context)
            return self._response(context)

        context["knowledge"]["pre"] = self.knowledge_agent.run(context, phase="pre")
        self._record(context, "KnowledgeRouterAgent", "完成第一轮轻量知识库 mock 召回。")

        if context["log_source"] == "need_retrieve":
            context["db_result"] = self.db_agent.run(context)
            self._record(context, "DBInvestigationAgent", context["db_result"].get("summary", "DB 调查完成。"))

            context["log_result"] = self.log_agent.run(context)
            context["log_text"] = context["log_result"].get("data", {}).get("log_text", "")
            self._record(context, "LogRetrievalAgent", context["log_result"].get("summary", "日志检索完成。"))
        elif context["log_source"] == "user_provided":
            context["log_text"] = payload.get("log_text") or ""
            self._record(context, "ParentAgent", "使用用户直接提供的日志。")

        context["knowledge"]["post"] = self.knowledge_agent.run(context, phase="post")
        self._record(context, "KnowledgeRouterAgent", "完成第二轮精准知识库 mock 召回。")

        if self._need_code_analysis(context):
            context["code_result"] = self.code_agent.run(context)
            self._record(context, "CodeAnalysisAgent", context["code_result"].get("summary", "代码分析完成。"))

        context["status"] = "completed"
        context["report"] = self.report_agent.run(context)
        context["answer"] = context["report"]
        return self._response(context)

    def _new_context(self, payload):
        return {
            "status": "running",
            "intent": "",
            "log_source": "",
            "task_type": "",
            "user_message": payload.get("message") or payload.get("description") or "",
            "repo_id": payload.get("repo_id") or "workspace",
            "max_steps": payload.get("max_steps") or 8,
            "parsed": {},
            "db_result": {},
            "log_result": {},
            "log_text": payload.get("log_text") or "",
            "knowledge": {"pre": {}, "post": {}},
            "code_result": {},
            "missing_fields": [],
            "question": "",
            "answer": "",
            "report": "",
            "steps": [],
        }

    def _missing_fields(self, context):
        if context.get("log_source") != "need_retrieve":
            return []
        parsed = context.get("parsed") or {}
        return [name for name in ("lot_id", "fab", "env") if not parsed.get(name)]

    def _build_question(self, missing):
        labels = {
            "lot_id": "lotId",
            "fab": "厂别（Fab1 或 Fab2）",
            "env": "运行环境（pirun 或 prod）",
        }
        names = [labels.get(name, name) for name in missing]
        return "还需要补充：" + "、".join(names) + "。"

    def _need_code_analysis(self, context):
        return context.get("intent") in {"code_question", "code_with_log"}

    def _record(self, context, agent, message):
        context["steps"].append({"agent": agent, "message": message})

    def _response(self, context):
        return {
            "ok": context.get("status") != "error",
            "status": context.get("status"),
            "intent": context.get("intent"),
            "log_source": context.get("log_source"),
            "task_type": context.get("task_type"),
            "answer": context.get("answer"),
            "question": context.get("question"),
            "report": context.get("report"),
            "steps": context.get("steps", []),
            "context": {
                "parsed": context.get("parsed"),
                "db_result": context.get("db_result"),
                "log_result": context.get("log_result"),
                "knowledge": context.get("knowledge"),
                "code_result": context.get("code_result"),
                "missing_fields": context.get("missing_fields"),
            },
        }
