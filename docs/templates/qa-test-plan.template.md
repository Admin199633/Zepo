# QA Test Plan — [Feature Name]

> Owner: Senior QA Reviewer
> Input: feature-spec.md, technical-design.md
> Gate: QA Gate (Gate 5)

---

## Test Scenarios
_Happy path and primary alternate paths._

| ID | Scenario | Steps | Expected Result |
|----|----------|-------|----------------|
| T01 |          |       |                |
| T02 |          |       |                |

---

## Edge Cases
_Boundary conditions, timing issues, unusual inputs._

| ID | Case | Expected Behavior |
|----|------|------------------|
| E01 |      |                  |
| E02 |      |                  |

---

## Failure Cases
_What should happen when things go wrong._

| ID | Failure | Expected Response |
|----|---------|-----------------|
| F01 |         |                 |
| F02 |         |                 |

---

## Regression Checklist
_Existing features that must still work after this change._

- [ ] Game engine state machine unaffected
- [ ] Reconnect still restores correct state
- [ ] Spectators still receive no hidden card data
- [ ] Chips are conserved (no chips created or destroyed)
- [ ] Turn timer still fires correctly
- [ ]

---

## Security Checks
- [ ] Server validates all input — client data is never trusted
- [ ] Hidden cards not leaked to opponents or spectators before showdown
- [ ] Admin actions are permission-checked
- [ ]

---

## Realtime and Reconnect Checks
- [ ] Player can reconnect mid-hand within 60 seconds and receive full state
- [ ] Disconnect timer fires correctly after 60 seconds
- [ ] No events are lost during a reconnect window
- [ ] Spectator receives filtered state (masked cards)
- [ ]

---

## Pass/Fail Criteria
| Criterion | Pass Condition |
|-----------|--------------|
|           |              |

---

## QA Sign-off
- [ ] All scenarios passed
- [ ] No blocker defects open
- [ ] Regression clean
- Date:
- Defects logged:
