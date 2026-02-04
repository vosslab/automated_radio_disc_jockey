# Prompt Color Categories

This doc defines the color palette and when to use each color for CLI output.
Use these colors consistently so logs remain easy to scan.

## Palette
- `RED` (`#e60000`): critical failure, unrecoverable error, or immediate stop
- `DARK ORANGE` (`#e65400`): error with possible recovery or external dependency failure
- `LIGHT ORANGE` (`#e69100`): warning that changed behavior, degraded quality, or a retry
- `DARK YELLOW` (`#b3b300`): cautionary info, non-fatal validation notes, or skipped steps
- `LIME GREEN` (`#59b300`): success with caveats, accepted fallback, or soft success
- `GREEN` (`#009900`): success, completion, and confirmed good outcome
- `TEAL` (`#00b38f`): neutral system status, progress checkpoints, or state transitions
- `CYAN` (`#00b3b3`): informative prompts, human input cues, or file selection lists
- `SKY BLUE` (`#0a9bf5`): external service interaction, model calls, or network actions
- `BLUE` (`#0039e6`): general informational messages, headings, or section labels
- `NAVY` (`#004d99`): debug output, developer-only diagnostics, or verbose traces
- `PURPLE` (`#7b12a1`): highlights for featured output blocks (for example DJ intro header)
- `MAGENTA` (`#b30077`): optional or secondary info that should stand out
- `PINK` (`#cc0066`): user-facing emphasis for non-error alerts or reminders

## Usage Rules
- Prefer `GREEN` for normal success, `LIME GREEN` for soft success, and `LIGHT ORANGE` for warnings.
- Use `RED` only for hard failures that stop a step or end the session.
- Use `BLUE` for general status lines and `CYAN` for prompts or user selection.
- Use `SKY BLUE` for LLM or external service requests and responses.
- Avoid mixing more than three colors in a short block.
