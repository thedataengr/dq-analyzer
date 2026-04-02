import json
from datetime import datetime, timezone


def log_fix_attempt(
        table_name: str,
        fix_sql: str,
        decision: str,
        issue_description: str
):
    """Append a fix approval or rejection event to the audit log.

    Args:
        table_name: Name of the table targeted by the proposed fix.
        fix_sql: SQL statement proposed for the fix.
        decision: Human decision recorded for the fix attempt.
        issue_description: Description of the issue the fix addresses.

    Returns:
        None

    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "table": table_name,
        "issue": issue_description,
        "fix_sql": fix_sql,
        "decision": decision  # "approved" or "rejected"
    }

    with open("fix_audit_log.jsonl", "a") as f:
        f.write(json.dumps(entry) + "\n")

    print(f"[audit] Fix attempt logged: {decision}")
