"""End-to-end MotorController test against the real standalone server."""

import asyncio
from configparser import ConfigParser
import logging
from pathlib import Path
import sys
import threading
import time
import unittest

from PyQt5.QtCore import QCoreApplication, QEventLoop


MOTORS_DIR = Path(__file__).resolve().parents[1]
REFACTOR_ROOT = Path(__file__).resolve().parents[4]
SERVER_DIR = REFACTOR_ROOT / "motor_server"
for path in (str(MOTORS_DIR), str(SERVER_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from motor_server import MotorServer, ServerConfig  # noqa: E402
from motor_controller_v4 import MotorController  # noqa: E402
from motor_handler import MotorHandler  # noqa: E402


class FastDummyMotor:
    """Deterministic hardware double; transport/server paths remain real."""

    def __init__(self, serial):
        self.serial = serial
        self.position = 1.0
        self.opened = False
        self.stopped = False

    def open_and_start_polling(self):
        self.opened = True
        return self

    def get_position(self):
        return self.position

    def move_to_position(self, position):
        # Leave enough time for a second same-motor request to prove it is
        # rejected rather than queued/replayed.
        time.sleep(0.15)
        if not self.stopped:
            self.position = float(position)
        return True

    def home(self, force=False, verbose=False):
        self.position = 0.0
        return True

    def stop_profiled(self):
        self.stopped = True

    def close(self):
        self.opened = False


class Parent:
    pass


class MotorControllerIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])
        cls.server_ready = threading.Event()
        cls.server_holder = {}

        def run_server():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            config = ServerConfig(
                host="127.0.0.1",
                port=0,
                request_timeout=10.0,
                heartbeat_interval=30.0,
                heartbeat_timeout=90.0,
                permissions={"EA": {"EC"}, "EC": {"EA"}},
            )
            server = MotorServer(
                config,
                logger=logging.getLogger("controller.integration.server"),
                audit_logger=logging.getLogger("controller.integration.audit"),
            )
            loop.run_until_complete(server.start())
            cls.server_holder.update(
                loop=loop, server=server, port=server.bound_address[1]
            )
            cls.server_ready.set()
            loop.run_forever()
            loop.close()

        cls.server_thread = threading.Thread(target=run_server, daemon=True)
        cls.server_thread.start()
        if not cls.server_ready.wait(5.0):
            raise RuntimeError("Motor Server did not start")

        cls.original_device_class = MotorHandler._device_class
        MotorHandler._device_class = lambda self: FastDummyMotor

    @classmethod
    def tearDownClass(cls):
        MotorHandler._device_class = cls.original_device_class
        loop = cls.server_holder["loop"]
        server = cls.server_holder["server"]
        future = asyncio.run_coroutine_threadsafe(server.close(), loop)
        future.result(timeout=5.0)
        loop.call_soon_threadsafe(loop.stop)
        cls.server_thread.join(timeout=5.0)

    def make_config(self, client_id, motors):
        cp = ConfigParser()
        cp.read_dict({
            "client": {"nickname": client_id},
            "device": {"motors": "MOTORS"},
            "motors": motors,
            "motor_server": {
                "enabled": "true",
                "mode": "standalone",
                "ip": "127.0.0.1",
                "port": str(self.server_holder["port"]),
                "protocol": "1",
                "reconnect_interval_ms": "100",
                "client_id": client_id,
            },
        })
        return cp

    def wait_until(self, predicate, timeout=5.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.app.processEvents(QEventLoop.AllEvents, 50)
            if predicate():
                return True
            time.sleep(0.005)
        self.app.processEvents(QEventLoop.AllEvents, 50)
        return bool(predicate())

    def test_remote_open_move_busy_result_and_clean_shutdown(self):
        ea_parent = Parent()
        ea_parent.cp = self.make_config(
            "EA",
            {
                "motor_type": "Dummy",
                "px_serno": "fast-ea",
                "px_min": "0",
                "px_max": "13",
            },
        )
        ec_parent = Parent()
        ec_parent.cp = self.make_config(
            "EC", {"motor_type": "Dummy", "px_owner": "EA"}
        )

        ea = MotorController(ea_parent)
        ec = MotorController(ec_parent)
        remote = ec._motors["EA:px"]
        errors = []
        moves = []
        remote._sig_motor_error.connect(errors.append)
        remote._sig_motor_move_done.connect(
            lambda nickname, position: moves.append((nickname, position))
        )

        try:
            self.assertTrue(self.wait_until(
                lambda: ea.transport.is_ready
                and ec.transport.is_ready
                and remote.subscribed
                and remote.online
                and remote.status == "closed"
            ))
            self.assertEqual(remote.status, "closed")
            self.assertIsNone(ea._resolveMotorNick("OTHER:px"))
            self.assertEqual(ea._resolveMotorNick("EA:px"), "px")

            ec.openDevice(["EA:px"])
            self.assertTrue(self.wait_until(
                lambda: remote._is_opened
                and remote.status == "standby"
                and not ec._pending_remote
                and not ea._pending_local
            ))

            ec.moveToPosition({"EA:px": 4.5})
            ec.moveToPosition({"EA:px": 9.0})
            self.assertTrue(self.wait_until(
                lambda: bool(moves)
                and not ec._pending_remote
                and not ea._pending_local
            ))
            self.assertEqual(moves[-1][0], "EA:px")
            self.assertAlmostEqual(moves[-1][1], 4.5, places=3)
            self.assertAlmostEqual(remote.position, 4.5, places=3)
            self.assertTrue(any("busy" in message.lower() for message in errors))
            self.assertEqual(ea._motors["px"].queue.qsize(), 0)
        finally:
            ec.shutdown()
            self.assertTrue(self.wait_until(lambda: not ec._pending_remote, 1.0))
            ea.shutdown()
            self.assertFalse(ea._motors["px"].isRunning())

    def test_stop_cancels_move_without_false_move_done(self):
        ea_parent = Parent()
        ea_parent.cp = self.make_config(
            "EA",
            {
                "motor_type": "Dummy",
                "px_serno": "fast-ea-stop",
                "px_min": "0",
                "px_max": "13",
            },
        )
        ec_parent = Parent()
        ec_parent.cp = self.make_config(
            "EC", {"motor_type": "Dummy", "px_owner": "EA"}
        )
        ea = MotorController(ea_parent)
        ec = MotorController(ec_parent)
        remote = ec._motors["EA:px"]
        move_done = []
        stopped = []
        cancelled = []
        remote._sig_motor_move_done.connect(
            lambda nickname, position: move_done.append((nickname, position))
        )
        remote._sig_motor_stopped.connect(stopped.append)
        remote._sig_motor_error.connect(cancelled.append)

        try:
            self.assertTrue(self.wait_until(
                lambda: ea.transport.is_ready
                and ec.transport.is_ready
                and remote.subscribed
                and remote.online
            ))
            ec.openDevice(["EA:px"])
            self.assertTrue(self.wait_until(
                lambda: remote._is_opened and not ec._pending_remote
            ))

            initial_position = remote.position
            ec.moveToPosition({"EA:px": 8.0})
            self.assertTrue(self.wait_until(lambda: bool(ec._pending_remote)))
            ec.stopMotor("EA:px")
            self.assertTrue(self.wait_until(
                lambda: bool(stopped)
                and not ec._pending_remote
                and not ea._pending_local
            ))
            # The interrupted worker must not masquerade as a successful move.
            self.assertEqual(move_done, [])
            self.assertAlmostEqual(remote.position, initial_position, places=3)
            self.assertTrue(any("cancel" in item.lower() for item in cancelled))
        finally:
            ec.shutdown()
            ea.shutdown()
            self.assertFalse(ea._motors["px"].isRunning())


if __name__ == "__main__":
    unittest.main()
