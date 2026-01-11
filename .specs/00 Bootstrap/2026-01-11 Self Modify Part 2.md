  Based on exploring this codebase, here's my deep analysis:

  Current State

  Yes, the agent CAN modify its own source code - but with important nuances:
  ┌──────────────────────────────────┬───────────┬──────────────────┬─────────────────┐
  │            Component             │ Can Read? │   Can Modify?    │ Can Hot-Reload? │
  ├──────────────────────────────────┼───────────┼──────────────────┼─────────────────┤
  │ Capabilities (capabilities/*.py) │ ✓         │ ✓                │ ✓               │
  ├──────────────────────────────────┼───────────┼──────────────────┼─────────────────┤
  │ Agent orchestrator (agent.py)    │ ✓         │ ⚠️ (no workflow) │ ✗               │
  ├──────────────────────────────────┼───────────┼──────────────────┼─────────────────┤
  │ Sandbox (sandbox.py)             │ ✓         │ ⚠️ (no workflow) │ ✗               │
  ├──────────────────────────────────┼───────────┼──────────────────┼─────────────────┤
  │ Core types (core.py)             │ ✓         │ ⚠️ (no workflow) │ ✗               │
  └──────────────────────────────────┴───────────┴──────────────────┴─────────────────┘
  The SelfSourceCapability provides a complete workflow for capabilities (stage → test → reload → commit), but the core infrastructure lacks this workflow.

  ---
  Is This Desirable?

  Yes, but with graduated trust levels. Here's the deeper question:

  Self-modification spectrum:

  SAFE                                                     DANGEROUS
   |                                                           |
   v                                                           v
  Add new      Modify        Modify         Modify          Modify
  capabilities existing      agent.py       sandbox.py      permission
               capabilities  (orchestration) (execution)     system

  The architecture wisely starts with the safest end - new capabilities are isolated, tested, and don't touch the trusted computing base. The question is: should the agent be able to modify its own sandbox?

  Arguments FOR:
  - True self-improvement requires fixing limitations
  - Agent might discover bugs in its own infrastructure
  - Enables bootstrapping from simpler to more capable systems
  - The "runtime-primary" philosophy implies code is malleable

  Arguments AGAINST:
  - Sandbox is the security boundary - if compromised, all bets are off
  - Agent modifying its own permission system is a security nightmare
  - Hot-reloading core infrastructure is fragile
  - Need stable foundation to build upon

  ---
  Recommended Architecture for Full Self-Evolution

  Here's how I'd architect graduated self-modification:

  ┌────────────────────────────────────────────────────────────────┐
  │                    TRUST LAYERS                                │
  ├────────────────────────────────────────────────────────────────┤
  │                                                                │
  │  Layer 0: IMMUTABLE KERNEL (cannot be modified at runtime)     │
  │  ├─ Permission enforcement                                     │
  │  ├─ Sandbox boundary checks                                    │
  │  └─ Cryptographic verification                                 │
  │                                                                │
  │  Layer 1: HOT-MODIFIABLE CORE (requires restart for some)      │
  │  ├─ agent.py (orchestration logic)                            │
  │  ├─ sandbox.py (execution engine)                             │
  │  └─ core.py (type definitions)                                │
  │                                                                │
  │  Layer 2: LIVE-MODIFIABLE (current implementation)            │
  │  ├─ Capabilities                                              │
  │  ├─ Prompts/workflows                                         │
  │  └─ Knowledge/data                                            │
  │                                                                │
  │  Layer 3: EPHEMERAL (in-session only)                         │
  │  ├─ Local variables                                           │
  │  └─ Temporary capabilities                                    │
  │                                                                │
  └────────────────────────────────────────────────────────────────┘

  Concrete Implementation Steps

  1. Add CoreSourceCapability for Layer 1 modification:

  class CoreSourceCapability(Capability):
      name = "core"

      def read_core_source(self, module: str) -> str:
          """Read agent.py, sandbox.py, or core.py"""

      def propose_core_change(self, module: str, new_source: str) -> ChangeProposal:
          """Stage a change - does NOT apply it"""

      def validate_core_change(self, proposal: ChangeProposal) -> ValidationResult:
          """Static analysis, type checking, AST validation"""

      def test_core_change(self, proposal: ChangeProposal) -> TestResult:
          """Run in isolated subprocess with test harness"""

      def apply_core_change(self, proposal: ChangeProposal) -> ApplyResult:
          """Write to disk - REQUIRES RESTART"""

  2. Fork-exec architecture for testing core changes:

  Current Process                    Child Process
  ┌──────────────┐                 ┌──────────────┐
  │ Running Agent│ ─── fork ────> │ Test Agent   │
  │ (stable)     │                 │ (with changes)│
  └──────────────┘                 └──────────────┘
         │                                │
         │                                v
         │                         Run test suite
         │                                │
         │ <──── result ──────────────────┘
         v
    Apply or reject

  3. Capability contracts for self-modification:

  def contract(self) -> CapabilityContract:
      return CapabilityContract(
          writes=["source:capabilities/*"],      # Layer 2 - allowed
          # writes=["source:agent.py"],          # Layer 1 - higher approval
          # writes=["source:sandbox.py"],        # Layer 1 - highest approval
      )

  4. Multi-phase approval for core changes:

  class CoreChangeHandler(PermissionHandler):
      async def handle(self, request: PermissionRequest) -> PermissionDecision:
          if "source:sandbox.py" in request.plan.writes:
              # Require: user approval + test pass + 24hr delay
              return await self._high_security_approval(request)
          elif "source:agent.py" in request.plan.writes:
              # Require: user approval + test pass
              return await self._medium_security_approval(request)
          else:
              return await self._standard_approval(request)

  5. Versioning and rollback:

  class VersionedSource:
      """Git-like versioning for self-modifications"""

      def checkpoint(self) -> str:
          """Create snapshot of current state, return hash"""

      def rollback(self, checkpoint: str):
          """Restore to previous state"""

      def history(self) -> List[Commit]:
          """View modification history"""

  ---
  Key Design Principles

  1. Graduated trust: Not all code is equally modifiable
  2. Test before apply: Never hot-reload untested changes
  3. Rollback always available: Every change should be reversible
  4. Immutable security kernel: Some code CANNOT be modified at runtime
  5. Fork-exec isolation: Test dangerous changes in subprocess
  6. Explicit restart: Some changes require restart, make this clear

  ---
  What's Missing in Current Architecture

  1. No CoreSourceCapability - agent can read but has no workflow to modify core
  2. No subprocess testing - hot-reload only, can't test core changes safely
  3. No immutable kernel - everything is theoretically modifiable
  4. No versioning - git used externally, not integrated into agent
  5. No multi-phase approval - all changes treated equally

  Would you like me to implement any of these components? The most valuable addition would be the CoreSourceCapability with fork-exec testing, which would allow the agent to evolve its own orchestration logic safely.


  # 2026-01-11

  New File: src/agentself/capabilities/core_source.py (~600 lines)

  Architecture:
  Modifiability Layers:
  ├── Layer 0: IMMUTABLE (permission kernel - future)
  ├── Layer 1: RESTART REQUIRED (core modules) ← CoreSourceCapability manages this
  └── Layer 2: HOT-RELOAD (capabilities) ← SelfSourceCapability manages this

  Core Modules Managed:
  - agent.py - Orchestration logic
  - sandbox.py - Execution engine
  - core.py - Type definitions
  - permissions.py - Permission system
  - proxy.py - Call recording

  Key Methods:
  ┌───────────────┬─────────────────────────────────────────────────────────────────────┐
  │   Category    │                               Methods                               │
  ├───────────────┼─────────────────────────────────────────────────────────────────────┤
  │ Introspection │ list_modules(), read_module(), describe_module(), get_module_hash() │
  ├───────────────┼─────────────────────────────────────────────────────────────────────┤
  │ Staging       │ modify_module(), diff_module(), staged_changes(), rollback_staged() │
  ├───────────────┼─────────────────────────────────────────────────────────────────────┤
  │ Testing       │ test_module() - runs in subprocess (fork-exec pattern)              │
  ├───────────────┼─────────────────────────────────────────────────────────────────────┤
  │ Apply         │ apply_module() - writes to disk, requires restart                   │
  ├───────────────┼─────────────────────────────────────────────────────────────────────┤
  │ Versioning    │ list_versions(), rollback_to_version() - automatic backup & restore │
  └───────────────┴─────────────────────────────────────────────────────────────────────┘
  Safety Features:
  1. Syntax validation before staging
  2. Subprocess testing - tests run in isolated process, won't corrupt running agent
  3. Integrity checking - detects if file changed on disk since staging
  4. Automatic versioning - saves original before every modification
  5. Force flag - untested changes require explicit force=True
  6. Immutable layer - framework for security-critical code that cannot be modified

  Integration:
  - Added to agent's default sandbox as core capability
  - Read-only introspection auto-approved; modifications require explicit approval
  - Documented in system prompt for LLM awareness

  Tests: 25 new tests covering all functionality, all passing (230 total tests pass).

  ---
  Next Steps (if desired):
  1. Add integration tests that verify subprocess testing catches import errors
  2. Implement the "immutable kernel" for security-critical code
  3. Add a preview_restart() method that shows what would change on restart
  4. Consider adding git integration for version control of core changes