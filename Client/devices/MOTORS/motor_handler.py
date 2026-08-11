# -*- coding: utf-8 -*-
"""Threaded, local KDC101 motor handler.

The public signals and method names are intentionally compatible with the
legacy handler.  Work is now queued as immutable records so that a later move
cannot overwrite the target of a move which is already waiting in the queue.
"""

from dataclasses import dataclass
import math
from queue import Empty, Queue
from threading import Lock

from PyQt5.QtCore import QThread, pyqtSignal


version = "3.0"


class MotorMotionCancelled(RuntimeError):
    pass


@dataclass(frozen=True)
class MotorWorkItem:
    action: str
    target: object = None
    request_id: object = None
    requester: object = None


class MotorHandler(QThread):
    """Serialize all calls to one locally attached motor."""

    _sig_motor_initialized = pyqtSignal(str)
    _sig_motor_error = pyqtSignal(str)
    _sig_motor_move_done = pyqtSignal(str, float)
    _sig_motor_changed_position = pyqtSignal(str, float)
    _sig_motor_homed = pyqtSignal(str)
    _sig_motors_changed_status = pyqtSignal(str, str)

    # Extra correlation signals used by MotorController.  Existing consumers
    # can continue to use the signals above unchanged.
    _sig_motor_command_started = pyqtSignal(str, str, object)
    _sig_motor_command_finished = pyqtSignal(str, str, object, object)
    _sig_motor_command_error = pyqtSignal(str, str, object, str)
    _sig_motor_closed = pyqtSignal(str)
    _sig_motor_stopped = pyqtSignal(str)

    _ACTION_MAP = {
        "O": "open",
        "M": "move",
        "H": "home",
        "Q": "status",
        "D": "close",
        "C": "close",
        "S": "stop",
        "OPEN": "open",
        "MOVE": "move",
        "HOME": "home",
        "STATUS": "status",
        "POS": "status",
        "CLOSE": "close",
        "STOP": "stop",
    }

    def __init__(self, controller=None, ser=None, dev_type="Dummy", nick="motor",
                 position_min=0.0, position_max=13.0):
        super().__init__()
        self.parent = controller
        self.dev_type = dev_type
        self._motor = None
        self._position = 0.0
        self._status = "closed"
        self._nickname = str(nick)
        self._serial = None
        self._is_opened = False
        self._target = 0.0  # Kept only for legacy setTargetPosition callers.
        self._current_work = None
        self._work_pending = False
        self._state_lock = Lock()
        self._shutdown_requested = False
        self._motion_cancelled = False
        self.queue = Queue()

        self.serial = ser
        self.position_min, self.position_max = self._validated_bounds(
            position_min, position_max
        )

        # A persistent worker eliminates the QThread start/exit race which can
        # otherwise strand a command queued exactly while run() is returning.
        self.start()

    @staticmethod
    def _validated_bounds(position_min, position_max):
        try:
            lower = float(position_min)
            upper = float(position_max)
        except (TypeError, ValueError):
            return 0.0, 13.0
        if not math.isfinite(lower) or not math.isfinite(upper) or lower > upper:
            return 0.0, 13.0
        return lower, upper

    @property
    def serial(self):
        return self._serial

    @serial.setter
    def serial(self, ser):
        if ser is None:
            raise ValueError("The serial of a motor cannot be None.")
        self._serial = str(ser)

    @property
    def nickname(self):
        return self._nickname

    @nickname.setter
    def nickname(self, nick):
        self._nickname = str(nick)

    @property
    def position(self):
        return self._position

    @position.setter
    def position(self, pos):
        value = float(pos)
        if not math.isfinite(value):
            raise ValueError("Motor position must be finite.")
        self._position = value

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, status):
        status = str(status).lower()
        if status == self._status:
            return
        self._status = status
        self._sig_motors_changed_status.emit(self.nickname, status)

    def info(self):
        return {
            "serial_number": self.serial,
            "position": self.position,
            "status": self.status,
            "type": self.dev_type,
            "min": self.position_min,
            "max": self.position_max,
        }

    def isBusy(self):
        with self._state_lock:
            return self._work_pending or self._current_work is not None

    def getPosition(self):
        if self._motor is None or not self._is_opened:
            return self.position
        position = round(float(self._motor.get_position()), 3)
        if not math.isfinite(position):
            raise RuntimeError("Motor %s returned a non-finite position." % self.nickname)
        self.position = position
        self._sig_motor_changed_position.emit(self.nickname, self.position)
        return self.position

    def setTargetPosition(self, target):
        # Compatibility only.  toWorkList captures this value immediately.
        self._target = self._validate_target(target)

    def _validate_target(self, target):
        try:
            value = float(target)
        except (TypeError, ValueError):
            raise ValueError("Target position for %s must be numeric." % self.nickname)
        if not math.isfinite(value):
            raise ValueError("Target position for %s must be finite." % self.nickname)
        if value < self.position_min or value > self.position_max:
            raise ValueError(
                "Target %.6g for %s is outside [%.6g, %.6g]." % (
                    value, self.nickname, self.position_min, self.position_max
                )
            )
        return value

    def _device_class(self):
        if str(self.dev_type).lower() == "dummy":
            try:
                from .Dummy_motor import DummyKDC101
            except (ImportError, ValueError):
                from Dummy_motor import DummyKDC101
            return DummyKDC101
        if str(self.dev_type).upper() == "KDC101":
            try:
                from .KDC101 import KDC101
            except (ImportError, ValueError):
                from KDC101 import KDC101
            return KDC101
        raise ValueError("Unsupported motor type: %s" % self.dev_type)

    def openDevice(self):
        if self._is_opened and self._motor is not None:
            self._sig_motor_initialized.emit(self.nickname)
            return self.getPosition()

        device_class = self._device_class()
        self.status = "initiating"
        motor = None
        try:
            motor = device_class(self.serial)
            motor.open_and_start_polling()
            self._motor = motor
            self._is_opened = True
            self.position = self.getPosition()
            self.status = "standby"
            self._sig_motor_initialized.emit(self.nickname)
            return self.position
        except Exception:
            if motor is not None:
                try:
                    motor.close()
                except Exception:
                    pass
            self._motor = None
            self._is_opened = False
            raise

    def moveToPosition(self, target_position):
        if not self._is_opened or self._motor is None:
            raise RuntimeError("The motor %s is not opened yet." % self.nickname)
        target = self._validate_target(target_position)
        self.status = "moving"
        if target != self.position:
            move_result = self._motor.move_to_position(target)
            if isinstance(move_result, tuple) and len(move_result) >= 2:
                message_id = move_result[1]
                if message_id == 2:
                    self._motion_cancelled = True
                elif message_id == 3:
                    raise RuntimeError(
                        "Motor %s reached its travel limit." % self.nickname
                    )
                elif message_id != 1:
                    raise RuntimeError(
                        "Motor %s returned unexpected move message %r."
                        % (self.nickname, move_result)
                    )
        self.position = self.getPosition()
        if self._motion_cancelled:
            self.status = "standby"
            raise MotorMotionCancelled(
                "MOVE motor %s was cancelled by STOP." % self.nickname
            )
        self.status = "standby"
        self._sig_motor_move_done.emit(self.nickname, self.position)
        return self.position

    def forceHome(self):
        if not self._is_opened or self._motor is None:
            raise RuntimeError("The motor %s is not opened yet." % self.nickname)
        self.status = "homing"
        home_result = self._motor.home(force=True, verbose=False)
        self.position = self.getPosition()
        if self._motion_cancelled or home_result is False:
            self.status = "standby"
            raise MotorMotionCancelled(
                "HOME motor %s was cancelled by STOP." % self.nickname
            )
        self.status = "standby"
        self._sig_motor_homed.emit(self.nickname)
        return self.position

    def closeDevice(self):
        if self._motor is not None:
            self._motor.close()
        self._motor = None
        self._is_opened = False
        self.status = "closed"
        self._sig_motor_closed.emit(self.nickname)
        return self.position

    def stopDevice(self):
        if not self._is_opened or self._motor is None:
            raise RuntimeError("The motor %s is not opened yet." % self.nickname)
        stop = getattr(self._motor, "stop_profiled", None)
        if stop is None:
            raise RuntimeError("Motor %s does not support STOP." % self.nickname)
        stop()
        self.position = self.getPosition()
        self.status = "standby"
        self._sig_motor_stopped.emit(self.nickname)
        return self.position

    def _normalise_work(self, cmd, target=None, request_id=None, requester=None):
        if isinstance(cmd, MotorWorkItem):
            return cmd
        if isinstance(cmd, dict):
            action = cmd.get("action")
            target = cmd.get("target", target)
            request_id = cmd.get("request_id", request_id)
            requester = cmd.get("requester", requester)
        else:
            action = cmd
        action = self._ACTION_MAP.get(str(action).upper(), str(action).lower())
        if action == "move":
            if target is None:
                target = self._target
            target = self._validate_target(target)
        return MotorWorkItem(action, target, request_id, requester)

    def toWorkList(self, cmd, target=None, request_id=None, requester=None):
        if self._shutdown_requested:
            self._sig_motor_error.emit("Motor %s is shutting down." % self.nickname)
            return None
        try:
            work = self._normalise_work(cmd, target, request_id, requester)
        except Exception as exc:
            message = str(exc)
            self._sig_motor_error.emit(message)
            self._sig_motor_command_error.emit(
                self.nickname, "move", request_id, message
            )
            return None
        with self._state_lock:
            busy = self._work_pending or self._current_work is not None
            if not busy:
                self._work_pending = True
                if work.action in ("move", "home"):
                    # Establish the cancellation generation when the work is
                    # accepted, not later when the worker happens to dequeue
                    # it.  A STOP arriving in that gap must cancel the work.
                    self._motion_cancelled = False
        if busy and work.action != "stop":
            message = "Motor %s is busy." % self.nickname
            self._sig_motor_error.emit(message)
            self._sig_motor_command_error.emit(
                self.nickname, work.action, request_id, message
            )
            return None
        if busy and work.action == "stop":
            # STOP is the sole pre-emptive operation.  KDC101.stop_profiled()
            # is designed to be called while the worker is blocked waiting for
            # motion completion, so execute it immediately in the caller.
            self._motion_cancelled = True
            self._sig_motor_command_started.emit(
                self.nickname, work.action, work.request_id
            )
            try:
                result = self.stopDevice()
            except Exception as exc:
                message = "STOP motor %s failed: %s" % (self.nickname, exc)
                self._sig_motor_error.emit(message)
                self._sig_motor_command_error.emit(
                    self.nickname, work.action, work.request_id, message
                )
                return None
            self._sig_motor_command_finished.emit(
                self.nickname, work.action, work.request_id, result
            )
            return work
        self.queue.put(work)
        return work

    def _execute(self, work):
        with self._state_lock:
            self._current_work = work
        self._sig_motor_command_started.emit(
            self.nickname, work.action, work.request_id
        )
        try:
            if self._shutdown_requested and work.action != "close":
                raise MotorMotionCancelled(
                    "%s motor %s was discarded during shutdown."
                    % (work.action.upper(), self.nickname)
                )
            if work.action in ("move", "home") and self._motion_cancelled:
                raise MotorMotionCancelled(
                    "%s motor %s was cancelled before execution."
                    % (work.action.upper(), self.nickname)
                )
            if work.action == "open":
                result = self.openDevice()
            elif work.action == "move":
                result = self.moveToPosition(work.target)
            elif work.action == "home":
                result = self.forceHome()
            elif work.action == "status":
                result = self.getPosition()
            elif work.action == "close":
                result = self.closeDevice()
            elif work.action == "stop":
                result = self.stopDevice()
            else:
                raise ValueError("Unknown motor action: %s" % work.action)
        except Exception as exc:
            cancelled = isinstance(exc, MotorMotionCancelled)
            self.status = "standby" if cancelled and self._is_opened else "error"
            message = "%s motor %s failed: %s" % (
                work.action.upper(), self.nickname, exc
            )
            self._sig_motor_error.emit(message)
            self._sig_motor_command_error.emit(
                self.nickname, work.action, work.request_id, message
            )
        else:
            self._sig_motor_command_finished.emit(
                self.nickname, work.action, work.request_id, result
            )
        finally:
            with self._state_lock:
                self._current_work = None
                self._work_pending = False

    def run(self):
        while True:
            work = self.queue.get()
            try:
                if work is None:
                    return
                self._execute(work)
            finally:
                self.queue.task_done()
        with self._state_lock:
            if self._current_work is None:
                self._work_pending = False

    def shutdown(self, wait_ms=15000):
        if self._shutdown_requested:
            if self.isRunning():
                self.wait(wait_ms)
            return
        self._shutdown_requested = True
        self._motion_cancelled = True
        # Never execute stale queued MOVE/HOME/OPEN requests during shutdown.
        while True:
            try:
                self.queue.get_nowait()
            except Empty:
                break
            else:
                self.queue.task_done()
        if self._current_work is not None and self._is_opened:
            try:
                self._motion_cancelled = True
                stop = getattr(self._motor, "stop_profiled", None)
                if stop is not None:
                    stop()
            except Exception:
                pass
        if self._is_opened:
            self.queue.put(MotorWorkItem("close"))
        self.queue.put(None)
        if not self.wait(wait_ms):
            self._sig_motor_error.emit(
                "Timed out waiting for motor %s worker shutdown." % self.nickname
            )
