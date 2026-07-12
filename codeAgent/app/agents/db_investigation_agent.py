class DBInvestigationAgent:
    def run(self, context):
        parsed = context.get("parsed", {})
        lot_id = parsed.get("lot_id")
        fab = parsed.get("fab")
        env = parsed.get("env")
        module = parsed.get("module") or "R2R"
        rule_name = parsed.get("rule_name") or "MockRecipeCheckRule"

        server_ip = self._mock_server_ip(fab, env)
        handled_at = "2026-07-06 05:02:56"

        return {
            "ok": True,
            "agent": "DBInvestigationAgent",
            "summary": "使用 mock DB 数据定位到 rule 执行记录。",
            "data": {
                "lot_id": lot_id,
                "fab": fab,
                "env": env,
                "rule_name": rule_name,
                "server_ip": server_ip,
                "module": module,
                "handled_at": handled_at,
            },
            "evidence": [
                {
                    "source": "mock.lot_history",
                    "content": f"lot_id={lot_id}, module={module}, rule_name={rule_name}",
                },
                {
                    "source": "mock.rule_execution",
                    "content": f"server_ip={server_ip}, handled_at={handled_at}, env={env}",
                },
            ],
            "warnings": ["当前分支 DB 使用 mock 数据，后续可替换为真实 DBQueryTool。"],
        }

    def _mock_server_ip(self, fab, env):
        if fab == "Fab2" and env == "prod":
            return "10.22.2.36"
        if fab == "Fab2":
            return "10.22.1.36"
        if env == "prod":
            return "10.11.2.25"
        return "10.11.1.25"

