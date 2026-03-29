# Car Tuner — Multi-Agent System

## Route Commands

When the user says **"tune my car"** or **"diagnose my car"**:
→ Find the orchestrator at `.claude/projects/car-tuner/orchestrator.md`
→ Spin up a sub-agent using that orchestrator as the system prompt
→ The orchestrator will handle delegating to the 4 specialist sub-agents

When the user says **"quick scan"**:
→ Run `python C:/Users/asol_/repos/car-tuner/car_tuner.py --demo` for testing
→ Or without `--demo` when a real car is connected

## Project Structure
```
.claude/projects/car-tuner/
├── orchestrator.md              ← Manages the workflow
└── subagents/
    ├── diagnostics-agent.md     ← Reads ECU data & sensors
    ├── analysis-agent.md        ← Interprets the data
    ├── tuning-agent.md          ← Recommends tune changes
    └── safety-agent.md          ← Validates safety of changes
```

## Tools
- Main script: `car_tuner.py` (OBD-II via python-obd library)
- Requires: ELM327 USB adapter for real car connection
- Use `--demo` flag for testing without a car
