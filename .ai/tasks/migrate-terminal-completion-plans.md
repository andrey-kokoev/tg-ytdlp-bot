# Task: Migrate Terminal and Completion Plans to TaskPlanExecutor

## Status
Ready for implementation

## Background
PDA infrastructure is complete. RuntimeTask is immutable with execution evidence fields. TaskPlanExecutor provides systematic plan execution with evidence recording.

Three high-traffic paths already migrated:
- GalleryTerminalOutcomePlan (COMMANDS/image_cmd.py)
- AudioRetryOutcomePlan (DOWN_AND_UP/down_and_audio.py)
- UploadRoutingPlan (DOWN_AND_UP/down_and_up.py)

This task migrates the terminal outcome and completion plans which are high-value for debugging production issues.

## Plans to Migrate

### Terminal Plans
1. **DownloadTerminalPlan** (DOWN_AND_UP/down_and_up.py)
   - Used in: `_build_download_terminal_plan()`, `_execute_download_terminal_plan()`
   - Category: TERMINAL
   - Evidence value: Final upload status, cleanup decisions

2. **DownloadErrorPlan** (DOWN_AND_UP/down_and_up.py)
   - Used in: `_build_download_error_plan()`, `_execute_download_error_plan()`
   - Category: RECOVERY (error handling)
   - Evidence value: Error classification, retry decisions

3. **SplitQualityKeyTerminalPlan** (DOWN_AND_UP/down_and_up.py)
   - Used in: Split upload finalization
   - Category: TERMINAL
   - Evidence value: Split completion status

### Completion Plans
4. **SplitUploadCompletionPlan** (DOWN_AND_UP/down_and_up.py)
   - Used in: `_execute_split_upload_completion_plan()`
   - Category: COMPLETION
   - Evidence value: Cache writeback, finalization status

5. **NonSplitUploadCompletionPlan** (DOWN_AND_UP/down_and_up.py)
   - Used in: `_execute_nonsplit_upload_completion_plan()`
   - Category: COMPLETION
   - Evidence value: Success messaging, cleanup decisions

6. **LiveStreamCompletionPlan** (DOWN_AND_UP/live_stream_downloader.py)
   - Used in: Live stream finalization
   - Category: COMPLETION
   - Evidence value: Chunk completion, final assembly

7. **AudioCompletionPlan** (DOWN_AND_UP/down_and_audio.py)
   - Used in: Audio download completion
   - Category: COMPLETION
   - Evidence value: Final audio processing status

## Implementation Pattern

Follow the established pattern from migrated plans:

```python
# 1. Keep the legacy executor for backward compatibility
def _execute_existing_plan(...):
    """Legacy executor - backward compatibility."""
    return _execute_existing_plan_core(...)

# 2. Create new evidence-aware executor
def _execute_existing_plan_with_evidence(
    *,
    ...,
    task_context: RuntimeTask | None,
) -> tuple[ResultType, RuntimeTask]:
    """
    PDA-refactored executor using TaskPlanExecutor.
    Returns (result, updated_task) with execution evidence recorded.
    """
    def _executor(p: PlanType) -> ResultType:
        return _execute_existing_plan_core(...)

    if task_context is None:
        result = _executor(plan)
        return result, task_context

    new_task, result = execute_terminal_plan(
        task_context,
        plan,
        _executor,
        executor_name="_execute_existing_plan",
    )
    return result, new_task

# 3. Extract core logic to _execute_existing_plan_core()
def _execute_existing_plan_core(...) -> ResultType:
    """Core plan logic (extracted for reuse)."""
    ...
```

## Category Assignment

| Plan | Category | Rationale |
|------|----------|-----------|
| DownloadTerminalPlan | TERMINAL | Final outcome determination |
| DownloadErrorPlan | RECOVERY | Error handling and recovery |
| SplitQualityKeyTerminalPlan | TERMINAL | Terminal split outcome |
| SplitUploadCompletionPlan | COMPLETION | Finalization and cleanup |
| NonSplitUploadCompletionPlan | COMPLETION | Finalization and cleanup |
| LiveStreamCompletionPlan | COMPLETION | Stream finalization |
| AudioCompletionPlan | COMPLETION | Audio finalization |

## Testing

- Run full test suite: `pytest tests/`
- Verify evidence accumulation in tests
- Use HELPERS/task_debug.py to validate trace output

## Acceptance Criteria

- [ ] All 7 plans migrated to use TaskPlanExecutor
- [ ] Legacy executors preserved for backward compatibility
- [ ] New `_with_evidence` variants available
- [ ] All 208+ tests passing
- [ ] Evidence structure validated with task_debug.render_summary()

## Dependencies

- DOWN_AND_UP/task_plan_executor.py (exists)
- DOWN_AND_UP/runtime_task.py (exists)
- HELPERS/task_debug.py (exists)
