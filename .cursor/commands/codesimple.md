---
name: code-simplification
description: Simplifies and refactors code while preserving behavior. Use when the user asks to simplify code, reduce duplication, lower nesting, clean up conditionals, or improve readability and maintainability.
---

# Code Simplification

## Goal

Produce simpler, clearer code without changing behavior.

## Working Rules

1. Keep behavior unchanged unless user explicitly allows behavior changes.
2. Prefer the smallest safe change first.
3. Prioritize readability over cleverness.
4. Preserve project conventions (naming, style, structure).
5. After edits, run or suggest verification steps.

## Simplification Checklist

- Remove duplicated logic (DRY).
- Replace deep nesting with guard clauses / early return.
- Split long functions into small focused functions.
- Reduce long if-elif chains with mapping/dispatch when suitable.
- Remove dead code, unused variables/imports, debug leftovers.
- Replace magic numbers/strings with named constants when meaningful.
- Keep naming concise and clear.

## Decision Heuristics

### 1) Duplicate Code

If two or more blocks do the same thing with minor differences:
- Extract helper function.
- Pass differences as parameters.

### 2) Nested Conditionals

If nesting depth is > 2:
- Handle invalid/boundary cases early with `return` / `continue`.
- Keep happy path flat.

### 3) Long Functions

If function does multiple responsibilities:
- Split by responsibility.
- Use intention-revealing function names.

### 4) Conditional Explosion

If many branches map key -> action:
- Use dictionary/dispatch table where readable.
- Keep explicit `default` handling.

### 5) Temporary Variables

If variable is used only once and does not improve clarity:
- Inline it.
- Keep only variables that improve comprehension.

## Refactor Pattern Library

### Pattern A: Guard Clauses

Before:
```python
if data:
    if data.valid:
        if data.items:
            return process(data)
return None
```

After:
```python
if not data or not data.valid or not data.items:
    return None
return process(data)
```

### Pattern B: Extract Function

Before:
```python
if user.age >= 18 and user.verified:
    allow(user)
if admin.age >= 18 and admin.verified:
    allow(admin)
```

After:
```python
def can_access(person):
    return person.age >= 18 and person.verified

if can_access(user):
    allow(user)
if can_access(admin):
    allow(admin)
```

### Pattern C: Mapping Instead of if-elif

Before:
```python
if status == "pending":
    action = "wait"
elif status == "approved":
    action = "run"
elif status == "rejected":
    action = "notify"
else:
    action = "unknown"
```

After:
```python
action = {
    "pending": "wait",
    "approved": "run",
    "rejected": "notify",
}.get(status, "unknown")
```

## Output Format (when user asks for simplification)

1. **What changed**: concise bullets.
2. **Why**: one line per change.
3. **Risk check**: note any potential behavior-sensitive points.
4. **Verification**: tests/lints/commands to run.

## Constraints

- Do not introduce broad architectural rewrites unless requested.
- Do not rename public APIs unless requested.
- Do not silently change error handling semantics.
- If requirements are ambiguous, state assumptions clearly.

## Trigger Examples

- "帮我简化这段代码"
- "重构这个函数，太绕了"
- "去掉重复逻辑"
- "降低这段代码的嵌套层级"
- "优化可读性，不改功能"