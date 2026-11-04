"""FRC history lake (TBA + Statbotics since 2010) for the history_sql tool."""
import sys
import types

# duckdb's native module imports __main__ when it loads, and the Azure
# Functions Python worker runs without one. Import this package before duckdb.
sys.modules.setdefault('__main__', types.ModuleType('__main__'))
