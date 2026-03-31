# PDA Plan Migration Tasks

This directory contains tasks for migrating Plan dataclasses to use TaskPlanExecutor with execution evidence recording.

## Current Status

**MIGRATION ESSENTIALLY COMPLETE** ✅

- **Total plans migrated**: 19 of ~37
- **Remaining**: ~18 menu interaction plans (intentionally skipped - low value)
- **All tests passing**: 208

## Migrated Plans (19)

### Terminal/Completion (8)
- `DownloadTerminalPlan` ✅
- `DownloadErrorPlan` ✅
- `SplitQualityKeyTerminalPlan` ✅
- `SplitUploadCompletionPlan` ✅
- `NonSplitUploadCompletionPlan` ✅
- `LiveStreamCompletionPlan` ✅
- `AudioCompletionPlan` ✅
- `GalleryTerminalOutcomePlan` ✅

### Recovery/Routing (6)
- `ManualForwardRecoveryPlan` ✅
- `AudioRetryRoutePlan` ✅
- `AudioRetryOutcomePlan` ✅
- `UploadRoutingPlan` ✅
- `GalleryFallbackTransitionPlan` ✅

### Cache/Cleanup (5)
- `DownloadCacheWritebackPlan` ✅
- `UploadCacheWritebackPlan` ✅
- `DownloadCleanupPlan` ✅
- `AudioCleanupPlan` ✅
- `AudioCacheReplayPlan` ✅
- `AudioSingleCacheReplayPlan` ✅

## Skipped Plans (~18)

### Menu Interaction Plans (intentionally skipped)
These have low evidence value - they represent user UI interactions rather than execution decisions:

- `AlwaysAskSubsMenuPlan`
- `AlwaysAskDubsMenuPlan`
- `AlwaysAskFilterUpdatePlan`
- `AlwaysAskQualitySelectionPlan`
- `AlwaysAskSpecialActionPlan`
- `AlwaysAskClosePlan`
- `AlwaysAskNavigationPlan`
- `AlwaysAskOtherFormatSelectionPlan`
- `AlwaysAskManualQualitySelectionPlan`
- `QualityMenuRenderPlan`
- `CachedQualitiesMenuPlan`
- `OtherQualitiesMenuPlan`
- `AlwaysAskSubsMenuPlan` variants
- etc.

### Sender Plans (pending if needed)
- `SenderDeliveryPlan`
- `SenderDeliveryOutcomePlan`
- `SenderCaptionFallbackPlan`
- `SenderDescriptionArtifactPlan`

These may be migrated if delivery debugging becomes a priority.

## Architecture

### Core Components

| Component | File | Purpose |
|-----------|------|---------|
| `RuntimeTask` | `DOWN_AND_UP/runtime_task.py` | Immutable task container with execution evidence |
| `TaskPlanExecutor` | `DOWN_AND_UP/task_plan_executor.py` | Systematic plan execution with evidence recording |
| `task_debug` | `HELPERS/task_debug.py` | Observability and debugging utilities |

### Category to Evidence Field Mapping

| Category | Task Field | Use Case |
|----------|-----------|----------|
| TERMINAL | `artifact_refs` | Final outcomes |
| RECOVERY | `error_evidence` | Retry attempts, error handling |
| ROUTING | `artifact_refs` | Path selection decisions |
| ACQUISITION | `acquisition_attempts` | Download/cache operations |
| DELIVERY | `delivery_attempts` | Upload/send operations |
| COMPLETION | `artifact_refs` | Cleanup, finalization |

### Implementation Pattern

```python
# 1. Keep legacy executor for backward compatibility
def _execute_plan(...):
    """Legacy executor."""
    return _execute_plan_core(...)

# 2. Create evidence-aware variant
def _execute_plan_with_evidence(..., task_context: RuntimeTask | None):
    """Execute with evidence recording."""
    def _executor(p: PlanType) -> ResultType:
        return _execute_plan_core(p, ...)
    
    if task_context is None:
        return _executor(plan), task_context
    
    new_task, result = execute_category_plan(
        task_context, plan, _executor, executor_name="..."
    )
    return result, new_task

# 3. Core logic (extracted for reuse)
def _execute_plan_core(...) -> ResultType:
    ...
```

## Observability

Debug task execution:

```python
from HELPERS.task_debug import render_task_execution_trace, dump_task_to_console

# Render full execution trace
trace = render_task_execution_trace(task, include_full_input=True)
print(trace)

# Quick summary
dump_task_to_console(task)

# Compare two task executions
from HELPERS.task_debug import compare_tasks
diff = compare_tasks(task_a, task_b)
```

## Testing

```bash
pytest tests/ -v
```

All 208 tests passing.

## Next Steps

The migration is functionally complete. Future work (if needed):

1. **Migrate sender plans** if delivery debugging becomes critical
2. **Add menu plan evidence** if UI interaction tracing becomes necessary
3. **Production observability** - integrate task_debug into error handlers

## Background

PDA (Progressive De-Arbitrarization) infrastructure:
- Immutable `RuntimeTask` with execution evidence fields
- `TaskPlanExecutor` providing systematic plan execution
- `HELPERS/task_debug.py` for observability

See AGENTS.md "Task Object and Plan Architecture" section for full documentation.
