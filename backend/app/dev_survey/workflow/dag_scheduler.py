import asyncio
from typing import Dict, Any, List, Set, Optional, Tuple
from dataclasses import dataclass, field
from harness.logger import logger
from app.dev_survey.models.models import Task


@dataclass
class DAGExecutionResult:
    results: List[Dict[str, Any]] = field(default_factory=list)
    levels: int = 0
    skipped_task_ids: List[str] = field(default_factory=list)
    degraded_to_parallel: bool = False


class DAGTaskScheduler:

    def __init__(self, parallel_executor):
        self.executor = parallel_executor

    async def execute(
        self,
        task_dicts: List[Dict[str, Any]],
        workflow_id: str,
        trace_context=None,
    ) -> DAGExecutionResult:
        try:
            return await self._execute_dag(task_dicts, workflow_id, trace_context)
        except Exception as e:
            logger.error(
                f"[DAG Scheduler] Internal error, degrading to full parallel: {e}",
                exc_info=True
            )
            return await self._execute_flat_parallel(task_dicts, workflow_id, trace_context)

    async def _execute_dag(
        self,
        task_dicts: List[Dict[str, Any]],
        workflow_id: str,
        trace_context=None,
    ) -> DAGExecutionResult:
        pending_ids = {t["task_id"] for t in task_dicts if t.get("status") != "completed"}
        if not pending_ids:
            return DAGExecutionResult(results=[], levels=0)

        has_dependencies = False
        for t in task_dicts:
            if t["task_id"] in pending_ids:
                deps = t.get("depends_on")
                # 规范化 depends_on 来判断是否有依赖
                if deps is not None and isinstance(deps, list) and len(deps) > 0:
                    has_dependencies = True
                    break
        if not has_dependencies:
            return await self._execute_flat_parallel(task_dicts, workflow_id, trace_context)

        tid_to_task = {t["task_id"]: t for t in task_dicts if t["task_id"] in pending_ids}
        task_id_set = set(tid_to_task.keys())

        in_degree = {}
        reverse_deps = {}
        for tid in pending_ids:
            raw_deps = tid_to_task[tid].get("depends_on")
            # 规范化 depends_on
            if raw_deps is None:
                raw_deps = []
            elif not isinstance(raw_deps, list):
                raw_deps = []
            
            valid_deps = set()
            for dep_id in raw_deps:
                if dep_id not in task_id_set:
                    logger.warning(
                        f"[DAG Scheduler] Task {tid} depends_on invalid task_id '{dep_id}', stripping"
                    )
                else:
                    valid_deps.add(dep_id)
            in_degree[tid] = len(valid_deps)
            if tid not in reverse_deps:
                reverse_deps[tid] = set()
            for dep_id in valid_deps:
                if dep_id not in reverse_deps:
                    reverse_deps[dep_id] = set()
                reverse_deps[dep_id].add(tid)

        has_cycle, cycle_edge = self._detect_cycle(in_degree, reverse_deps, task_id_set)
        if has_cycle:
            logger.warning(
                f"[DAG Scheduler] Cycle detected involving edge {cycle_edge}, breaking cycle"
            )
            self._break_cycle(cycle_edge, in_degree, reverse_deps)

        results = []
        skipped_ids = []
        levels = 0

        while pending_ids:
            ready = sorted(tid for tid in pending_ids if in_degree[tid] == 0)

            if not ready:
                logger.error(
                    f"[DAG Scheduler] Invariant violated: no ready tasks in DAG with {len(pending_ids)} pending. "
                    f"Degrading to parallel for remaining tasks."
                )
                flat_results = await self.executor.execute_tasks_parallel(
                    self._dicts_to_tasks([tid_to_task[tid] for tid in pending_ids], workflow_id),
                    trace_context=trace_context
                )
                results.extend(flat_results)
                break

            levels += 1
            logger.info(
                f"[DAG Scheduler] Level {levels}: executing {len(ready)} tasks in parallel"
            )

            level_tasks = [tid_to_task[tid] for tid in ready]
            level_results = await self.executor.execute_tasks_parallel(
                self._dicts_to_tasks(level_tasks, workflow_id), trace_context=trace_context
            )
            results.extend(level_results)

            for result in level_results:
                tid = result["task_id"]
                pending_ids.discard(tid)

                if result.get("status") == "failed":
                    downstream = self._collect_downstream(tid, reverse_deps)
                    for ds_tid in downstream:
                        if ds_tid in pending_ids:
                            skipped_ids.append(ds_tid)
                            pending_ids.discard(ds_tid)
                            results.append({
                                "task_id": ds_tid,
                                "title": tid_to_task[ds_tid].get("title", ""),
                                "status": "skipped",
                                "summary": None,
                                "sources_summary": None,
                                "notices": f"Skipped: upstream task '{tid}' failed",
                            })

                for dep_tid in reverse_deps.get(tid, set()):
                    if dep_tid in in_degree:
                        in_degree[dep_tid] = max(0, in_degree[dep_tid] - 1)

        return DAGExecutionResult(
            results=results,
            levels=levels,
            skipped_task_ids=skipped_ids,
            degraded_to_parallel=False,
        )

    async def _execute_flat_parallel(
        self,
        task_dicts: List[Dict[str, Any]],
        workflow_id: str,
        trace_context=None,
    ) -> DAGExecutionResult:
        pending = [t for t in task_dicts if t.get("status") != "completed" and t.get("status") != "skipped"]
        if not pending:
            return DAGExecutionResult(results=[], levels=1)

        logger.info(
            f"[DAG Scheduler] Flat parallel execution: {len(pending)} tasks"
        )
        results = await self.executor.execute_tasks_parallel(
            self._dicts_to_tasks(pending, workflow_id), trace_context=trace_context
        )
        return DAGExecutionResult(
            results=results,
            levels=1,
            degraded_to_parallel=True,
        )

    def _detect_cycle(
        self,
        in_degree: Dict[str, int],
        reverse_deps: Dict[str, Set[str]],
        task_id_set: Set[str],
    ) -> Tuple[bool, Optional[Tuple[str, str]]]:
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {tid: WHITE for tid in task_id_set}

        def dfs(u: str) -> Optional[Tuple[str, str]]:
            color[u] = GRAY
            for v in reverse_deps.get(u, set()):
                if v not in color:
                    continue
                if color[v] == GRAY:
                    return (u, v)
                if color[v] == WHITE:
                    result = dfs(v)
                    if result:
                        return result
            color[u] = BLACK
            return None

        for tid in task_id_set:
            if color[tid] == WHITE:
                result = dfs(tid)
                if result:
                    return True, result
        return False, None

    def _break_cycle(
        self,
        cycle_edge: Tuple[str, str],
        in_degree: Dict[str, int],
        reverse_deps: Dict[str, Set[str]],
    ) -> None:
        u, v = cycle_edge
        if v in reverse_deps.get(u, set()):
            reverse_deps[u].discard(v)
        if v in in_degree:
            in_degree[v] = max(0, in_degree[v] - 1)
        logger.info(f"[DAG Scheduler] Removed edge {u} -> {v} to break cycle")

    def _collect_downstream(
        self,
        failed_tid: str,
        reverse_deps: Dict[str, Set[str]],
    ) -> Set[str]:
        visited = set()
        stack = [failed_tid]
        while stack:
            cur = stack.pop()
            for dep in reverse_deps.get(cur, set()):
                if dep not in visited:
                    visited.add(dep)
                    stack.append(dep)
        return visited

    def _dicts_to_tasks(self, task_dicts: List[Dict[str, Any]], workflow_id: str = "") -> List[Task]:
        tasks = []
        for d in task_dicts:
            depends_on = d.get("depends_on")
            if depends_on is None:
                depends_on = []
            elif not isinstance(depends_on, list):
                depends_on = []
            else:
                depends_on = [str(x) for x in depends_on if isinstance(x, (str, int))]
            
            task = Task(
                task_id=d['task_id'],
                workflow_id=d.get('workflow_id') or workflow_id,
                title=d.get('title', ''),
                intent=d.get('intent', ''),
                query=d.get('query', ''),
                order=d.get('order', 0),
                depends_on=depends_on,
                status=d.get('status', 'pending'),
            )
            tasks.append(task)
        return tasks
