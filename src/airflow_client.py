from abc import ABC, abstractmethod
import os
from urllib.parse import quote
import requests
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth
load_dotenv()

class BaseAirflowClient(ABC):
    @abstractmethod
    def get_dags(self) -> list[dict]: ...

    @abstractmethod
    def get_dag_status(self, dag_id: str) -> dict: ...

    @abstractmethod
    def get_dag_run_history(self, dag_id: str, limit: int = 5) -> list[dict]: ...

    @abstractmethod
    def get_failed_task_logs(self, dag_id: str, run_id: str) -> list[dict]: ...

class RealAirflowClient(BaseAirflowClient):
    def __init__(self, base_url: str, username: str, password: str):
        normalized_base_url = base_url.rstrip("/")
        if not normalized_base_url.endswith("/api/v1"):
            normalized_base_url = f"{normalized_base_url}/api/v1"

        self.base_url = normalized_base_url
        self.username = username
        self.password = password
        self.auth = HTTPBasicAuth(username, password)

    def _build_url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def _get_json(self, path: str, params: dict | None = None) -> dict:
        response = requests.get(
            url=self._build_url(path),
            auth=self.auth,
            headers={"Content-Type": "application/json"},
            params=params,
            timeout=30
        )
        response.raise_for_status()
        return response.json()

    def get_dags(self) -> list[dict]:
        try:
            payload = self._get_json("dags")
        except requests.RequestException:
            return []

        dags = payload.get("dags", [])
        return [
            {
                "dag_id": dag.get("dag_id"),
                "is_paused": dag.get("is_paused"),
                "last_parsed_time": dag.get("last_parsed_time"),
            }
            for dag in dags
        ]

    def get_dag_status(self, dag_id: str) -> dict:
        encoded_dag_id = quote(dag_id, safe="")

        try:
            dag = self._get_json(f"dags/{encoded_dag_id}")
            run_history = self.get_dag_run_history(dag_id, limit=1)
        except requests.RequestException as exc:
            return {"dag_id": dag_id, "error": str(exc)}

        if not run_history:
            return {
                "dag_id": dag_id,
                "is_paused": dag.get("is_paused"),
                "last_parsed_time": dag.get("last_parsed_time"),
                "run_id": None,
                "state": "no_runs",
                "start_time": None,
                "end_time": None,
            }

        latest_run = run_history[0]
        return {
            "dag_id": dag_id,
            "is_paused": dag.get("is_paused"),
            "last_parsed_time": dag.get("last_parsed_time"),
            "run_id": latest_run["run_id"],
            "state": latest_run["state"],
            "start_time": latest_run["start_time"],
            "end_time": latest_run["end_time"],
        }

    def get_dag_run_history(self, dag_id: str, limit: int = 5) -> list[dict]:
        if limit <= 0:
            return []

        encoded_dag_id = quote(dag_id, safe="")
        try:
            payload = self._get_json(
                f"dags/{encoded_dag_id}/dagRuns",
                params={"limit": limit, "order_by": "-start_date"}
            )
        except requests.RequestException:
            return []

        dag_runs = payload.get("dag_runs", [])
        return [
            {
                "run_id": dag_run.get("dag_run_id") or dag_run.get("run_id"),
                "state": dag_run.get("state"),
                "start_time": dag_run.get("start_date") or dag_run.get("start_time"),
                "end_time": dag_run.get("end_date") or dag_run.get("end_time"),
            }
            for dag_run in dag_runs
        ]

    def get_failed_task_logs(self, dag_id: str, run_id: str) -> list[dict]:
        encoded_dag_id = quote(dag_id, safe="")
        encoded_run_id = quote(run_id, safe="")

        try:
            payload = self._get_json(f"dags/{encoded_dag_id}/dagRuns/{encoded_run_id}/taskInstances")
        except requests.RequestException:
            return []

        task_instances = payload.get("task_instances", [])
        failed_states = {"failed", "upstream_failed"}
        failed_tasks = [task for task in task_instances if task.get("state") in failed_states]
        failed_logs = []

        for task in failed_tasks:
            task_id = task.get("task_id")
            if not task_id:
                continue

            encoded_task_id = quote(task_id, safe="")
            try_number = task.get("try_number") or 1
            if isinstance(try_number, int) and try_number < 1:
                try_number = 1

            log_text = ""
            try:
                log_response = requests.get(
                    url=self._build_url(
                        f"dags/{encoded_dag_id}/dagRuns/{encoded_run_id}/taskInstances/"
                        f"{encoded_task_id}/logs/{try_number}"
                    ),
                    auth=self.auth,
                    headers={"Content-Type": "application/json"},
                    timeout=30
                )
                log_response.raise_for_status()
                try:
                    log_payload = log_response.json()
                    log_text = log_payload.get("content", "") or log_payload.get("message", "")
                except ValueError:
                    log_text = log_response.text
            except requests.RequestException as e:
                log_text = f"Failed to fetch logs: {e}"

            failed_logs.append(
                {
                    "task_id": task_id,
                    "state": task.get("state"),
                    "log": log_text,
                }
            )

        return failed_logs


class MockAirflowClient (BaseAirflowClient):
    """returns hardcoded but realistic data."""

    def get_dags(self) -> list[dict]:
        """Returns list of mock airflow DAGs"""
        return [
            {"dag_id": "orders_etl", "is_paused": False, "last_parsed_time": "2026-03-22T02:00:00"},
            {"dag_id": "customer_sync", "is_paused": False, "last_parsed_time": "2026-03-22T01:00:00"},
            {"dag_id": "product_catalog_update", "is_paused": True, "last_parsed_time": "2026-03-20T10:00:00"},
        ]

    def get_dag_status(self, dag_id: str) -> dict:
        """gets the latest run status for a specific DAG"""
        run_history = self.get_dag_run_history(dag_id, limit=1)
        if not run_history:
            return {"dag_id": dag_id, "error": "DAG not found"}

        latest_run = run_history[0]
        dag_lookup = {dag["dag_id"]: dag for dag in self.get_dags()}
        dag = dag_lookup.get(dag_id)

        return {
            "dag_id": dag_id,
            "is_paused": dag["is_paused"] if dag else False,
            "last_parsed_time": dag["last_parsed_time"] if dag else None,
            "run_id": latest_run["run_id"],
            "state": latest_run["state"],
            "start_time": latest_run["start_time"],
            "end_time": latest_run["end_time"],
        }

    def get_dag_run_history(self, dag_id: str, limit: int = 5) -> list[dict]:
        """shows the last N runs with success/failure
        Return at least 5 runs with a mix of success and failure states"""
        mock_histories = {
            "orders_etl": [
                {
                    "run_id": "manual__2026-03-22T02:00:00+00:00",
                    "state": "failed",
                    "start_time": "2026-03-22T02:00:00+00:00",
                    "end_time": "2026-03-22T02:14:33+00:00",
                },
                {
                    "run_id": "scheduled__2026-03-21T02:00:00+00:00",
                    "state": "success",
                    "start_time": "2026-03-21T02:00:00+00:00",
                    "end_time": "2026-03-21T02:10:11+00:00",
                },
                {
                    "run_id": "scheduled__2026-03-20T02:00:00+00:00",
                    "state": "success",
                    "start_time": "2026-03-20T02:00:00+00:00",
                    "end_time": "2026-03-20T02:08:54+00:00",
                },
                {
                    "run_id": "scheduled__2026-03-19T02:00:00+00:00",
                    "state": "failed",
                    "start_time": "2026-03-19T02:00:00+00:00",
                    "end_time": "2026-03-19T02:12:47+00:00",
                },
                {
                    "run_id": "scheduled__2026-03-18T02:00:00+00:00",
                    "state": "success",
                    "start_time": "2026-03-18T02:00:00+00:00",
                    "end_time": "2026-03-18T02:09:08+00:00",
                },
            ],
            "customer_sync": [
                {
                    "run_id": "scheduled__2026-03-22T01:00:00+00:00",
                    "state": "running",
                    "start_time": "2026-03-22T01:00:00+00:00",
                    "end_time": None,
                },
                {
                    "run_id": "scheduled__2026-03-21T01:00:00+00:00",
                    "state": "failed",
                    "start_time": "2026-03-21T01:00:00+00:00",
                    "end_time": "2026-03-21T01:06:42+00:00",
                },
                {
                    "run_id": "scheduled__2026-03-20T01:00:00+00:00",
                    "state": "success",
                    "start_time": "2026-03-20T01:00:00+00:00",
                    "end_time": "2026-03-20T01:04:05+00:00",
                },
                {
                    "run_id": "scheduled__2026-03-19T01:00:00+00:00",
                    "state": "failed",
                    "start_time": "2026-03-19T01:00:00+00:00",
                    "end_time": "2026-03-19T01:05:51+00:00",
                },
                {
                    "run_id": "scheduled__2026-03-18T01:00:00+00:00",
                    "state": "success",
                    "start_time": "2026-03-18T01:00:00+00:00",
                    "end_time": "2026-03-18T01:03:49+00:00",
                },
            ],
            "product_catalog_update": [
                {
                    "run_id": "scheduled__2026-03-20T10:00:00+00:00",
                    "state": "queued",
                    "start_time": "2026-03-20T10:00:00+00:00",
                    "end_time": None,
                },
                {
                    "run_id": "scheduled__2026-03-19T10:00:00+00:00",
                    "state": "success",
                    "start_time": "2026-03-19T10:00:00+00:00",
                    "end_time": "2026-03-19T10:07:14+00:00",
                },
                {
                    "run_id": "scheduled__2026-03-18T10:00:00+00:00",
                    "state": "success",
                    "start_time": "2026-03-18T10:00:00+00:00",
                    "end_time": "2026-03-18T10:06:58+00:00",
                },
                {
                    "run_id": "scheduled__2026-03-17T10:00:00+00:00",
                    "state": "failed",
                    "start_time": "2026-03-17T10:00:00+00:00",
                    "end_time": "2026-03-17T10:09:22+00:00",
                },
                {
                    "run_id": "scheduled__2026-03-16T10:00:00+00:00",
                    "state": "success",
                    "start_time": "2026-03-16T10:00:00+00:00",
                    "end_time": "2026-03-16T10:05:43+00:00",
                },
            ],
        }

        history = mock_histories.get(dag_id, [])
        if limit <= 0:
            return []
        return history[:limit]

    def get_failed_task_logs(self, dag_id: str, run_id: str) -> list[dict]:
        """gets the error details for a failed task"""
        failed_logs = {
            ("orders_etl", "manual__2026-03-22T02:00:00+00:00"): [
                {
                    "task_id": "resolve_customer_dim",
                    "state": "failed",
                    "log": "CustomerResolutionError: Timeout connecting to customer service after 30s. "
                           "3 retries exhausted. Task failed at 2026-03-22T02:14:33 UTC."
                },
                {
                    "task_id": "load_orders",
                    "state": "upstream_failed",
                    "log": "Upstream task resolve_customer_dim failed, so load_orders did not run."
                },
            ],
            ("orders_etl", "scheduled__2026-03-19T02:00:00+00:00"): [
                {
                    "task_id": "validate_orders",
                    "state": "failed",
                    "log": "SchemaValidationError: amount contained NULL values for 2 rows and negative values "
                           "for 1 row beyond accepted refund thresholds."
                }
            ],
            ("customer_sync", "scheduled__2026-03-21T01:00:00+00:00"): [
                {
                    "task_id": "upsert_customers",
                    "state": "failed",
                    "log": "UniqueViolation: duplicate key value violates unique constraint on normalized email. "
                           "Batch aborted after encountering alice@example.com mapped to multiple customer IDs."
                }
            ],
            ("customer_sync", "scheduled__2026-03-19T01:00:00+00:00"): [
                {
                    "task_id": "extract_crm_customers",
                    "state": "failed",
                    "log": "APIConnectionError: CRM API returned HTTP 502 for 4 consecutive retries during "
                           "incremental customer sync."
                }
            ],
            ("product_catalog_update", "scheduled__2026-03-17T10:00:00+00:00"): [
                {
                    "task_id": "normalize_product_feed",
                    "state": "failed",
                    "log": "CatalogTransformError: category mapping missing for quick-add products with NULL "
                           "category values. 17 records could not be normalized."
                }
            ],
        }

        return failed_logs.get((dag_id, run_id), [])


def get_airflow_client() -> BaseAirflowClient:
    """Returns real client if AIRFLOW_URL is set, mock otherwise"""
    airflow_url = os.environ.get("AIRFLOW_URL")
    if airflow_url:
        return RealAirflowClient(
            base_url=airflow_url,
            username=os.environ.get("AIRFLOW_USERNAME", "airflow"),
            password=os.environ.get("AIRFLOW_PASSWORD", "airflow")
        )
    return MockAirflowClient()
