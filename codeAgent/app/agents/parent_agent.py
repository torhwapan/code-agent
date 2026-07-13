from app.agents.code_analysis_agent import CodeAnalysisChildAgent
from app.agents.input_parse_agent import InputParseAgent
from app.agents.intent_agent import IntentAgent
from app.agents.report_agent import ReportAgent


class OnCallParentAgent:
    def __init__(self, code_agent=None, code_agent_url=None):
        self.intent_agent = IntentAgent()
        self.input_agent = InputParseAgent()
        self.code_agent = CodeAnalysisChildAgent(code_agent=code_agent, service_url=code_agent_url)
        self.report_agent = ReportAgent()

    def handle(self, payload):
        context = self._new_context(payload)
        self._record(context, "ParentAgent", "收到用户输入，按代码分析任务处理。")

        intent = self.intent_agent.decide(payload)
        context["intent"] = intent["intent"]
        context["task_type"] = intent.get("task_type") or intent["intent"]
        self._record(context, "IntentAgent", intent["reason"])

        context["parsed"] = self.input_agent.run(payload)
        self._record(context, "InputParseAgent", "完成代码关键词、模块、ruleName 等上下文解析。")

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
            "task_type": "",
            "user_message": payload.get("message") or payload.get("description") or payload.get("user_message") or "",
            "repo_id": payload.get("repo_id") or "workspace",
            "max_steps": payload.get("max_steps") or 8,
            "parsed": {},
            "extra_text": payload.get("extra_text") or "",
            "code_result": {},
            "answer": "",
            "report": "",
            "steps": [],
        }

    def _record(self, context, agent, message):
        context["steps"].append({"agent": agent, "message": message})

    def _response(self, context):
        return {
            "ok": context.get("status") != "error",
            "status": context.get("status"),
            "intent": context.get("intent"),
            "task_type": context.get("task_type"),
            "answer": context.get("answer"),
            "report": context.get("report"),
            "steps": context.get("steps", []),
            "context": {
                "parsed": context.get("parsed"),
                "code_result": context.get("code_result"),
            },
        }
