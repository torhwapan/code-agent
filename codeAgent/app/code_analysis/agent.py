import json
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.code_analysis.business_logger import BusinessLogger
from app.code_analysis.llm import LLMClient
from app.logs.parser import LogParser


class AgentState:
    def __init__(self, case_id, repo_id, description, raw_log, parsed_log, search_terms):
        # This object is the working memory for one analysis case.
        self.case_id = case_id
        self.repo_id = repo_id
        self.description = description
        self.raw_log = raw_log
        self.parsed_log = parsed_log
        self.search_terms = search_terms

        self.steps = []
        self.matches = []
        self.snippets = []
        self.observations = []
        self.codegraph_results = []
        self.searched_terms = []
        self.read_keys = set()
        self.errors = []


class CodeAnalysisAgent:
    def __init__(self, tools, llm=None, case_dir="data/cases", business_logger=None, codegraph_tool=None):
        self.tools = tools
        self.llm = llm or LLMClient()
        self.parser = LogParser()
        self.case_dir = Path(case_dir)
        self.case_dir.mkdir(parents=True, exist_ok=True)
        self.business_logger = business_logger or BusinessLogger()
        self.codegraph_tool = codegraph_tool

    def handle_input(self, request):
        request_id = self.business_logger.new_request_id()
        started = time.perf_counter()
        self.business_logger.write(
            "code_analysis.request_received",
            {
                "request_id": request_id,
                "input_type": "wide_request",
                "request": self.business_logger.summarize_request(request),
            },
        )
        try:
            task = self.normalize_request(request)
            self.business_logger.write(
                "code_analysis.request_normalized",
                {
                    "request_id": request_id,
                    "task": self.business_logger.summarize_task(task),
                },
            )
            result = self.analyze_task(task, log_business=False, parent_request_id=request_id)
            result["normalized_task"] = task
            self.business_logger.write(
                "code_analysis.request_completed",
                {
                    "request_id": request_id,
                    "duration_ms": self._duration_ms(started),
                    "result": self.business_logger.summarize_result(result),
                },
            )
            return result
        except Exception as exc:
            self.business_logger.write(
                "code_analysis.request_failed",
                {
                    "request_id": request_id,
                    "duration_ms": self._duration_ms(started),
                    "error": str(exc),
                },
            )
            raise

    def normalize_request(self, request):
        message = request.get("user_message") or request.get("message") or request.get("description") or ""
        attachments = request.get("attachments") or {}
        known_context = request.get("known_context") or {}
        conversation_summary = request.get("conversation_summary") or request.get("context_summary") or ""
        repo_id = request.get("repo_id") or known_context.get("repo_id") or "workspace"
        log_text = attachments.get("log_text") or request.get("log_text") or ""
        extra_text = attachments.get("extra_text") or request.get("extra_text") or ""
        combined_text = "\n".join(part for part in [message, conversation_summary, log_text, extra_text] if part)

        parsed = self.parser.parse(combined_text)
        task_type = request.get("task_type") or self._classify_task(message, log_text, combined_text)
        code_signals = self._extract_code_signals(parsed, known_context, message)

        evidence = {
            "log_text": log_text,
            "extra_text": extra_text,
            "db": request.get("db_evidence") or request.get("db") or {},
            "knowledge": request.get("knowledge_evidence") or request.get("knowledge") or {},
        }

        return {
            "task_type": task_type,
            "repo_id": repo_id,
            "user_goal": message or "请分析代码。",
            "code_signals": code_signals,
            "evidence": evidence,
            "context_summary": conversation_summary,
            "max_steps": request.get("max_steps") or (request.get("options") or {}).get("max_steps") or 8,
        }

    def analyze_task(self, task, log_business=True, parent_request_id=""):
        request_id = parent_request_id or self.business_logger.new_request_id()
        started = time.perf_counter()
        if log_business:
            self.business_logger.write(
                "code_analysis.task_received",
                {
                    "request_id": request_id,
                    "input_type": "normalized_task",
                    "task": self.business_logger.summarize_task(task),
                },
            )
        repo_id = task.get("repo_id") or "workspace"
        max_steps = task.get("max_steps") or 8
        analysis_text = self._task_to_analysis_text(task)
        description = self._task_description(task)
        extra_terms = self._task_search_terms(task)
        try:
            result = self.analyze(
                repo_id=repo_id,
                raw_log=analysis_text,
                description=description,
                max_steps=max_steps,
                extra_search_terms=extra_terms,
                task_type=task.get("task_type") or "code_question",
                log_business=False,
            )
            result["task_type"] = task.get("task_type") or "code_question"
            result["user_goal"] = task.get("user_goal") or ""
            if log_business:
                self.business_logger.write(
                    "code_analysis.task_completed",
                    {
                        "request_id": request_id,
                        "duration_ms": self._duration_ms(started),
                        "result": self.business_logger.summarize_result(result),
                    },
                )
            return result
        except Exception as exc:
            if log_business:
                self.business_logger.write(
                    "code_analysis.task_failed",
                    {
                        "request_id": request_id,
                        "duration_ms": self._duration_ms(started),
                        "error": str(exc),
                    },
                )
            raise

    def _classify_task(self, message, log_text, combined_text):
        lowered = (message or "").lower()
        if log_text or self.parser.parse(combined_text).exceptions:
            return "log_diagnosis"
        if any(word in message for word in ["流程", "调用链", "链路", "怎么执行", "怎么跑", "如何执行"]):
            return "flow_analysis"
        if any(word in message for word in ["影响", "改动", "风险", "会不会影响"]):
            return "impact_analysis"
        if any(word in lowered for word in ["bug", "error", "exception"]) or any(word in message for word in ["报错", "异常", "失败"]):
            return "bug_hunt"
        return "code_question"

    def _extract_code_signals(self, parsed, known_context, message):
        keywords = self.parser.build_search_terms(parsed)
        keywords.extend(self._extract_goal_terms(message or ""))
        module = known_context.get("module") or self._first_match(r"\b(MES|R2R|CIM|EAP|FDC|APC)\b", message)
        rule_name = known_context.get("rule_name") or self._first_match(r"\b([A-Za-z_][A-Za-z0-9_]*(?:Rule|RULE))\b", message)

        return {
            "keywords": self._unique_terms(keywords, 40),
            "classes": parsed.classes,
            "methods": parsed.methods,
            "error_codes": parsed.error_codes,
            "exceptions": parsed.exceptions,
            "tables": parsed.tables,
            "module": module,
            "rule_name": rule_name,
            "known_context": {key: value for key, value in known_context.items() if value not in (None, "", [], {})},
        }

    def _first_match(self, pattern, text):
        match = re.search(pattern, text or "", re.IGNORECASE)
        if not match:
            return None
        return match.group(1)

    def _duration_ms(self, started):
        return int((time.perf_counter() - started) * 1000)

    def analyze(self, repo_id, raw_log, description="", max_steps=8, extra_search_terms=None, task_type="log_diagnosis", log_business=True):
        request_id = self.business_logger.new_request_id()
        started = time.perf_counter()
        if log_business:
            self.business_logger.write(
                "code_analysis.legacy_analyze_received",
                {
                    "request_id": request_id,
                    "input_type": "legacy_analyze",
                    "repo_id": repo_id,
                    "task_type": task_type,
                    "description_preview": self.business_logger.preview(description),
                    "raw_log_length": len(raw_log or ""),
                },
            )
        parsed = self.parser.parse(raw_log)
        search_terms = self._unique_terms(
            self.parser.build_search_terms(parsed) + (extra_search_terms or []),
            80,
        )
        state = AgentState(
            case_id=self._new_case_id(),
            repo_id=repo_id,
            description=description.strip(),
            raw_log=raw_log,
            parsed_log=parsed,
            search_terms=search_terms,
        )
        state.task_type = task_type

        self._explore_with_codegraph(state)

        if self.llm.available:
            self._run_llm_loop(state, max(2, min(max_steps, 12)))
            report = self._generate_llm_report(state)
        else:
            self._run_rule_based_loop(state, max_steps)
            report = self._generate_rule_based_report(state)

        result = {
            "case_id": state.case_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "repo_id": repo_id,
            "task_type": task_type,
            "llm_enabled": self.llm.available,
            "parsed_log": parsed.to_dict(),
            "search_terms": state.search_terms,
            "steps": state.steps,
            "matches": [match.to_dict() for match in state.matches[:80]],
            "snippets": [snippet.to_dict() for snippet in state.snippets],
            "codegraph_results": [item.to_dict() for item in state.codegraph_results],
            "observations": state.observations,
            "errors": state.errors,
            "report": report,
        }
        self._save_case(result)
        if log_business:
            self.business_logger.write(
                "code_analysis.legacy_analyze_completed",
                {
                    "request_id": request_id,
                    "duration_ms": self._duration_ms(started),
                    "result": self.business_logger.summarize_result(result),
                },
            )
        return result

    def _run_llm_loop(self, state, max_steps):
        # Main Agent loop: ask LLM what to do, run a safe tool, record the result.
        for step_index in range(max_steps):
            decision = self._ask_next_action(state, step_index)
            action = decision.get("action")
            reason = decision.get("reason", "")

            if action == "final":
                state.steps.append({"type": "final", "reason": reason or "LLM decided enough evidence was collected."})
                break

            if action == "search_code":
                query = str(decision.get("query", "")).strip()
                if not query or query.lower() in {term.lower() for term in state.searched_terms}:
                    query = self._next_unsearched_term(state)
                if not query:
                    state.steps.append({"type": "stop", "reason": "No more useful search terms."})
                    break
                self._search(state, query, reason or "LLM requested code search")
                continue

            if action == "read_file":
                path = str(decision.get("path", "")).strip()
                if not path:
                    fallback = self._next_unread_match(state)
                    if fallback:
                        self._read_match(state, fallback, reason or "Fallback read from search result")
                    else:
                        state.steps.append({"type": "stop", "reason": "No unread search matches."})
                        break
                    continue

                start = self._optional_int(decision.get("start_line"))
                end = self._optional_int(decision.get("end_line"))
                self._read_file(state, path, start, end, reason or "LLM requested file read")
                continue

            fallback_term = self._next_unsearched_term(state)
            if fallback_term:
                self._search(state, fallback_term, "Fallback search because LLM action was invalid")
            else:
                state.steps.append({"type": "stop", "reason": f"Invalid LLM action and no fallback term: {action}"})
                break

        if not state.snippets:
            self._read_top_matches(state, 5)

    def _explore_with_codegraph(self, state):
        if not self.codegraph_tool:
            return

        query = self._build_codegraph_query(state)
        result = self.codegraph_tool.explore(state.repo_id, query)
        state.codegraph_results.append(result)

        if result.ok:
            state.steps.append(
                {
                    "type": "codegraph_explore",
                    "query": result.query,
                    "project_path": result.project_path,
                    "output_length": len(result.output or ""),
                }
            )
            state.observations.append(
                "CodeGraph 已返回代码地图上下文，后续分析会优先基于该上下文，并保留原有代码搜索作为兜底。"
            )
        else:
            state.steps.append(
                {
                    "type": "codegraph_explore",
                    "query": result.query,
                    "project_path": result.project_path,
                    "error": result.error,
                }
            )
            state.errors.append(f"codegraph_explore failed: {result.error}")

    def _build_codegraph_query(self, state):
        parts = []
        if state.description:
            parts.append(state.description)
        if state.raw_log:
            parts.append(state.raw_log[:3000])
        if state.search_terms:
            parts.append("search_terms: " + " ".join(state.search_terms[:30]))
        return "\n".join(parts).strip() or "Analyze code flow"

    def _run_rule_based_loop(self, state, max_steps):
        for term in state.search_terms[: max(3, max_steps)]:
            self._search(state, term, "Rule-based search from parsed log signal")
            if len(state.matches) >= 20:
                break

        self._read_top_matches(state, 8)
        state.observations.append("LLM is not configured, so the report is based on parsed log signals and code search/read evidence.")

    def _ask_next_action(self, state, step_index):
        prompt = {
            "task": "You are a general code analysis agent. Decide the next safe code-search/read action for the user's code task.",
            "allowed_actions": [
                {"action": "search_code", "query": "term to search", "reason": "why this search matters"},
                {"action": "read_file", "path": "relative path", "start_line": 1, "end_line": 120, "reason": "why this file range matters"},
                {"action": "final", "reason": "enough evidence or blocked"},
            ],
            "rules": [
                "Prefer exact classes, methods, filenames, APIs, business terms, error codes, SQL table names, and constants from the task.",
                "After search results are available, read the most relevant files or line ranges.",
                "Do not request arbitrary shell commands.",
                "Stop if enough code evidence has been collected or no new useful path remains.",
                "Return only JSON.",
            ],
            "state": self._compact_state(state),
            "step_index": step_index,
        }

        try:
            content = self.llm.chat(
                [
                    {"role": "system", "content": "You plan safe code-search/read actions. You must return valid JSON only."},
                    {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
                ],
                json_mode=True,
            )
            return json.loads(self._extract_json(content))
        except Exception as exc:
            state.errors.append(str(exc))
            return {
                "action": "search_code",
                "query": self._next_unsearched_term(state),
                "reason": "Fallback after LLM planning error",
            }

    def _generate_llm_report(self, state):
        payload = {
            "description": state.description,
            "task_type": getattr(state, "task_type", "code_question"),
            "parsed_log": state.parsed_log.to_dict(),
            "steps": state.steps,
            "observations": state.observations,
            "codegraph_context": [
                {
                    "query": item.query,
                    "project_path": item.project_path,
                    "output": item.output,
                    "error": item.error,
                }
                for item in state.codegraph_results
                if item.ok
            ],
            "code_snippets": [snippet.to_dict() for snippet in state.snippets],
            "instruction": "Generate a Chinese Markdown code analysis report with evidence. Match the user's task type: code question, flow analysis, impact analysis, or log diagnosis. Include related files, call path or implementation flow when useful, confidence, missing information, and next steps. If evidence is insufficient, say so clearly.",
        }

        try:
            return self.llm.chat(
                [
                    {"role": "system", "content": "You are a senior CIM/MES code analysis engineer. Be precise, evidence-driven, and cautious."},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ]
            )
        except Exception as exc:
            state.errors.append(str(exc))
            return self._generate_rule_based_report(state)

    def _generate_rule_based_report(self, state):
        parsed = state.parsed_log
        files = []
        for snippet in state.snippets:
            files.append(f"- `{snippet.path}:{snippet.start_line}` - {snippet.reason or 'matched log signal'}")
        if not files:
            files.append("- No clearly related code file was found.")

        terms = ", ".join(state.search_terms[:12]) or "No useful search term was extracted."
        errors = ", ".join(parsed.error_codes + parsed.exceptions) or "No clear error code or exception was found."
        codegraph_lines = self._rule_based_codegraph_lines(state)

        return "\n".join(
            [
                "# Code Analysis Report",
                "",
                "## 1. Summary",
                f"- Task type: {getattr(state, 'task_type', 'code_question')}",
                f"- User goal: {state.description or 'N/A'}",
                f"- Error / exception: {errors}",
                f"- Main search terms: {terms}",
                f"- Code snippets read: {len(state.snippets)}",
                "",
                "## 2. Extracted Signals",
                f"- Error codes: {', '.join(parsed.error_codes) or 'N/A'}",
                f"- Exceptions: {', '.join(parsed.exceptions) or 'N/A'}",
                f"- Classes: {', '.join(parsed.classes[:10]) or 'N/A'}",
                f"- Methods: {', '.join(parsed.methods[:10]) or 'N/A'}",
                f"- Tables: {', '.join(parsed.tables[:10]) or 'N/A'}",
                "",
                "## 3. Related Code Locations",
                *files,
                "",
                "## 4. CodeGraph Context",
                *codegraph_lines,
                "",
                "## 5. Initial Judgment",
                "- LLM is not configured, so this report only shows rule-based code location results.",
                "- Please inspect the listed files and nearby lines first. For pure code questions, focus on entry points, call flow, interfaces, and state transitions. For log diagnosis, also inspect error handling and validation branches.",
                "",
                "## 6. Next Steps",
                "- Configure `LLM_API_KEY` and model settings to enable multi-step LLM analysis.",
                "- If too many files match, add module name, class/method name, interface name, or full stack trace.",
            ]
        )

    def _rule_based_codegraph_lines(self, state):
        if not state.codegraph_results:
            return ["- CodeGraph was not configured for this analysis."]

        result = state.codegraph_results[0]
        if not result.ok:
            return [f"- CodeGraph did not return context: {result.error or 'unknown error'}"]

        preview = (result.output or "").strip()
        if len(preview) > 2500:
            preview = preview[:2500] + "\n...<truncated>"
        if not preview:
            return ["- CodeGraph ran successfully but returned no text."]

        return [
            f"- CodeGraph project: `{result.project_path}`",
            f"- CodeGraph query: `{result.query[:300]}`",
            "",
            "```text",
            preview,
            "```",
        ]

    def _task_to_analysis_text(self, task):
        evidence = task.get("evidence") or {}
        code_signals = task.get("code_signals") or {}
        parts = [
            task.get("user_goal") or "",
            task.get("context_summary") or "",
            evidence.get("log_text") or "",
        ]

        for key in ("keywords", "classes", "methods", "error_codes", "exceptions", "tables"):
            values = code_signals.get(key) or []
            if values:
                parts.append(f"{key}: " + ", ".join(str(item) for item in values))

        for key in ("module", "rule_name"):
            if code_signals.get(key):
                parts.append(f"{key}: {code_signals.get(key)}")

        db_data = (evidence.get("db") or {}).get("data", {})
        if db_data:
            parts.append("db_evidence: " + json.dumps(db_data, ensure_ascii=False))

        return "\n".join(part for part in parts if str(part).strip()) or "Code analysis task"

    def _task_description(self, task):
        parts = [
            f"任务类型：{task.get('task_type') or 'code_question'}",
            f"用户目标：{task.get('user_goal') or 'N/A'}",
        ]
        if task.get("context_summary"):
            parts.append(task["context_summary"])
        return "\n".join(parts)

    def _task_search_terms(self, task):
        terms = []
        terms.extend(self._extract_goal_terms(task.get("user_goal") or ""))
        code_signals = task.get("code_signals") or {}
        for key in ("keywords", "classes", "methods", "error_codes", "exceptions", "tables"):
            value = code_signals.get(key)
            if isinstance(value, list):
                terms.extend(value)
        for key in ("module", "rule_name"):
            if code_signals.get(key):
                terms.append(code_signals[key])

        evidence = task.get("evidence") or {}
        db_data = (evidence.get("db") or {}).get("data", {})
        for key in ("rule_name", "module"):
            if db_data.get(key):
                terms.append(db_data[key])

        return self._unique_terms(terms, 60)

    def _extract_goal_terms(self, text):
        if not text:
            return []

        terms = []
        terms.extend(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]{2,}\b", text))
        terms.extend(re.findall(r"[\u4e00-\u9fff]{2,12}", text))
        return [term for term in terms if term.lower() not in {"the", "and", "for", "with"}]

    def _unique_terms(self, items, limit):
        seen = set()
        result = []
        for item in items:
            text = str(item).strip()
            key = text.lower()
            if not text or key in seen:
                continue
            seen.add(key)
            result.append(text)
            if len(result) >= limit:
                break
        return result

    def _search(self, state, query, reason):
        try:
            matches = self.tools.search_code(state.repo_id, query, max_results=25)
            state.searched_terms.append(query)
            state.matches.extend(matches)
            state.steps.append(
                {
                    "type": "search_code",
                    "query": query,
                    "reason": reason,
                    "result_count": len(matches),
                    "top_results": [match.to_dict() for match in matches[:5]],
                }
            )
        except Exception as exc:
            state.errors.append(f"search_code({query}) failed: {exc}")

    def _read_file(self, state, path, start, end, reason):
        key = f"{path}:{start or ''}:{end or ''}"
        if key in state.read_keys:
            state.steps.append({"type": "skip_read", "path": path, "reason": "Already read"})
            return

        try:
            snippet = self.tools.read_file(state.repo_id, path, start, end, reason=reason)
            state.read_keys.add(key)
            state.snippets.append(snippet)
            state.steps.append(
                {
                    "type": "read_file",
                    "path": snippet.path,
                    "start_line": snippet.start_line,
                    "end_line": snippet.end_line,
                    "reason": reason,
                }
            )
        except Exception as exc:
            state.errors.append(f"read_file({path}) failed: {exc}")

    def _read_match(self, state, match, reason):
        key = f"{match.path}:{max(1, match.line - 80)}:{match.line + 80}"
        if key in state.read_keys:
            return

        try:
            snippet = self.tools.read_around(state.repo_id, match.path, match.line, context_lines=80, reason=reason)
            state.read_keys.add(key)
            state.snippets.append(snippet)
            state.steps.append(
                {
                    "type": "read_file",
                    "path": snippet.path,
                    "start_line": snippet.start_line,
                    "end_line": snippet.end_line,
                    "reason": reason,
                }
            )
        except Exception as exc:
            state.errors.append(f"read around {match.path}:{match.line} failed: {exc}")

    def _read_top_matches(self, state, limit):
        ranked = self._rank_matches(state.matches)
        for match in ranked[:limit]:
            self._read_match(state, match, f"Read around match `{match.matched}` at line {match.line}")

    def _rank_matches(self, matches):
        preferred = (".java", ".cs", ".py", ".sql", ".xml", ".properties", ".yml", ".yaml")
        seen = set()
        ranked = []

        for match in matches:
            key = (match.path, match.line)
            if key in seen:
                continue
            seen.add(key)
            ranked.append(match)

        return sorted(ranked, key=lambda m: (0 if m.path.endswith(preferred) else 1, len(m.path), m.line))

    def _next_unread_match(self, state):
        for match in self._rank_matches(state.matches):
            prefix = f"{match.path}:"
            if not any(key.startswith(prefix) for key in state.read_keys):
                return match
        return None

    def _next_unsearched_term(self, state):
        searched = {term.lower() for term in state.searched_terms}
        for term in state.search_terms:
            if term.lower() not in searched:
                return term
        return None

    def _compact_state(self, state):
        return {
            "description": state.description,
            "parsed_log": state.parsed_log.to_dict(),
            "codegraph_results": [
                {
                    "ok": item.ok,
                    "query": item.query,
                    "project_path": item.project_path,
                    "output_preview": item.output[:3000] if item.output else "",
                    "error": item.error,
                }
                for item in state.codegraph_results
            ],
            "suggested_search_terms": state.search_terms[:30],
            "searched_terms": state.searched_terms[-20:],
            "recent_steps": state.steps[-8:],
            "available_matches": [match.to_dict() for match in self._rank_matches(state.matches)[:15]],
            "read_files": [f"{snippet.path}:{snippet.start_line}-{snippet.end_line}" for snippet in state.snippets],
            "errors": state.errors[-5:],
        }

    def _extract_json(self, content):
        text = content.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?", "", text).strip()
            text = re.sub(r"```$", "", text).strip()
        return text

    def _optional_int(self, value):
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _new_case_id(self):
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return f"CASE-{stamp}-{uuid.uuid4().hex[:6].upper()}"

    def _save_case(self, result):
        path = self.case_dir / f"{result['case_id']}.json"
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
