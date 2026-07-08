from datetime import datetime

from app.db.query_tool import DBQueryTool


class DBInvestigator:
    def __init__(self, query_tool=None):
        self.query_tool = query_tool or DBQueryTool()

    def investigate(self, lot_id, fab, env):
        result = {
            "lot_id": lot_id,
            "fab": fab,
            "env": env,
            "queries": [],
            "rule_name": None,
            "server_ip": None,
            "module": None,
            "handled_at": None,
            "warnings": [],
        }

        lot_history = self._safe_query("query_lot_history", {"lot_id": lot_id})
        result["queries"].append({"query_id": "query_lot_history", "result": lot_history})

        lot_module = self._safe_query("query_lot_module", {"lot_id": lot_id})
        result["queries"].append({"query_id": "query_lot_module", "result": lot_module})

        rule_name = self._resolve_rule_name(lot_history.get("rows", []))
        result["rule_name"] = rule_name

        if not rule_name:
            result["warnings"].append("No rule_name found from LotHistory. Add business rules or improve SQL templates.")
            self._fill_module_from_lot_module(result, lot_module.get("rows", []))
            return result

        rule_execution = self._safe_query("query_rule_execution", {"lot_id": lot_id, "rule_name": rule_name})
        result["queries"].append({"query_id": "query_rule_execution", "result": rule_execution})

        self._fill_execution(result, rule_execution.get("rows", []))
        if not result["module"]:
            self._fill_module_from_lot_module(result, lot_module.get("rows", []))

        return result

    def _safe_query(self, query_id, params):
        try:
            return self.query_tool.run_query(query_id, params)
        except Exception as exc:
            return {"rows": [], "error": str(exc)}

    def _resolve_rule_name(self, rows):
        for row in rows:
            for key in ("rule_name", "RULE_NAME", "ruleName", "RULE"):
                value = row.get(key)
                if value:
                    return str(value)
        return None

    def _fill_execution(self, result, rows):
        if not rows:
            result["warnings"].append("No rule execution record found for lotId + ruleName.")
            return

        row = rows[0]
        result["server_ip"] = row.get("server_ip") or row.get("SERVER_IP")
        result["module"] = row.get("module") or row.get("MODULE")
        result["handled_at"] = row.get("handled_at") or row.get("HANDLED_AT")
        result["env"] = row.get("env") or row.get("ENV") or result["env"]

    def _fill_module_from_lot_module(self, result, rows):
        if rows and not result["module"]:
            row = rows[0]
            result["module"] = row.get("module") or row.get("MODULE")
