# Task: Migrate Recovery and Routing Plans to TaskPlanExecutor

## Metadata
- **Status**: ✅ COMPLETE
- **Priority**: MEDIUM
- **Created**: 2026-03-30
- **Completed**: 2026-03-30
- **Plans**: 6 (5 specified + 1 bonus)
- **Category**: PDA Migration

## Background
PDA infrastructure is complete. This task migrates recovery and routing plans which handle failure scenarios and delivery decisions.

## Plans to Migrate

### Recovery Plans
1. **ManualForwardRecoveryPlan** (DOWN_AND_UP/down_and_up.py)
   - Used in: `_execute_manual_forward_recovery_plan()`
   - Category: RECOVERY
   - Evidence value: Manual retry decisions, recovery route selection

2. **SplitQualityKeyRecoveryPlan** (DOWN_AND_UP/down_and_up.py)
   - Used in: `_execute_split_quality_key_recovery_plan()`
   - Category: RECOVERY
   - Evidence value: Quality key recovery attempts, finalization decisions

3. **AudioRetryRoutePlan** (DOWN_AND_UP/down_and_audio.py)
   - Used in: `_build_audio_retry_route_plan()`, routing logic
   - Category: RECOVERY (routing to retry)
   - Evidence value: Retry route selection, fallback decisions

### Delivery/Routing Plans
4. **SenderDeliveryPlan** (DOWN_AND_UP/sender.py)
   - Used in: Video/audio message sending
   - Category: DELIVERY
   - Evidence value: Send method (paid/document), timeout handling

5. **SenderDeliveryOutcomePlan** (DOWN_AND_UP/sender.py)
   - Used in: Delivery result handling
   - Category: DELIVERY
   - Evidence value: Delivery success/failure classification

6. **SenderCaptionFallbackPlan** (DOWN_AND_UP/sender.py)
   - Used in: Caption retry on failure
   - Category: RECOVERY (caption handling)
   - Evidence value: Fallback triggers, minimal caption usage

7. **SenderDescriptionArtifactPlan** (DOWN_AND_UP/sender.py)
   - Used in: Description file handling
   - Category: DELIVERY
   - Evidence value: Description send/cleanup decisions

## Implementation Pattern

Follow established pattern. Key difference: these plans often need access to task_context during execution for state decisions.

Example for recovery plan:
```python
def _execute_recovery_plan_with_evidence(
    *,
    plan: RecoveryPlanType,
    message,
    user_id: int,
    task_context: RuntimeTask | None,
    **kwargs
) -> tuple[ResultType, RuntimeTask]:
    def _executor(p: RecoveryPlanType) -> ResultType:
        # Use closure to access message, user_id, etc.
        return _execute_recovery_plan_core(p, message, user_id, **kwargs)

    if task_context is None:
        result = _executor(plan)
        return result, task_context

    new_task, result = execute_recovery_plan(
        task_context,
        plan,
        _executor,
        executor_name="_execute_recovery_plan",
    )
    return result, new_task
```

## Category Assignment

| Plan | Category | Evidence Target Field |
|------|----------|----------------------|
| ManualForwardRecoveryPlan | RECOVERY | error_evidence |
| SplitQualityKeyRecoveryPlan | RECOVERY | error_evidence |
| AudioRetryRoutePlan | RECOVERY | error_evidence |
| SenderDeliveryPlan | DELIVERY | delivery_attempts |
| SenderDeliveryOutcomePlan | DELIVERY | delivery_attempts |
| SenderCaptionFallbackPlan | RECOVERY | error_evidence |
| SenderDescriptionArtifactPlan | DELIVERY | delivery_attempts |

## Special Considerations

### Sender Module Plans
Sender plans (DOWN_AND_UP/sender.py) are called from many locations:
- `down_and_up.py` (video uploads)
- `down_and_audio.py` (audio uploads)
- Gallery fallback paths

Migration strategy:
1. Add evidence-aware variants in sender.py
2. Update call sites incrementally
3. Pass task_context through the call chain

### Recovery Plan Chain
Recovery plans often chain:
```
Error → Build RecoveryPlan → Execute → Maybe Retry → Terminal
```

Ensure evidence accumulates across the chain:
- Each plan execution adds to task evidence
- Final task shows full recovery attempt history

## Testing

- Test recovery scenarios specifically
- Verify error_evidence accumulation
- Test delivery_attempts accumulation in sender paths
- Use compare_tasks() to verify divergence detection

## Acceptance Criteria

- [ ] All 7 plans migrated to use TaskPlanExecutor
- [ ] Sender module plans callable with and without task_context
- [ ] Recovery chain evidence accumulation verified
- [ ] All 208+ tests passing
- [ ] No regression in upload/delivery functionality

## Dependencies

- Task: migrate-terminal-completion-plans.md (should complete first)
- DOWN_AND_UP/task_plan_executor.py
- DOWN_AND_UP/runtime_task.py
