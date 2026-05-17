import logging
from logging import handlers
from pathlib import Path
import signal
import threading
import asyncio
from typing import Any, Callable, Dict

import daq_utils
from epics import PV
from threads import run_summary_monitor
from utils.healthcheck import perform_server_checks
from daq_utils import getBlConfig, setBlConfig
from daq_main_common import pybass_init, process_input
import os
from queue import Queue

# Setup logger
logger = logging.getLogger()
logging.getLogger().setLevel(logging.INFO)
logging.getLogger("ophyd").setLevel(logging.WARN)
logging.getLogger("caproto").setLevel(logging.WARN)
handler1 = handlers.RotatingFileHandler(
    "lsdcServerLog.txt", maxBytes=5000000, backupCount=100
)
myformat = logging.Formatter("%(asctime)s %(name)-8s %(levelname)-8s %(message)s")
handler1.setFormatter(myformat)
logger.addHandler(handler1)


workers: Dict[str, Dict[str, Any]] = {
    "normal": {
        "queue": Queue(),
        "pv_suffix": "command_s",
        "label": "command",
    },
    "immediate": {
        "queue": Queue(),
        "pv_suffix": "immediate_command_s",
        "label": "immediate",
    },
}

def worker(queue: Queue, worker_name: str = "worker") -> None:
    """
    This worker thread waits for a command to be added to the queue,
    then processes it directly in the worker thread
    """
    logger.info(f"{worker_name} started")
    # Make sure this worker thread has a default asyncio loop for the RunEngine
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())
    while True:
        cmd = queue.get()  # blocks until a command is available
        try:
            if cmd == "__STOP__":
                break
            process_input(cmd)
        except Exception:
            logger.exception("Error executing %r", cmd)
        finally:
            queue.task_done()
    logger.info(f"{worker_name} exiting")


def make_pv_callback(queue_label: str, queue: Queue) -> Callable[..., None]:
    def _cb(value: Any = None, char_value: Any = None, **kws: Any) -> None:
        s = (char_value or "").strip()
        if not s:
            return
        logger.info("PV %s -> %s", queue_label, s)
        queue.put(s)  # just enqueue; worker will pick it up

    return _cb


def run_server(prefix: str) -> None:
    """
    This server implementation allows multiple "workers" to execute commands in its own thread.
    Each worker runs commands from a queue assigned to it and each queue is populated by commands sent to it via Epics PVs.
    """
    # Start worker threads
    stop_evt = threading.Event()
    threads: Dict[str, threading.Thread] = {}
    # Start command handling threads
    for name, cfg in workers.items():
        t = threading.Thread(
            target=worker,
            name=f"cmd-worker-{name}",
            args=[cfg["queue"], f"{name} worker"],
            daemon=True,
        )
        t.start()
        threads[name] = t

    # Start summary table threads
    mx_dir = Path(getBlConfig("visitDirectory"))
    visit_name = ""
    for part in mx_dir.parts:
        if "pass-" in part:
            visit_name = f"mx{part.split('-')[1]}-1"
    fast_dp_dir = mx_dir / Path(visit_name) / Path("fast_dp_dir")
    fast_dp_dir.mkdir(parents=True, exist_ok=True)
    autoproc_dir = Path(mx_dir) / Path(visit_name) / Path("autoProc_dir")
    autoproc_dir.mkdir(parents=True, exist_ok=True)
    for basename, final_dir in {"fast_dp": fast_dp_dir, "autoPROC": autoproc_dir}.items():
        name = f"summary-monitor-{basename}"
        t = threading.Thread(
            target=run_summary_monitor,
            args=(final_dir, basename),
            kwargs={"period": 10, "stop_evt": stop_evt},
            daemon=True,
            name=name
        )
        t.start()
        threads[name] = t


    pvs: Dict[str, PV] = {}
    for name, cfg in workers.items():
        pv = PV(f"{prefix}{cfg['pv_suffix']}", auto_monitor=True)
        pv.put("", wait=True)
        pv.add_callback(make_pv_callback(cfg["label"], cfg["queue"]), run_now=False)
        pvs[name] = pv

    # Keep process alive; stop cleanly on Ctrl-C / SIGTERM
    def _sig(_s: int, _f: Any) -> None:
        stop_evt.set()

    signal.signal(signal.SIGINT, _sig)
    signal.signal(signal.SIGTERM, _sig)

    try:
        stop_evt.wait()
    finally:
        # tell workers to exit and wait for them
        stop_evt.set()
        for cfg in workers.values():
            cfg["queue"].put("__STOP__")
        for t in threads.values():
            t.join()


def main() -> None:
    pybass_init()
    perform_server_checks()
    setBlConfig("visitDirectory", os.environ.get("CURRENT_VISIT_DIR", os.getcwd()))
    logger.info(f"Beamline Comm: {daq_utils.beamlineComm}")
    run_server(daq_utils.beamlineComm)


if __name__ == "__main__":
    main()
