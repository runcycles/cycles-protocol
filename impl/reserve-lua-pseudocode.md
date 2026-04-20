# reserve.lua — 5-Step Evaluation Pseudocode

Reference pseudocode for the **upcoming v0.1.26** reservation evaluation
path (action-kind access control + risk-class quotas + per-kind quotas
layered on top of v0.1.25 budget checks). v0.1.26 is not yet the active
conformance target — see `CONFORMANCE.md`. This document is a forward-
looking implementation aid for servers planning v0.1.26 support.

This is **not** executable Lua — it is a structural guide for implementers
building the atomic evaluation block described in the spec.

The entire block below runs as a single Redis Lua script invocation.
No partial state is visible to other clients between steps.

## Inputs

```
tenant_id        -- resolved from auth
scope            -- canonical scope string
action_kind      -- from Action.kind
risk_class       -- looked up from registry (default: "side_effect")
amount           -- reservation amount
unit             -- USD_MICROCENTS | TOKENS | CREDITS | RISK_POINTS
run_id           -- from Subject.dimensions.run_id (may be nil)
policy           -- highest-priority matching policy (pre-resolved)
observe_mode     -- effective mode: per-request > tenant > ENFORCE
dry_run          -- boolean
idempotency_key  -- from request
now_utc          -- server timestamp
```

## Step 1 — Action Kind Access Control

```lua
-- Hard gate. No counters touched, no budget touched.
if policy.denied_action_kinds and #policy.denied_action_kinds > 0 then
  for _, denied in ipairs(policy.denied_action_kinds) do
    if denied == action_kind then
      return DENY("ACTION_KIND_DENIED", {
        blocked_by_policy = policy.id,
        suggested_fix = "Remove '" .. action_kind .. "' from denied_action_kinds"
      })
    end
  end
end

if policy.allowed_action_kinds and #policy.allowed_action_kinds > 0 then
  local found = false
  for _, allowed in ipairs(policy.allowed_action_kinds) do
    if allowed == action_kind then found = true; break end
  end
  if not found then
    return DENY("ACTION_KIND_NOT_ALLOWED", {
      blocked_by_policy = policy.id,
      suggested_fix = "Add '" .. action_kind .. "' to allowed_action_kinds"
    })
  end
end
```

## Step 2 — Risk-Class Quotas

```lua
for _, rq in ipairs(policy.risk_class_quotas or {}) do
  if rq.risk_class == risk_class then
    local bucket = derive_bucket(rq.window, now_utc, run_id)
    local counter_key = "quota:" .. tenant_id .. ":" .. scope
                        .. ":__risk__:" .. rq.risk_class
                        .. ":" .. rq.window .. ":" .. bucket

    local used = tonumber(redis.call("GET", counter_key) or "0")

    if used >= rq.max_calls then
      return DENY("ACTION_QUOTA_EXCEEDED", {
        quota_violation = {
          action_kind  = action_kind,  -- triggering kind
          risk_class   = rq.risk_class,
          window       = rq.window,
          window_key   = bucket,
          used         = used,
          limit        = rq.max_calls,
          scope        = scope,
          policy_id    = policy.id
        }
      })
    end

    -- Stage increment (applied in Step 5 if ALLOW)
    stage_increment(counter_key, rq.window, rq.per_run_counter_ttl_ms,
                    rq.threshold_pct, rq.max_calls, used)
  end
end
```

## Step 3 — Per-Kind Action Quotas

```lua
for _, aq in ipairs(policy.action_quotas or {}) do
  if aq.action_kind == action_kind then
    -- Apply host/domain/resource allowlists if present
    if not matches_policy_key_filters(aq, request.policy_keys) then
      goto continue_aq
    end

    local bucket = derive_bucket(aq.window, now_utc, run_id)
    local counter_key = "quota:" .. tenant_id .. ":" .. scope
                        .. ":" .. aq.action_kind
                        .. ":" .. aq.window .. ":" .. bucket

    local used = tonumber(redis.call("GET", counter_key) or "0")

    if used >= aq.max_calls then
      return DENY("ACTION_QUOTA_EXCEEDED", {
        quota_violation = {
          action_kind = aq.action_kind,
          window      = aq.window,
          window_key  = bucket,
          used        = used,
          limit       = aq.max_calls,
          scope       = scope,
          policy_id   = policy.id
        }
      })
    end

    stage_increment(counter_key, aq.window, aq.per_run_counter_ttl_ms,
                    aq.threshold_pct, aq.max_calls, used)

    ::continue_aq::
  end
end
```

## Step 4 — Budget Balance Check

```lua
local balance_key = "balance:" .. tenant_id .. ":" .. scope .. ":" .. unit
local remaining = tonumber(redis.call("GET", balance_key) or "0")

if remaining < amount then
  -- Check overdraft policy (REJECT / ALLOW_IF_AVAILABLE / ALLOW_WITH_OVERDRAFT)
  local overage_policy = resolve_overage_policy(policy, tenant, budget)

  if overage_policy == "REJECT" then
    return DENY("BUDGET_EXCEEDED", {
      blocked_by_scope = scope,
      budget_remaining = remaining
    })
  elseif overage_policy == "ALLOW_IF_AVAILABLE" then
    if remaining <= 0 then
      return DENY("BUDGET_EXCEEDED", {
        blocked_by_scope = scope,
        budget_remaining = remaining
      })
    end
    -- Cap amount to remaining
    amount = remaining
  elseif overage_policy == "ALLOW_WITH_OVERDRAFT" then
    local debt = amount - remaining
    local overdraft_limit = get_overdraft_limit(budget)
    local existing_debt = get_existing_debt(budget)
    if existing_debt + debt > overdraft_limit then
      return DENY("OVERDRAFT_LIMIT_EXCEEDED", {
        blocked_by_scope = scope,
        budget_remaining = remaining
      })
    end
  end
end

-- Also check: BUDGET_FROZEN, BUDGET_CLOSED, DEBT_OUTSTANDING
```

## Step 5 — Atomic Commit (on ALLOW)

```lua
if observe_mode == "OBSERVE" or dry_run then
  -- No mutations. Return evaluation result.
  -- Events handled post-Lua by the application layer.
  return ALLOW_DRY(decision, affected_scopes)
end

-- === ATOMIC MUTATIONS START ===

-- Decrement budget balance
redis.call("DECRBY", balance_key, amount)

-- Apply all staged counter increments
for _, staged in ipairs(staged_increments) do
  local new_val = redis.call("INCR", staged.counter_key)

  -- Set TTL for cleanup (does NOT define window boundary)
  if staged.window == "per_run" then
    redis.call("PEXPIRE", staged.counter_key, staged.per_run_counter_ttl_ms)
  elseif staged.window == "per_minute_tumbling" then
    redis.call("EXPIRE", staged.counter_key, 120)
  elseif staged.window == "per_hour_tumbling" then
    redis.call("EXPIRE", staged.counter_key, 3660)
  else -- per_day_tumbling, per_tenant_per_day
    redis.call("EXPIRE", staged.counter_key, 90000)
  end

  -- Check threshold crossing
  if staged.threshold_pct then
    local prev_ratio = staged.used / staged.max_calls
    local new_ratio = new_val / staged.max_calls
    if prev_ratio < staged.threshold_pct and new_ratio >= staged.threshold_pct then
      emit_threshold_event(staged)  -- handled post-Lua
    end
  end
end

-- Create reservation record with TTL
local reservation_id = generate_id()
-- ... store reservation state ...

return ALLOW(reservation_id, expires_at_ms, affected_scopes)
```

## Helper: derive_bucket

```lua
function derive_bucket(window, now_utc, run_id)
  if window == "per_run" then
    return run_id  -- REQUIRED; caller validated non-nil
  elseif window == "per_minute_tumbling" then
    return os.date("!%Y-%m-%dT%H:%M", now_utc)   -- "2026-04-09T14:32"
  elseif window == "per_hour_tumbling" then
    return os.date("!%Y-%m-%dT%H", now_utc)       -- "2026-04-09T14"
  elseif window == "per_day_tumbling" then
    return os.date("!%Y-%m-%d", now_utc)           -- "2026-04-09"
  elseif window == "per_tenant_per_day" then
    return os.date("!%Y-%m-%d", now_utc)           -- scope normalized to tenant root
  end
end
```

## Post-Lua Event Emission (Application Layer)

Event emission happens **outside** the Lua script, after the atomic block returns:

```
if observe_mode == "OBSERVE" then
  if decision == DENY then
    emit("reservation.observed_denied", EventDataObservedDenied)
  else
    emit("reservation.observed_allowed", EventDataObservedAllowed)  -- subject to sampling
  end
end

for each threshold_crossing in lua_result.threshold_crossings do
  emit("quota.threshold_approaching", EventDataQuotaThresholdApproaching)
end
```

## Release / Expiry Counter Decrement

When a `per_run` reservation is released or expires without commit,
the application layer must decrement **both** counter types:

```lua
-- Called on release or expiry sweep
function decrement_per_run_counters(reservation)
  -- Decrement per-kind counter
  if reservation.action_quota_counter_key then
    redis.call("DECR", reservation.action_quota_counter_key)
  end
  -- Decrement risk-class counter (same lifecycle)
  if reservation.risk_class_counter_key then
    redis.call("DECR", reservation.risk_class_counter_key)
  end
end
```

Committed reservations do **not** decrement counters — committed calls permanently count.
