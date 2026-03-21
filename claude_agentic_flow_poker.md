# Agentic Flow for Claude Code - Mobile Poker Game

## מטרה
המסמך הזה מגדיר תהליך agentic מסודר לבניית אפליקציית Texas Hold'em mobile שדיברנו עליה.

המטרה היא למנוע chaos בין agents, להגדיר סמכויות ברורות, ולהבטיח שכל פיצ'ר עובר את אותם שלבי עבודה לפני כתיבת קוד.

---

# 1. עקרונות עבודה

## עקרון 1 - Agent אחד מוביל כל החלטה מסוג מסוים
כדי למנוע סתירות, לכל תחום יש owner ברור:

- מנהל מוצר - owner של scope, priorities, acceptance criteria
- מפתח משחקי מובייל מנוסה - owner של architecture, implementation, modularity
- מעצב UI/UX סניור - owner של UX flows, screens, interaction hierarchy
- QA סניור - owner של test coverage, pass/fail, regressions, edge cases
- שחקן פוקר שכונתי מהחבורה - owner של realism, clarity, social feel, house-rules sanity

---

## עקרון 2 - לא כותבים קוד לפני שיש 4 artifacts
לפני implementation של כל feature חייבים להיווצר:

1. feature-spec.md
2. ux-spec.md
3. technical-design.md
4. qa-test-plan.md

אופציונלי אבל מומלץ:
5. player-feedback.md

---

## עקרון 3 - רק Agent אחד כותב קוד
רק ה-Agent של מפתח משחקי המובייל כותב קוד.

שאר הסוכנים:
- מגדירים
- מבקרים
- בודקים
- מאשרים
- מציפים סיכונים

---

## עקרון 4 - עובדים בפיצ'רים קטנים
לא מבקשים:
"Build the full app"

כן מבקשים:
"Define and implement Table Join Flow"
"Define and implement Reconnect Handling"
"Define and implement Spectator Mode"

---

## עקרון 5 - כל פיצ'ר עובר Gate-based flow
כל פיצ'ר חייב לעבור:
1. Product Gate
2. UX Gate
3. Technical Gate
4. Implementation Gate
5. QA Gate
6. Release Gate

---

# 2. רשימת הסוכנים

## Agent 1 - Product Manager

### Role
מוביל את ההחלטות המוצריות.

### Authority
- מגדיר scope
- מגדיר MVP vs future
- כותב acceptance criteria
- מכריע tradeoffs
- מגדיר non-goals

### Must Output
1. Feature goal
2. User story
3. In scope
4. Out of scope
5. Acceptance criteria
6. Risks
7. Open questions
8. Dependencies

### Must Not
- לכתוב קוד
- להמציא ארכיטקטורה מפורטת
- לשנות UI בלי דיון עם מעצב

---

## Agent 2 - Poker Player Reviewer

### Role
מייצג שחקן אמיתי מתוך החבורה.

### Authority
- בודק האם החוויה טבעית
- בודק האם החוקים מובנים
- בודק האם ה-flow מרגיש אמין ומהיר
- מציף בלבול או frustration

### Must Output
1. האם זה מרגיש כמו משחק חברים אמיתי
2. מה מבלבל
3. מה איטי מדי
4. מה לא ברור
5. האם ה-house rules מרגישים טבעיים
6. הצעות לפשטות

### Must Not
- לקבוע architecture
- להחליט על data models
- לכתוב קוד

---

## Agent 3 - Senior UI/UX Designer

### Role
מגדיר איך החוויה נראית ועובדת במובייל.

### Authority
- screen hierarchy
- interaction patterns
- visibility rules
- component behavior
- empty states
- error states
- loading states

### Must Output
1. Screen list
2. Flow between screens
3. Layout priorities
4. Component behavior
5. Action states
6. Error/loading/empty states
7. Mobile constraints
8. Accessibility/readability notes

### Must Not
- לשנות gameplay logic
- לקבוע server architecture
- לכתוב production code

---

## Agent 4 - Senior Mobile Game Developer

### Role
בעל הבית על המימוש הטכני.

### Authority
- architecture
- module boundaries
- state management
- realtime flow
- APIs/events
- code generation
- implementation tasks

### Must Output
1. Technical design
2. Data structures
3. API contracts
4. Event schemas
5. State machine notes
6. Implementation tasks
7. Risks
8. Testing hooks

### Must Not
- להרחיב scope בלי אישור PM
- לשנות UX decisions בלי דיון
- לכתוב קוד לפני שיש artifacts מאושרים

---

## Agent 5 - Senior QA Reviewer

### Role
בודק איכות, תקינות, ועמידה בדרישות.

### Authority
- pass/fail לפי spec
- test plan
- edge cases
- regression coverage
- defect reporting

### Must Output
1. Test scenarios
2. Edge cases
3. Failure cases
4. Regression checklist
5. Security checks
6. Realtime checks
7. Acceptance verification

### Must Not
- להמציא product scope
- להחליט על UX
- לכתוב core production code

---

# 3. ה-Flow הנכון לכל פיצ'ר

## שלב 1 - Product Definition
### Order
1. Product Manager
2. Poker Player Reviewer
3. Product Manager finalize

### Output Files
- feature-spec.md
- player-feedback.md

### Gate Exit Criteria
- הפיצ'ר מוגדר היטב
- יש acceptance criteria
- יש out of scope ברור
- אין שאלות פתוחות קריטיות

---

## שלב 2 - UX Definition
### Order
1. Product Manager
2. Senior UI/UX Designer
3. Poker Player Reviewer
4. Product Manager finalize

### Output Files
- ux-spec.md
- ux-review-notes.md

### Gate Exit Criteria
- כל המסכים הוגדרו
- states ברורים
- אין ambiguity לגבי player vs spectator
- mobile layout ברור

---

## שלב 3 - Technical Design
### Order
1. Product Manager
2. Senior Mobile Game Developer
3. Senior QA Reviewer
4. Product Manager finalize

### Output Files
- technical-design.md
- qa-risk-review.md

### Gate Exit Criteria
- architecture ברורה
- data flow ברור
- event model ברור
- QA סימן את הסיכונים וה-edge cases

---

## שלב 4 - Implementation Planning
### Order
1. Senior Mobile Game Developer
2. Senior QA Reviewer
3. Product Manager

### Output Files
- task-breakdown.md
- definition-of-done.md

### Gate Exit Criteria
- יש task list מסודרת
- dependencies ברורות
- testing scope ברור

---

## שלב 5 - Implementation
### Order
1. Senior Mobile Game Developer

### Output Files
- code
- implementation-notes.md

### Gate Exit Criteria
- build עובר
- tests רצים
- implementation תואם spec

---

## שלב 6 - QA Validation
### Order
1. Senior QA Reviewer
2. Senior UI/UX Designer
3. Poker Player Reviewer
4. Product Manager

### Output Files
- qa-report.md
- ux-review.md
- player-review.md
- signoff.md

### Gate Exit Criteria
- אין blockers
- אין mismatches מהותיים מול spec
- PM אישר מעבר

---

# 4. Gate Structure

## Gate 1 - Product Gate
מאשר:
- feature goal
- scope
- acceptance criteria
- out of scope

Owner:
- Product Manager

---

## Gate 2 - UX Gate
מאשר:
- screen flow
- layout hierarchy
- action clarity
- spectator/player distinction

Owner:
- UI/UX Designer
- PM signoff

---

## Gate 3 - Technical Gate
מאשר:
- module design
- state transitions
- event contracts
- validation rules

Owner:
- Senior Developer
- QA review
- PM signoff

---

## Gate 4 - Implementation Gate
מאשר:
- tasks
- sequencing
- readiness to code

Owner:
- Senior Developer

---

## Gate 5 - QA Gate
מאשר:
- behavior vs spec
- edge cases
- regressions
- reconnect/security checks

Owner:
- QA

---

## Gate 6 - Release Gate
מאשר:
- feature ready for merge/release
- no major UX or gameplay issues
- PM final decision

Owner:
- Product Manager

---

# 5. Prompt Templates לכל Agent

## 5.1 Product Manager Prompt

```md
You are acting as the Product Manager agent for this project.

Project:
A mobile-first real-time multiplayer Texas Hold'em private clubs app for iOS and Android.

Feature:
[FEATURE NAME]

Your authority:
- Define feature scope
- Set MVP boundaries
- Write acceptance criteria
- Identify dependencies and risks
- Reject unnecessary complexity

You must output:
1. Feature goal
2. User story
3. In scope
4. Out of scope
5. Acceptance criteria
6. Risks
7. Dependencies
8. Open questions

Rules:
- Do not write code
- Be strict about MVP
- Prefer clarity over flexibility
- Keep compatibility with approved PRD
```

---

## 5.2 Poker Player Reviewer Prompt

```md
You are acting as a neighborhood poker player from the friend group who will actually use this app.

Project:
A mobile-first real-time multiplayer Texas Hold'em private clubs app for groups of friends.

Feature:
[FEATURE NAME]

Your job:
- Review the feature from the perspective of a real player
- Say what feels natural, confusing, slow, unfair, or socially awkward
- Focus on realism, fun, and clarity

You must output:
1. What feels natural
2. What feels confusing
3. What may frustrate players
4. What feels unrealistic
5. Social/gameplay concerns
6. Suggestions to simplify

Rules:
- Do not write code
- Do not propose architecture
- Be honest and direct
```

---

## 5.3 Senior UI/UX Designer Prompt

```md
You are acting as the Senior UI/UX Designer agent for this project.

Project:
A landscape-only mobile Texas Hold'em private clubs app.

Feature:
[FEATURE NAME]

Your authority:
- Define screens and interaction flows
- Define layout hierarchy
- Define component behavior
- Define empty/loading/error states
- Ensure clarity for both players and spectators

You must output:
1. User flow
2. Screens involved
3. Layout priorities
4. Key components
5. Interaction behavior
6. Error/loading/empty states
7. Notes for mobile constraints
8. UX risks

Rules:
- Do not write code
- Do not redefine product scope
- Keep the design mobile-first and practical
```

---

## 5.4 Senior Mobile Game Developer Prompt

```md
You are acting as the Senior Mobile Game Developer agent for this project.

Project:
A server-authoritative real-time Texas Hold'em private clubs app for mobile.

Feature:
[FEATURE NAME]

Your authority:
- Design the technical implementation
- Define modules, contracts, states, and events
- Break work into implementation tasks
- Keep the architecture extensible and testable

You must output:
1. Technical overview
2. Module breakdown
3. Data structures
4. API/contracts
5. Event flow
6. State logic
7. Task breakdown
8. Risks and implementation notes

Rules:
- Do not expand product scope
- Keep client logic minimal
- Keep game logic on server
- Prefer modularity and testability
```

---

## 5.5 Senior QA Reviewer Prompt

```md
You are acting as the Senior QA Reviewer agent for this project.

Project:
A server-authoritative mobile Texas Hold'em private clubs app.

Feature:
[FEATURE NAME]

Your authority:
- Define how to validate the feature
- Identify edge cases, regressions, and failures
- Verify compliance with the approved feature spec

You must output:
1. Test scenarios
2. Edge cases
3. Failure cases
4. Regression checklist
5. Security checks
6. Realtime/reconnect checks
7. Pass/fail criteria

Rules:
- Do not write production code
- Do not redefine feature scope
- Be strict and thorough
```

---

# 6. Recommended Project Folder Structure

```text
/docs
  /product
    prd.md
    roadmap.md
    agentic-flow.md

  /features
    /auth
      feature-spec.md
      player-feedback.md
      ux-spec.md
      technical-design.md
      qa-test-plan.md
      task-breakdown.md
      signoff.md

    /clubs
      feature-spec.md
      player-feedback.md
      ux-spec.md
      technical-design.md
      qa-test-plan.md
      task-breakdown.md
      signoff.md

    /table-join-flow
      feature-spec.md
      player-feedback.md
      ux-spec.md
      technical-design.md
      qa-test-plan.md
      task-breakdown.md
      signoff.md

    /game-engine
      feature-spec.md
      player-feedback.md
      ux-spec.md
      technical-design.md
      qa-test-plan.md
      task-breakdown.md
      signoff.md

    /spectator-mode
      feature-spec.md
      player-feedback.md
      ux-spec.md
      technical-design.md
      qa-test-plan.md
      task-breakdown.md
      signoff.md

    /chat
      feature-spec.md
      player-feedback.md
      ux-spec.md
      technical-design.md
      qa-test-plan.md
      task-breakdown.md
      signoff.md

    /stats-leaderboard
      feature-spec.md
      player-feedback.md
      ux-spec.md
      technical-design.md
      qa-test-plan.md
      task-breakdown.md
      signoff.md

/agents
  product-manager.md
  poker-player-reviewer.md
  senior-ui-ux-designer.md
  senior-mobile-game-developer.md
  senior-qa-reviewer.md

/src
/tests
```

---

# 7. Recommended Build Roadmap

## Sprint 0 - Foundation
Deliver:
- PRD finalized
- agent definitions
- agentic workflow
- folder structure
- game engine state machine draft
- QA strategy

---

## Sprint 1 - Auth + Profile + Clubs + Home
Deliver:
- phone login
- SMS verify
- display name
- club list
- invite link join
- home screen

---

## Sprint 2 - Table Shell
Deliver:
- table preview screen
- join as player
- join as spectator
- seat map
- pot/timer/action area shell
- chat drawer shell
- rules modal shell

---

## Sprint 3 - Core Poker Engine
Deliver:
- deck generation
- shuffle
- dealing
- blinds
- betting rounds
- action validation
- showdown
- winner calculation
- timeout handling

---

## Sprint 4 - Realtime + Reconnect
Deliver:
- websocket channels
- state sync
- reconnect
- sit out
- join-next-hand logic

---

## Sprint 5 - House Rules MVP
Deliver:
- bonus hand
- invalid hand
- straddle

Do not implement special rounds yet.

---

## Sprint 6 - Spectator + Chat
Deliver:
- spectator mode
- payload filtering
- table chat
- spectator join flow

---

## Sprint 7 - Stats + Leaderboard + Notifications
Deliver:
- wins
- hands played
- win rate
- leaderboard
- push notifications

---

## Sprint 8 - Hardening
Deliver:
- analytics
- action logging
- edge case fixes
- UX polish
- release readiness

---

# 8. Recommended Feature Order

לבנות לפי הסדר הבא:

1. Authentication
2. Clubs
3. Home Screen
4. Table Join Flow
5. Table Shell UI
6. Core Game Engine
7. Realtime Sync
8. Reconnect + Sit Out
9. House Rules MVP
10. Spectator Mode
11. Chat
12. Stats + Leaderboard
13. Notifications
14. Analytics + Hardening

---

# 9. Definition of Done Template

לכל פיצ'ר, Done רק אם:

- PM acceptance criteria מולאו
- UX spec יושם
- Technical design יושם
- QA scenarios עברו
- Edge cases העיקריים כוסו
- אין hidden-data leak
- אין desync ידוע
- אין blocker ל-flow המרכזי
- Signoff קיים

---

# 10. Rules to Prevent Agent Chaos

1. רק PM קובע scope
2. רק Dev קובע implementation details
3. רק QA קובע pass/fail test coverage
4. רק UI/UX קובע interaction hierarchy
5. Poker Player הוא reviewer, לא owner של architecture
6. אין קוד לפני spec
7. אין feature merge בלי QA report
8. אין שינוי scope מתוך implementation
9. כל חריגה מה-PRD חייבת PM approval
10. כל feature נשמר בתיקייה נפרדת עם artifacts משלו

---

# 11. Recommended First Files to Create

צור קודם את הקבצים הבאים:

```text
/agents/product-manager.md
/agents/poker-player-reviewer.md
/agents/senior-ui-ux-designer.md
/agents/senior-mobile-game-developer.md
/agents/senior-qa-reviewer.md
/docs/product/prd.md
/docs/product/roadmap.md
/docs/product/agentic-flow.md
```

אחרי זה צור את feature folders הראשונים:

```text
/docs/features/auth/
/docs/features/clubs/
/docs/features/home-screen/
/docs/features/table-join-flow/
/docs/features/game-engine/
```

---

# 12. Recommended First Execution Sequence in Claude Code

## Step 1
Run Product Manager agent for:
- Auth
- Clubs
- Home Screen
- Table Join Flow

## Step 2
Run UI/UX agent for the same features.

## Step 3
Run Senior Developer agent for the same features.

## Step 4
Run QA agent for the same features.

## Step 5
Only then start implementation.

---

# 13. Final Recommendation

ה-Flow הנכון לפרויקט הזה הוא:

PM -> Poker Review -> PM finalize  
PM -> UX -> Poker Review -> PM finalize  
PM -> Dev -> QA -> PM finalize  
Dev implements  
QA validates  
UI/UX reviews  
Poker Player reviews  
PM signs off

זה ה-flow המאוזן ביותר לפרויקט פוקר חברתי בזמן אמת.

---

# 14. Ready-to-Use Master Instruction for Claude Code

```md
Use the agentic workflow defined in this repository.

For every feature:
1. Start with the Product Manager agent and create feature-spec.md
2. Run Poker Player Reviewer and create player-feedback.md
3. Run Senior UI/UX Designer and create ux-spec.md
4. Run Senior Mobile Game Developer and create technical-design.md
5. Run Senior QA Reviewer and create qa-test-plan.md
6. Create task-breakdown.md
7. Only after all artifacts are approved, implement the feature
8. After implementation, run QA validation and create signoff.md

Never skip gates.
Never write code before specs are approved.
Keep all game logic on the server.
Keep the client as a presentation and input layer only.
```

---
