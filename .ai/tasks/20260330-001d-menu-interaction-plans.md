# Task: Migrate Menu Interaction Plans to TaskPlanExecutor

## Metadata
- **Status**: ✅ Complete
- **Priority**: LOWEST
- **Created**: 2026-03-30
- **Completed**: 2026-03-30
- **Plans**: 14 (1 migrated, 13 skipped)
- **Category**: PDA Migration

## Background
Menu interaction plans handle UI state and callback routing. These have lower evidence value because they represent user interactions rather than execution decisions.

## Migration Summary

### Migrated Plans

#### 1. GalleryFallbackTransitionPlan (DOWN_AND_UP/always_ask_menu.py) ✅
- **Category**: ROUTING
- **Evidence value**: Gallery fallback decisions have execution impact
- **Implementation**:
  - Added `_execute_gallery_fallback_transition_plan_core()` - Core execution logic
  - Added `_execute_gallery_fallback_transition_plan_with_evidence()` - Evidence-aware wrapper
  - Updated `fallback_gallery_dl_callback_logic()` to use evidence-aware executor
  - Added import for `execute_routing_plan` from TaskPlanExecutor

### Skipped Plans (13 AlwaysAsk Menu Plans)

The following plans were **explicitly skipped** based on the rationale below:

| Plan | Location | Skip Rationale |
|------|----------|----------------|
| AlwaysAskSubsMenuPlan | always_ask_menu.py | User decision, transient state |
| AlwaysAskDubsMenuPlan | always_ask_menu.py | User decision, transient state |
| AlwaysAskFilterUpdatePlan | always_ask_menu.py | UI state update, no execution impact |
| AlwaysAskQualitySelectionPlan | always_ask_menu.py | User decision, captured in branch selection |
| AlwaysAskSpecialActionPlan | always_ask_menu.py | UI navigation, no execution impact |
| AlwaysAskClosePlan | always_ask_menu.py | UI cleanup, no execution impact |
| AlwaysAskNavigationPlan | always_ask_menu.py | UI pagination, no execution impact |
| AlwaysAskOtherFormatSelectionPlan | always_ask_menu.py | User decision, captured in branch selection |
| AlwaysAskManualQualitySelectionPlan | always_ask_menu.py | User input, captured in format selection |
| QualityMenuRenderPlan | always_ask_menu.py | UI rendering, no execution impact |
| CachedQualitiesMenuPlan | always_ask_menu.py | UI display, no execution impact |
| OtherQualitiesMenuPlan | always_ask_menu.py | UI display, no execution impact |
| TagsCallbackResultPlan | COMMANDS/tag_cmd.py | User interaction, logged separately |

## Skip Rationale

### Why Skip Most Menu Plans?

1. **User decisions, not system decisions**: Menu selections reflect user choice, not system policy. The actual execution decisions are already captured in branch selection results.

2. **Transient state**: Menu state is ephemeral (selection made, menu closed). The resulting action (download, fallback, etc.) is what matters for debugging.

3. **Low debugging value**: User interactions are logged separately in Telegram callback queries. The execution path is determined by branch selection, not menu rendering.

4. **Evidence redundancy**: Quality/format selections are already captured when branch selection results are recorded on the RuntimeTask.

### Why Migrate GalleryFallbackTransitionPlan?

This plan has **execution impact**:
- It triggers a new download flow via gallery-dl
- Creates a new RuntimeTask with branch selection
- Represents a routing decision between yt-dlp and gallery-dl engines
- Important for debugging fallback scenarios

## Implementation Pattern Used

```python
# Core executor extracted for reuse
def _execute_plan_core(*, plan: PlanType, ...) -> dict:
    ...

# Evidence-aware wrapper using TaskPlanExecutor
def _execute_plan_with_evidence(
    *,
    plan: PlanType,
    ...
) -> tuple[dict, RuntimeTask]:
    def _executor(p: PlanType) -> dict:
        return _execute_plan_core(plan=p, ...)
    
    new_task, result = execute_routing_plan(
        task_context,
        plan,
        _executor,
        executor_name="_execute_plan",
    )
    return result, new_task
```

## Evidence Target

GalleryFallbackTransitionPlan evidence goes to `artifact_refs` (ROUTING category).

## Acceptance Criteria

- [x] GalleryFallbackTransitionPlan migrated (highest value)
- [x] Other menu plans explicitly skipped with documented rationale
- [x] All 208 tests passing
- [x] No regression in menu functionality

## Dependencies

- All other migration tasks complete
- TaskPlanExecutor infrastructure available
