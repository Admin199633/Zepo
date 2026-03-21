# Claude Code Master Prompt - Install Agentic Workflow Into Project

You are working inside an existing project repository.

Your job is to take the supplied markdown files and integrate them into the repository so they become the project's working agent system.

## Source Files
Use the provided files exactly as the initial source of truth:
- agents/product-manager.md
- agents/poker-player-reviewer.md
- agents/senior-ui-ux-designer.md
- agents/senior-mobile-game-developer.md
- agents/senior-qa-reviewer.md
- docs/product/agentic-flow.md

## Your Goals
1. Create the required folder structure in the repository.
2. Copy or create these files in the correct locations.
3. Create feature workflow templates so future features follow the same process.
4. Update repository documentation so contributors know how to use the agent system.
5. Do not change the product scope. Do not invent missing gameplay rules. Preserve the architecture principles.

## Required Folder Structure
Create this structure if it does not already exist:

/agents
/docs/product
/docs/features
/docs/templates

Under /docs/features create feature folders only when needed, not all at once.

## Required Files To Create Or Update

### 1. Keep these files
- /agents/product-manager.md
- /agents/poker-player-reviewer.md
- /agents/senior-ui-ux-designer.md
- /agents/senior-mobile-game-developer.md
- /agents/senior-qa-reviewer.md
- /docs/product/agentic-flow.md

### 2. Create these templates
- /docs/templates/feature-spec.template.md
- /docs/templates/player-feedback.template.md
- /docs/templates/ux-spec.template.md
- /docs/templates/technical-design.template.md
- /docs/templates/qa-test-plan.template.md
- /docs/templates/task-breakdown.template.md
- /docs/templates/signoff.template.md

### 3. Create a usage guide
- /docs/product/how-to-use-agents.md

### 4. Update root documentation
If a README exists, update it with a short section called "Agentic Workflow".
If no README exists, create one with:
- project overview placeholder
- repository structure
- short explanation of the agent workflow

## Template Requirements

### feature-spec.template.md
Include sections for:
- Feature name
- Goal
- User story
- In scope
- Out of scope
- Acceptance criteria
- Risks
- Dependencies
- Open questions

### player-feedback.template.md
Include sections for:
- What feels natural
- What is confusing
- Possible frustration points
- Social realism notes
- Simplification suggestions

### ux-spec.template.md
Include sections for:
- User flow
- Screens
- Layout priorities
- Components
- Interaction states
- Empty/loading/error states
- Mobile constraints
- UX risks

### technical-design.template.md
Include sections for:
- Technical overview
- Modules
- Data structures
- APIs and contracts
- Events
- State transitions
- Validation rules
- Risks
- Implementation notes

### qa-test-plan.template.md
Include sections for:
- Test scenarios
- Edge cases
- Failure cases
- Regression checklist
- Security checks
- Realtime and reconnect checks
- Pass/fail criteria

### task-breakdown.template.md
Include sections for:
- Milestones
- Tasks
- Dependencies
- Definition of done

### signoff.template.md
Include sections for:
- PM approval
- UX approval
- QA status
- Developer notes
- Remaining risks
- Final decision

## Usage Guide Requirements
In /docs/product/how-to-use-agents.md explain:
1. The order of agents for every feature
2. What each agent owns
3. Which artifacts must exist before code is written
4. The approval gates
5. The recommended feature implementation order
6. Rules that prevent agent chaos

## Working Rules
- Do not delete existing project files unless absolutely necessary
- Prefer additive changes
- Keep markdown clean and minimal
- Preserve server-authoritative principles
- Keep game logic on server
- Treat spectator hidden-data protection as a hard rule
- Do not implement app code in this task unless needed for documentation wiring only

## Final Output
At the end, provide:
1. A list of files created
2. A list of files updated
3. Any assumptions you had to make
4. Suggested next step: create the first feature package for Auth
