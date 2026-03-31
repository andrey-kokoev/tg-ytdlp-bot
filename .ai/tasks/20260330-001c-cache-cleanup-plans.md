# Task: Migrate Cache and Cleanup Plans to TaskPlanExecutor

## Metadata
- **Status**: 📋 Ready
- **Priority**: LOW
- **Created**: 2026-03-30
- **Plans**: 6
- **Category**: PDA Migration

## Background
Cache and cleanup plans handle file system operations and cache management. These are lower priority than terminal/completion plans but still valuable for debugging cache-related issues.

## Plans to Migrate

### Cache/Writeback Plans
1. **DownloadCacheWritebackPlan** (DOWN_AND_UP/down_and_up.py)
   - Used in: Video cache persistence
   - Category: ACQUISITION (cache is part of acquisition)
   - Evidence value: Cache write decisions, skip reasons

2. **UploadCacheWritebackPlan** (DOWN_AND_UP/down_and_up.py)
   - Used in: Upload result caching
   - Category: DELIVERY (cache of delivery result)
   - Evidence value: Cache save success/failure

3. **AudioCacheReplayPlan** (DOWN_AND_UP/down_and_audio.py)
   - Used in: Audio cache hit replay
   - Category: ACQUISITION (replaying acquisition)
   - Evidence value: Cache hit, replay status

4. **AudioSingleCacheReplayPlan** (DOWN_AND_UP/down_and_audio.py)
   - Used in: Single audio cache replay
   - Category: ACQUISITION
   - Evidence value: Single item cache replay

### Cleanup Plans
5. **DownloadCleanupPlan** (DOWN_AND_UP/down_and_up.py)
   - Used in: Post-download cleanup
   - Category: COMPLETION (cleanup is finalization)
   - Evidence value: Cleanup actions, file deletions

6. **AudioCleanupPlan** (DOWN_AND_UP/down_and_audio.py)
   - Used in: Audio post-processing cleanup
   - Category: COMPLETION
   - Evidence value: Audio file cleanup

## Implementation Pattern

Cache plans have simpler signatures than terminal plans:

```python
@dataclass(frozen=True)
class CacheWritebackPlan:
    mode: str
    should_save: bool
    # ... other fields

def _execute_cache_writeback_plan_with_evidence(
    plan: CacheWritebackPlan,
    task_context: RuntimeTask | None,
) -> tuple[bool, RuntimeTask]:
    """Returns (success, updated_task)."""
    def _executor(p: CacheWritebackPlan) -> bool:
        return _execute_cache_writeback_plan_core(p)
    
    if task_context is None:
        return _executor(plan), task_context
    
    new_task, result = execute_plan(
        task_context,
        plan,
        _executor,
        category=PlanCategory.ACQUISITION,  # or DELIVERY
        executor_name="_execute_cache_writeback_plan",
    )
    return result, new_task
```

## Category Assignment

| Plan | Category | Rationale |
|------|----------|-----------|
| DownloadCacheWritebackPlan | ACQUISITION | Cache is acquisition optimization |
| UploadCacheWritebackPlan | DELIVERY | Cache of delivery result |
| AudioCacheReplayPlan | ACQUISITION | Replay is acquisition shortcut |
| AudioSingleCacheReplayPlan | ACQUISITION | Single item replay |
| DownloadCleanupPlan | COMPLETION | Cleanup is finalization |
| AudioCleanupPlan | COMPLETION | Cleanup is finalization |

## Evidence Value

Cache/cleanup evidence helps debug:
- Cache misses that should have been hits
- Cache corruption scenarios
- Disk space issues (cleanup failures)
- Orphaned temp files

## Lower Priority Rationale

These plans are lower priority because:
1. They don't affect core user-visible outcomes
2. Failures here are often recoverable (cache miss just means re-download)
3. Evidence is more useful for operational debugging than user issue resolution

## Testing

- Test cache hit/miss scenarios
- Verify cleanup evidence on disk full errors
- Test cache write failures

## Acceptance Criteria

- [ ] All 6 plans migrated
- [ ] Cache evidence accumulated in acquisition_attempts
- [ ] Cleanup evidence in artifact_refs
- [ ] All tests passing

## Dependencies

- Task: migrate-terminal-completion-plans.md
- Task: migrate-recovery-routing-plans.md (optional, can proceed in parallel)
