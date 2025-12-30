import argparse
import logging
from logging import handlers
import signal
import threading
from concurrent.futures import ThreadPoolExecutor
import asyncio

import daq_utils
from epics import PV
from utils.healthcheck import perform_server_checks
from daq_utils import setBlConfig
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


# Queues to hold commands from 
normal_queue: "Queue[str]" = Queue()
immediate_queue: "Queue[str]" = Queue()

# Threadpools to execute the commands
normal_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="Normal")
immediate_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="Immediate")

def _ensure_loop_then_call(fn, *a, **kw):
    # Make sure this worker thread has a default asyncio loop for the RunEngine
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())
    return fn(*a, **kw)


def call_on_executor(executor, fn, *a, **kw):
    return executor.submit(_ensure_loop_then_call, fn, *a, **kw).result()


def worker(queue, executor, worker_name="worker"):
    """
    This worker thread waits for a command to be added to the queue,
    then passes it on to the executor pool
    """
    logger.info(f"{worker_name} started")
    while True:
        cmd = queue.get()  # blocks until a command is available
        try:
            if cmd == "__STOP__":
                break
            call_on_executor(executor, process_input, cmd)
        except Exception:
            logger.exception("Error executing %r", cmd)
        finally:
            queue.task_done()
    logger.info(f"{worker_name} exiting")


def make_pv_callback(priority_label, queue):
    def _cb(value=None, char_value=None, **kws):
        s = (char_value or "").strip()
        if not s:
            return
        logger.info("PV %s -> %s", priority_label, s)
        queue.put(s)  # just enqueue; worker will pick it up

    return _cb


def run_server(prefix: str):
    """
    This server implementation allows multiple "workers" to execute commands in its own thread.
    Each worker runs commands from a queue assigned to it and each queue is populated by commands sent to it via Epics PVs.
    """
    # Start worker thread
    normal_worker_thread = threading.Thread(target=worker, name="cmd-worker", args=[normal_queue, normal_executor, "normal worker"], daemon=True)
    normal_worker_thread.start()
    immediate_worker_thread = threading.Thread(target=worker, name="cmd-worker", args=[immediate_queue, immediate_executor, "immediate worker"], daemon=True)
    immediate_worker_thread.start()

    pv_cmd = PV(f"{prefix}command_s", auto_monitor=True)
    pv_cmd.put("", wait=True)
    pv_cmd.add_callback(make_pv_callback("command", normal_queue), run_now=False)

    pv_imm = PV(f"{prefix}immediate_command_s", auto_monitor=True)
    pv_imm.put("", wait=True)
    pv_imm.add_callback(make_pv_callback("immediate", immediate_queue), run_now=False)

    # Keep process alive; stop cleanly on Ctrl-C / SIGTERM
    stop_evt = threading.Event()

    def _sig(_s, _f):
        stop_evt.set()

    signal.signal(signal.SIGINT, _sig)
    signal.signal(signal.SIGTERM, _sig)

    try:
        stop_evt.wait()
    finally:
        # tell worker to exit and wait for it
        normal_queue.put("__STOP__")
        normal_worker_thread.join()
        immediate_worker_thread.join()
        normal_executor.shutdown(wait=True, cancel_futures=True)
        immediate_executor.shutdown(wait=True, cancel_futures=True)


def main():
    pybass_init()
    perform_server_checks()
    setBlConfig("visitDirectory", os.environ.get("CURRENT_VISIT_DIR", os.getcwd()))
    logger.info(f"Beamline Comm: {daq_utils.beamlineComm}")
    run_server(daq_utils.beamlineComm)


if __name__ == "__main__":
    main()
