python_terminal.py

A single-file Python backend that implements a functioning command terminal (CLI) and
an optional minimal web-based front-end (Flask) to send commands and receive outputs.

Features implemented:
- Built-in commands: ls, cd, pwd, mkdir, rm, cat, echo, touch, mv, cp
- System monitoring commands: cpu, mem, ps, top (snapshot)
- External command execution fallback via subprocess
- Error handling for invalid commands
- Command history saved to ~/.pyterminal_history
- Autocomplete using readline (when available)
- Basic natural-language -> command interpreter (naive rules)

Security note: This tool executes shell commands. Do NOT run this on a multi-user
or production system without sandboxing. It is intended for learning and local use.

Dependencies:
- Python 3.8+
- psutil (for system monitoring): pip install psutil

Run as CLI:
    python python_terminal.py
