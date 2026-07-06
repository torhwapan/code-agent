import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

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
        self.searched_terms = []
        self.read_keys = set()
        self.errors = []


class CodeAnalysisAgent:
    def __init__(self, tools, llm=None, case_dir="data/cases"):
        self.tools = tools
        self.llm = llm or LLMClient()
        self.parser = LogParser()
        self.case_dir = Path(case_dir)
        self.case_dir.mkdir(parents=True, exist_ok=True)

    def analyze(self, repo_id, raw_log, description="", max_steps=8):
        parsed = self.parser.parse(raw_log)
        state = AgentState(
            case_id=self._new_case_id(),
            repo_id=repo_id,
            description=description.strip(),
            raw_log=raw_log,
            parsed_log=parsed,
            search_terms=self.parser.build_search_terms(parsed),
        )

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
            "llm_enabled": self.llm.available,
            "parsed_log": parsed.to_dict(),
            "search_terms": state.search_terms,
            "steps": state.steps,
            "matches": [match.to_dict() for match in state.matches[:80]],
            "snippets": [snippet.to_dict() for snippet in state.snippets],
            "observations": state.observations,
            "errors": state.errors,
            "report": report,
        }
        self._save_case(result)
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

    def _run_rule_based_loop(self, state, max_steps):
        for term in state.search_terms[: max(3, max_steps)]:
            self._search(state, term, "Rule-based search from parsed log signal")
            if len(state.matches) >= 20:
                break

        self._read_top_matches(state, 8)
        state.observations.append("LLM is not configured, so the report is based on parsed log signals and code search/read evidence.")

    def _ask_next_action(self, state, step_index):
        prompt = {
            "task": "You are a code analysis agent. Decide the next tool action to diagnose code from an incident log.",
            "allowed_actions": [
                {"action": "search_code", "query": "term to search", "reason": "why this search matters"},
                {"action": "read_file", "path": "relative path", "start_line": 1, "end_line": 120, "reason": "why this file range matters"},
                {"action": "final", "reason": "enough evidence or blocked"},
            ],
            "rules": [
                "Prefer exact classes, methods, error codes, SQL table names, and constants from the log.",
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
            "parsed_log": state.parsed_log.to_dict(),
            "steps": state.steps,
            "observations": state.observations,
            "code_snippets": [snippet.to_dict() for snippet in state.snippets],
            "instruction": "Generate a Chinese Markdown code analysis report with evidence. Include likely cause, related files, call path, confidence, missing information, and next steps. If evidence is insufficient, say so clearly.",
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

        return "\n".join(
            [
                "# Code Analysis Report",
                "",
                "## 1. Summary",
                f"- Error / exception: {errors}",
                f"- Main search terms: {terms}",
                f"- Code snippets read: {len(state.snippets)}",
                "",
                "## 2. Log Signals",
                f"- Error codes: {', '.join(parsed.error_codes) or 'N/A'}",
                f"- Exceptions: {', '.join(parsed.exceptions) or 'N/A'}",
                f"- Classes: {', '.join(parsed.classes[:10]) or 'N/A'}",
                f"- Methods: {', '.join(parsed.methods[:10]) or 'N/A'}",
                f"- Tables: {', '.join(parsed.tables[:10]) or 'N/A'}",
                "",
                "## 3. Related Code Locations",
                *files,
                "",
                "## 4. Initial Judgment",
                "- LLM is not configured, so this report only shows rule-based code location results.",
                "- Please inspect the listed files and nearby lines first, especially error handling, SQL/table access, and state validation branches.",
                "",
                "## 5. Next Steps",
                "- Configure `LLM_API_KEY` and model settings to enable multi-step LLM analysis.",
                "- If too many files match, add system/module information or keep the full stack trace in the log.",
            ]
        )

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
