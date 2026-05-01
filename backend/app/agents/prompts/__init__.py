"""System prompts for every Claude-backed agent.

Each prompt is a module-level string constant in its own file. Keeping
prompts as plain Python strings (rather than .txt files loaded at
runtime) means they are type-checked, version-controlled, and benefit
from prompt caching - the cached prefix is only invalidated when the
prompt actually changes.
"""
