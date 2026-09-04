<!-- OPENSPEC:START -->
# OpenSpec Instructions

These instructions are for AI assistants working in this project.

Always open `@/openspec/AGENTS.md` when the request:
- Mentions planning or proposals (words like proposal, spec, change, plan)
- Introduces new capabilities, breaking changes, architecture shifts, or big performance/security work
- Sounds ambiguous and you need the authoritative spec before coding

Use `@/openspec/AGENTS.md` to learn:
- How to create and apply change proposals
- Spec format and conventions
- Project structure and guidelines

Keep this managed block so 'openspec update' can refresh the instructions.

<!-- OPENSPEC:END -->

# Repository Agent Guide

This file supplements the OpenSpec block above with practical commands and
local code conventions observed in this repository.

## Agent Guidance Files (Read When Relevant)

- `openspec/AGENTS.md`: OpenSpec workflow (proposals, tasks, archiving).
- `.specify/memory/constitution.md`: Project principles (MVP-first, testability, robustness).
- `.github/agents/*.md` and `.github/prompts/*.md`: Speckit agent definitions and prompts.
- `docs/VLM_FIRST_ARCHITECTURE.md`: VLM-First architecture overview.
- `docs/PROJECT_STRUCTURE.md`: Repository structure and module layout.

## Installed Skills & Frameworks

### UI/UX Design Intelligence (UI UX Pro Max)
- **Location**: `.opencode/skills/ui-ux-pro-max/`
- **Trigger**: Any UI/UX design request (build, design, create, implement landing page, dashboard, component)
- **Usage**: Automatically activates when requesting UI/UX work
- **Capabilities**:
  - 67 UI styles (Glassmorphism, Minimalism, Brutalism, Dark Mode, AI-Native UI, etc.)
  - 96 color palettes (SaaS, E-commerce, Healthcare, Fintech, Beauty, etc.)
  - 57 font pairings with Google Fonts imports
  - Industry-specific design system generation
  - Responsive design with accessibility (WCAG AA)
- **Example prompts**:
  - "Build a landing page for my SaaS product"
  - "Create a dashboard for healthcare analytics"
  - "Design a portfolio website with dark mode"
  - "Make a mobile app UI for e-commerce"
- **When to use**: Frontend UI/UX implementation, design system creation, responsive layouts
- **DO NOT use for**: Backend logic, API design, database schemas

### Software Development Workflow (Superpowers)
- **Location**: `~/.config/opencode/superpowers/`
- **Trigger**: Complex development tasks requiring structured workflow
- **Usage**: Use `skill` tool to load specific workflows
- **Core Skills**:
  - `superpowers/brainstorming` - Interactive design refinement (Socratic method)
  - `superpowers/writing-plans` - Create detailed implementation plans
  - `superpowers/executing-plans` - Execute plans in batches with checkpoints
  - `superpowers/test-driven-development` - RED-GREEN-REFACTOR cycle
  - `superpowers/systematic-debugging` - 4-phase root cause analysis
  - `superpowers/using-git-worktrees` - Parallel development branches
  - `superpowers/requesting-code-review` - Pre-review checklist
  - `superpowers/subagent-driven-development` - Fast iteration with two-stage review
- **Example usage**:
  ```
  # Load brainstorming skill for design discussions
  use skill tool to load superpowers/brainstorming
  
  # Load TDD skill for test-first development
  use skill tool to load superpowers/test-driven-development
  ```
- **When to use**:
  - Starting a new feature (brainstorming)
  - Need structured implementation plan (writing-plans)
  - Complex refactoring or bug fixing (systematic-debugging)
  - Test-first development (test-driven-development)
- **Philosophy**: Test-Driven Development, Systematic over ad-hoc, Complexity reduction, Evidence over claims

### Skills Registry Management (Context7)
- **CLI**: `ctx7` (installed globally)
- **Purpose**: Search, install, and manage additional skills from Context7 registry
- **Common commands**:
  ```bash
  # Search for skills
  ctx7 skills search pdf
  ctx7 skills search react testing
  
  # Install skills for OpenCode
  ctx7 skills install /anthropics/skills pdf --opencode
  
  # List installed skills
  ctx7 skills list --opencode
  
  # Get skill information
  ctx7 skills info /anthropics/skills
  
  # Remove a skill
  ctx7 skills remove pdf --opencode
  ```
- **When to use**: Need specialized skills not covered by UI UX Pro Max or Superpowers (e.g., PDF processing, commit message generation, code review templates)

## AI Assistant Skill Invocation Rules

### When to Invoke Skills (MANDATORY)

AI assistants MUST follow these rules when processing user requests:

#### 1. UI/UX Design Requests (Auto-invoke UI UX Pro Max)
**Triggers**: build, design, create, implement, make, improve + (landing page, dashboard, component, UI, UX, interface, layout, form, button, navbar, sidebar, modal, card, hero section, footer)

**Action**: Skill auto-activates. AI should:
1. Analyze product type and industry
2. Generate complete design system (style + colors + typography + layout)
3. Provide anti-pattern warnings for the specific industry
4. Generate accessible, responsive code (WCAG AA compliance)

**Example**:
```
User: "Build a landing page for my healthcare startup"
AI: [UI UX Pro Max activates]
     1. Analyzes: Healthcare → Trust & Authority pattern
     2. Recommends: Soft UI + Teal/White palette + Poppins/Inter fonts
     3. Warns: Avoid bright neon colors, dark mode
     4. Generates: Vue 3 + Tailwind code with proper contrast ratios
```

#### 2. Brainstorming & Design Discussions (Manual load Superpowers)
**Triggers**: complex feature, new feature, architecture decision, design discussion, not sure how to, need help planning

**Action**: AI MUST load `superpowers/brainstorming` before proceeding
```
use skill tool to load superpowers/brainstorming
```

**Process**:
1. Socratic questioning to understand true requirements
2. Explore alternative approaches
3. Present design in digestible sections
4. Get user approval before implementation

**Example**:
```
User: "I want to add real-time preview to the note generation system"
AI: use skill tool to load superpowers/brainstorming
    "Let me understand your requirements:
     1. What triggers the preview update? (keystroke / button / auto-save)
     2. Should it preview intermediate results or only final output?
     3. What's the acceptable latency? (< 100ms / < 500ms / < 1s)
     ..."
```

#### 3. Implementation Planning (Manual load Superpowers)
**Triggers**: After brainstorming approval, user says "create plan", "let's implement", "how should we build this"

**Action**: AI MUST load `superpowers/writing-plans`
```
use skill tool to load superpowers/writing-plans
```

**Process**:
1. Break work into 2-5 minute atomic tasks
2. Each task: exact file paths + complete code + verification steps
3. Create trackable TODO list
4. Get user approval before execution

#### 4. Test-Driven Development (Manual load Superpowers)
**Triggers**: User explicitly requests TDD, or plan includes testing requirements

**Action**: AI MUST load `superpowers/test-driven-development`
```
use skill tool to load superpowers/test-driven-development
```

**Enforced Flow**:
1. RED: Write failing test first (must see it fail)
2. GREEN: Write minimal code to pass
3. REFACTOR: Improve while keeping tests green
4. AUTO-DELETE: Any code written before tests

#### 5. Systematic Debugging (Manual load Superpowers)
**Triggers**: bug report, error, crash, memory leak, performance issue, "not working", "failing"

**Action**: AI MUST load `superpowers/systematic-debugging`
```
use skill tool to load superpowers/systematic-debugging
```

**4-Phase Process**:
1. **Evidence Collection**: Logs, error messages, environment info
2. **Isolation**: Create minimal reproducible example
3. **Root Cause Tracing**: Analyze underlying issue (not symptoms)
4. **Verification**: Prove the fix actually works

**Anti-pattern**: Never apply random fixes without understanding root cause

#### 6. Specialized Tasks (Use Context7)
**Triggers**: PDF processing, chart generation, commit message formatting, specific framework patterns not covered above

**Action**: Search and install appropriate skill
```bash
ctx7 skills search <keyword>
ctx7 skills install <skill-path> --opencode
```

### Skill Selection Decision Tree

```
User request received
│
├─ Contains UI/UX keywords (build/design/create + landing page/dashboard/component)?
│  └─ ✅ AUTO-INVOKE: UI UX Pro Max (no manual action needed)
│
├─ New complex feature OR architecture decision OR "not sure how to"?
│  └─ 🔧 MUST LOAD: superpowers/brainstorming
│
├─ User approved design and says "implement" / "create plan"?
│  └─ 🔧 MUST LOAD: superpowers/writing-plans
│
├─ Plan includes testing OR user requests TDD?
│  └─ 🔧 MUST LOAD: superpowers/test-driven-development
│
├─ Bug report OR error OR "not working"?
│  └─ 🔧 MUST LOAD: superpowers/systematic-debugging
│
├─ Need specialized functionality (PDF / charts / specific framework)?
│  └─ 📦 SEARCH: ctx7 skills search <keyword>
│
└─ Simple task (typo fix, small change, documentation)?
   └─ 💬 NO SKILL NEEDED: Direct implementation
```

### Anti-Patterns (FORBIDDEN)

❌ **DO NOT**:
1. Load Superpowers for UI/UX design (use UI UX Pro Max instead)
2. Implement complex features without brainstorming first
3. Write code before writing tests (when TDD is loaded)
4. Apply random bug fixes without systematic debugging
5. Load multiple Superpowers skills simultaneously (one at a time)
6. Skip brainstorming for features with >3 implementation steps

### Skill Loading Syntax (IMPORTANT)

**Correct**:
```
use skill tool to load superpowers/brainstorming
use skill tool to load superpowers/writing-plans
use skill tool to load superpowers/test-driven-development
```

**Incorrect**:
```
load skill superpowers/brainstorming  ❌
@superpowers/brainstorming            ❌
skill:superpowers/brainstorming       ❌
```

### Complete Workflow Example

```
User: "I want to add video chapter auto-detection to the note generation system"

AI Step 1: Load brainstorming skill
  use skill tool to load superpowers/brainstorming
  [Socratic questioning to understand requirements]
  [Present design document in sections]
  [Get user approval]

User: "Looks good, let's implement it"

AI Step 2: Load planning skill
  use skill tool to load superpowers/writing-plans
  [Break into atomic tasks]
  [Create TODO list with verification steps]
  [Get user approval]

User: "Approved, let's start with TDD"

AI Step 3: Load TDD skill
  use skill tool to load superpowers/test-driven-development
  [Write failing test for first task]
  [Verify test fails]
  [Write minimal implementation]
  [Verify test passes]
  [Refactor if needed]

AI Step 4: Request code review
  use skill tool to load superpowers/requesting-code-review
  [Review against plan]
  [Report issues by severity]
  [Get user sign-off before next task]
```

**Full workflow documentation**: See `docs/SKILLS_USAGE_GUIDE.md` for detailed examples and best practices.

## Cursor / Copilot Rules

- No `.cursorrules`, `.cursor/rules/`, or `.github/copilot-instructions.md` found.
- If these are added later, mirror their rules here.

## Build / Run Commands

### Docker (full stack)

- Start all services: `docker compose -f ops/docker/docker-compose.yml up -d`
- Build + start Ollama + backend + frontend: `bash ops/scripts/setup_llm_services.sh`
- Rebuild without cache (Linux): `bash ops/scripts/docker/docker-build.sh`
- Rebuild without cache (Windows): `ops/scripts/docker/docker-build.bat`

### Backend (FastAPI)

- Dev server: `uvicorn source.backend.app.main:app --reload`
- API health check: `curl http://localhost:18000/api/version`

### Frontend (Vue 3 + Vite)

- Dev server: `npm --prefix source/frontend run dev`
- Build: `npm --prefix source/frontend run build`
- Preview: `npm --prefix source/frontend run preview`

## Lint / Format

- No repository-wide formatter or linter is configured.
- Avoid introducing a formatter unless explicitly requested.
- Keep changes minimal and localized; do not reformat unrelated code.
- Legacy docs mention `black` and `mypy`, but they are not configured in this repo.

## Test Commands

### Backend (pytest)

- Run all: `pytest`
- Run single test file: `pytest source/backend/tests/test_cornell_pipeline.py -q`
- Run single test case: `pytest source/backend/tests/test_cornell_pipeline.py -k "test_name" -q`
- `pytest.ini` sets `addopts = -q` and `testpaths = source/backend/tests`

### Frontend (vitest)

- Run all: `npm --prefix source/frontend run test`
- Watch mode: `npm --prefix source/frontend run test:watch`
- UI runner: `npm --prefix source/frontend run test:ui`
- Run single test file: `npm --prefix source/frontend run test -- --runTestsByPath src/utils/markdownRenderer.test.js`

### Docker test profile

- Run backend tests in container: `docker compose -f ops/docker/docker-compose.yml run --rm notegen-tests`

### API automation (PowerShell)

- Automated pipeline test: `powershell -ExecutionPolicy Bypass -File ops/scripts/automation/test-api-automation.ps1`

## Code Style Guidelines

### General

- Follow the style of the file you are editing.
- Prefer small, targeted fixes over refactors during bugfixes.
- Do not introduce new dependencies without a clear need.
- Avoid global side effects unless an entrypoint explicitly requires them.
- Prefer explicit names over abbreviations for public APIs.
- Keep behavior changes localized and documented in the commit or PR description.

### Python (FastAPI backend)

- Indentation: 4 spaces.
- Naming: `snake_case` for functions/variables, `PascalCase` for classes.
- Imports: standard library first, then third-party, then local modules; keep grouping consistent with the file.
- Types: use type hints where already present; prefer `Optional[T]`, `list[T]`, `dict[str, T]`.
- Error handling: use `try/except` with logging; surface API errors via `HTTPException`.
- Logging: use module-level `logger = logging.getLogger(__name__)` and include context.
- Paths: prefer `pathlib.Path` where already in use; avoid mixing styles in one file.
- Configuration: use `source/backend/app/config.yaml` and existing config helpers.

### JavaScript/Vue (frontend)

- Scripts are ES modules (`type: module` in `package.json`).
- Keep existing quote style per file (single quotes are common in `src/`).
- Avoid new global side effects; use composables for shared logic.
- Keep error handling user-friendly (see `source/frontend/src/main.js`).
- For Vue SFCs, follow component structure used in the file (template/script/style order).
- Do not change visual styles unless explicitly requested.

### Tests

- Backend tests live in `source/backend/tests/` (pytest).
- Frontend tests use Vitest (`source/frontend/vitest.config.js`).
- Prefer adding tests alongside existing test modules and naming patterns.

## Repo Structure References

- Backend entrypoint: `source/backend/app/main.py`
- Backend modules: `source/backend/modules/`
- Shared services: `source/backend/modules/services/`
- API routes: `source/backend/modules/api_routes.py` (some endpoints still in `app/main.py`)
- Frontend app: `source/frontend/src/`
- Frontend views: `source/frontend/src/views/`
- Frontend components: `source/frontend/src/components/`
- Frontend composables: `source/frontend/src/composables/`
- Frontend stores: `source/frontend/src/stores/`
- Docker compose: `ops/docker/docker-compose.yml`

## Common Scripts

- System inventory: `python ops/scripts/collect_system_info.py`
- Clean generated notes: `python ops/scripts/clean_notes.py`
- Convert HEIC assets: `python ops/scripts/tools/convert_heic_images.py`
- Verify prompt wiring: `python ops/scripts/verify_prompt_integration.py`

## Runtime Paths (gitignored)

- Outputs/logs: `var/notes/`, `var/output/`, `var/log/`, `var/tmp/`
- External assets/models: `data/` (videos/images/models, external mounts)
- Avoid committing runtime artifacts from `var/` or `data/`.

## Image Note Layout (Required)

Use this structure for image-based notes. Every chapter is a self-contained “image note unit.”

### Chapter Structure

- Chapter title (auto-generated, conceptual; never raw OCR)
- Image note unit:
  1. Image (must be first)
  2. Japanese key outline (original lecture language)
  3. Mother-tongue explanation (user selected language)
  4. Key terms / terminology table
  5. Code or math (if present)
  6. Supplement / extended understanding (optional)

### Rules

- Image must always be the first element of the unit.
- Image title must be inferred and conceptual (not “Slide 3”).
- Japanese outline: bullet list, not prose; fix OCR errors; may restore missing subject/verb.
- Mother-tongue explanation: teaching-style, explain “why” and “where it’s used,” plain language.
- Key terms: only when technical terms exist; fixed 3-column table.
- Code/math: use `$...$` for inline math; add one-line plain-language explanation under formulas.
- Supplement section: optional, but must add real value when present.

### Minimum Viable Unit

A valid image note must include:
- Image
- Japanese outline
- Mother-tongue explanation

## Notes on Docs vs Reality

- `docs/reports/QUICK_REFERENCE.md` mentions `black`/`mypy` commands, but these tools
  are not listed in `requirements.txt` and no config files exist. Treat as legacy.

## Single-Test Examples (Copy/Paste)

- `pytest source/backend/tests/test_api_smoke.py -q`
- `pytest source/backend/tests/test_ollama_provider.py -k "health" -q`
- `npm --prefix source/frontend run test -- --runTestsByPath src/utils/markdownRenderer.test.js`
