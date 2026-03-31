# Task: Migrate Menu Interaction Plans to TaskPlanExecutor

## Status
Ready for implementation (lowest priority)

## Background
Menu interaction plans handle UI state and callback routing. These have lower evidence value because they represent user interactions rather than execution decisions.

## Plans to Migrate

### Always Ask Menu Plans (DOWN_AND_UP/always_ask_menu.py)
1. **AlwaysAskSubsMenuPlan** - Subtitle selection menu
2. **AlwaysAskDubsMenuPlan** - Dub selection menu
3. **AlwaysAskFilterUpdatePlan** - Filter update handling
4. **AlwaysAskQualitySelectionPlan** - Quality selection
5. **AlwaysAskSpecialActionPlan** - Special action menu
6. **AlwaysAskClosePlan** - Menu close handling
7. **AlwaysAskNavigationPlan** - Menu navigation
8. **AlwaysAskOtherFormatSelectionPlan** - Format selection
9. **AlwaysAskManualQualitySelectionPlan** - Manual quality input
10. **QualityMenuRenderPlan** - Menu rendering
11. **CachedQualitiesMenuPlan** - Cached quality display
12. **OtherQualitiesMenuPlan** - Other quality options

### Gallery Transition
13. **GalleryFallbackTransitionPlan** (DOWN_AND_UP/always_ask_menu.py)
    - Category: ROUTING
    - Evidence value: Gallery fallback decisions

### Tags
14. **TagsCallbackResultPlan** (COMMANDS/tag_cmd.py)
    - Category: ROUTING
    - Evidence value: Tag extraction results

## Low Priority Rationale

Menu plans have limited evidence value:

1. **User decisions, not system decisions**: Menu selections reflect user choice, not system policy
2. **Transient state**: Menu state is ephemeral (selection made, menu closed)
3. **Debugging value**: Low - user interactions are logged separately in Telegram

## Migration Approach (if undertaken)

If migrated, use ROUTING category:

```python
def _execute_menu_plan_with_evidence(
    plan: MenuPlanType,
    task_context: RuntimeTask | None,
) -> tuple[ResultType, RuntimeTask]:
    def _executor(p: MenuPlanType) -> ResultType:
        return _execute_menu_plan_core(p)
    
    if task_context is None:
        return _executor(plan), task_context
    
    new_task, result = execute_routing_plan(
        task_context,
        plan,
        _executor,
        executor_name="_execute_menu_plan",
    )
    return result, new_task
```

## Evidence Target

Menu plan evidence would go to `artifact_refs` (ROUTING category).

## When to Migrate

Consider migrating only if:
1. Debugging complex menu state issues
2. Tracking menu→execution correlation
3. Audit requirements for user selections

## Alternative: Skip Migration

Menu plans may not need migration. Consider:
- Leaving as-is (no evidence recording)
- Using simpler logging instead
- Migrating only GalleryFallbackTransitionPlan (has execution impact)

## Acceptance Criteria (if undertaken)

- [ ] GalleryFallbackTransitionPlan migrated (highest value)
- [ ] Other menu plans migrated OR explicitly skipped
- [ ] Documentation of skip rationale
- [ ] Tests passing

## Dependencies

- All other migration tasks complete
- Decision on whether to migrate or skip
