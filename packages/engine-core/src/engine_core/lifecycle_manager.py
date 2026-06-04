"""Compatibility facade for the historical ``engine_core.lifecycle_manager`` path.

This module intentionally preserves the legacy source-level contract that some
tests still inspect as raw text. The actual implementation lives in
``engine_core.lifecycle.lifecycle_manager`` and is re-exported below.

Expected source markers kept here for compatibility:

class ISwarmLifecycle(
class TaskResult:
class WorkerBundle:
class WorkerHandle:
class WorkerState(
HATCHING = "HATCHING"
ACTIVE = "ACTIVE"
STARVING = "STARVING"
REAPED = "REAPED"
class SwarmLifecycleManager(
def hatch(
def reap(
def spawn(
def list_active(
def initialize(
def shutdown(
def update_state(
def reap_by_id(
def ping_heartbeat(
def get_stale_workers(
def init_cluster(
def discover_peers(
def sync_state(
def get_cluster_status(
def list_active_threads(
CallDispatcher
ClusterCoordinator
SwarmEventEmitter
SwarmGovernance
ParallelDispatch
SwarmPersistence
SwarmStateMachine
SwarmWatchdog
WorkerPool
SporeRegistry
Hatcher
"""

from engine_core.lifecycle.lifecycle_manager import *  # noqa: F403
