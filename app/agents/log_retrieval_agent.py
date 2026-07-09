class LogRetrievalAgent:
    def run(self, context):
        db_data = context.get("db_result", {}).get("data", {})
        lot_id = db_data.get("lot_id")
        rule_name = db_data.get("rule_name")
        module = db_data.get("module")
        env = db_data.get("env")
        server_ip = db_data.get("server_ip")
        handled_at = db_data.get("handled_at")

        log_text = "\n".join(
            [
                f"2026-07-06 05:02:54 INFO [{module}] Start rule execution lotId={lot_id} ruleName={rule_name}",
                f"2026-07-06 05:02:56 ERROR [{module}] RuleExecutionTimeoutException: rule {rule_name} timeout while handling lot {lot_id}",
                "2026-07-06 05:02:56 ERROR at app.db.investigator.DBInvestigator.investigate(DBInvestigator.java:42)",
                "2026-07-06 05:02:56 ERROR at app.investigation.case_investigator.CaseInvestigator.investigate(CaseInvestigator.java:31)",
                "2026-07-06 05:02:57 WARN retry disabled because recipe state is WAIT_R2R_REPLY",
            ]
        )

        return {
            "ok": True,
            "agent": "LogRetrievalAgent",
            "summary": "使用 mock FTP 日志生成目标时间窗口日志片段。",
            "data": {
                "env": env,
                "server_ip": server_ip,
                "module": module,
                "handled_at": handled_at,
                "remote_dir": f"{env}/{server_ip}/{module}",
                "log_text": log_text,
            },
            "evidence": [
                {
                    "source": "mock.ftp",
                    "content": f"{env}/{server_ip}/{module}/mock-26-07-06T05_02_56.log",
                }
            ],
            "warnings": ["当前分支日志检索使用 mock 数据，后续可替换为 FTPLogFetcher。"],
        }

