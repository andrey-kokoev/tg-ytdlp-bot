# PDA Plan Migration Tasks

This directory contains tasks for migrating remaining Plan dataclasses to use TaskPlanExecutor with execution evidence recording.

## Background

PDA (Progressive De-Arbitrarization) infrastructure is complete:
- Immutable `RuntimeTask` with execution evidence fields
- `TaskPlanExecutor` providing systematic plan execution
- `HELPERS/task_debug.py` for observability

Three high-traffic paths already migrated:
- GalleryTerminalOutcomePlan
- AudioRetryOutcomePlan  
- UploadRoutingPlan

## Task Priority

### 1. Terminal and Completion Plans (HIGH)
**File**: `migrate-terminal-completion-plans.md`

Terminal outcomes and completion finalization. Highest value for debugging production issues.

**Plans**: 7
- DownloadTerminalPlan
- DownloadErrorPlan
- SplitQualityKeyTerminalPlan
- SplitUploadCompletionPlan
- NonSplitUploadCompletionPlan
- LiveStreamCompletionPlan
- AudioCompletionPlan

### 2. Recovery and Routing Plans (MEDIUM)
**File**: `migrate-recovery-routing-plans.md`

Failure handling and delivery routing. Medium value for understanding retry chains.

**Plans**: 7
- ManualForwardRecoveryPlan
- SplitQualityKeyRecoveryPlan
- AudioRetryRoutePlan
- SenderDeliveryPlan
- SenderDeliveryOutcomePlan
- SenderCaptionFallbackPlan
- SenderDescriptionArtifactPlan

### 3. Cache and Cleanup Plans (LOW)
**File**: `migrate-cache-cleanup-plans.md`

Cache operations and file cleanup. Lower value but useful for operational debugging.

**Plans**: 6
- DownloadCacheWritebackPlan
- UploadCacheWritebackPlan
- AudioCacheReplayPlan
- AudioSingleCacheReplayPlan
- DownloadCleanupPlan
- AudioCleanupPlan

### 4. Menu Interaction Plans (LOWEST)
**File**: `migrate-menu-interaction-plans.md`

UI menu state and callback handling. Lowest value - consider skipping.

**Plans**: 14 (or skip)
- GalleryFallbackTransitionPlan (migrate - has execution impact)
- 13 AlwaysAsk menu plans (consider skipping)

## Implementation Pattern

Each task follows the established pattern:

1. Keep legacy executor for backward compatibility
2. Create `_execute_plan_with_evidence()` variant
3. Extract core logic to `_execute_plan_core()`
4. Use appropriate category executor:
   - `execute_terminal_plan()` for terminal outcomes
   - `execute_recovery_plan()` for error handling
   - `execute_routing_plan()` for routing decisions
   - `execute_plan()` with category for others

## Category to Evidence Field Mapping

| Category | Task Field | Use Case |
|----------|-----------|----------|
| TERMINAL | artifact_refs | Final outcomes |
| RECOVERY | error_evidence | Retry attempts, error handling |
| ROUTING | artifact_refs | Path selection decisions |
| ACQUISITION | acquisition_attempts | Download/cache operations |
| DELIVERY | delivery_attempts | Upload/send operations |
| COMPLETION | artifact_refs | Cleanup, finalization |

## Testing

Run full test suite after each task:
```bash
pytest tests/ -v
```

Verify evidence structure:
```python
from HELPERS.task_debug import render_summary, dump_task_to_console
# After plan execution
dump_task_to_console(task, verbose=True)
```

## Total Plans

- Migrated: 3
- Remaining: ~34
- Total in codebase: ~37

## Completion Criteria

All tasks complete when:
- High and medium priority plans migrated
- Low priority plans migrated or explicitly skipped
- All tests passing
- No regression in core functionality
