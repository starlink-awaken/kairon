# WARNING: Phantom Directory
# packages/ontoderive/engine/ contains the REAL implementation (116 files).
# src/ontoderive/ is the installed package (21 files) — effectively untested.
# All 50 test files import from engine/ via sys.path hacks.
# DO NOT delete engine/ — it is the source of truth for tests.
# Resolution requires dedicated session to merge engine/ into src/ontoderive/.
