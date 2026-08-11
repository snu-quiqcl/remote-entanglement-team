# -*- coding: utf-8 -*-
"""Signal-compatible proxy for a motor owned by another client."""

import math
from queue import Queue

from PyQt5.QtCore import QThread, pyqtSignal


version = "4.0"


class RemoteMotorHandler(QThread):
    """Represent one canonical ``OWNER:motor`` without touching hardware.

    Network writes are asynchronous and cheap, so this compatibility QThread
    subclass does not start a worker.  Commands go through MotorController and
    its dedicated MotorTransport immediately.
    """

    _sig_motor_initialized = pyqtSignal(str)
    _sig_motor_error = pyqtSignal(str)
    _sig_motor_move_done = pyqtSignal(str, float)
    _sig_motor_changed_position = pyqtSignal(str, float)
    _sig_motor_homed = pyqtSignal(str)
    _sig_motors_changed_status = pyqtSignal(str, str)
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

    def __init__(self, controller=None, owner=None, dev_type="remote",
                 nick="motor", socket=None):
        super().__init__()
        if owner is None or not str(owner).strip():
            raise ValueError("A remote motor owner is required.")
        self.parent = controller
        self.dev_type = dev_type
        self._owner = str(owner).strip()
        self._nickname = str(nick).split(":")[-1]
        self.serial = "remote"
        self.socket = None  # Deliberately never use the legacy DDS socket.
        self._motor = None
        self._position = 0.0
        self._status = "offline"
        self.hardware_status = "unknown"
        self._is_opened = False
        self.online = False
        self.subscribed = False
        self._target = 0.0
        self.queue = Queue()  # Preserved for callers which inspect this attr.
        self.pending_request_ids = set()

    @property
    def owner(self):
        return self._owner

    @property
    def nickname(self):
        return self._nickname

    @nickname.setter
    def nickname(self, nick):
        self._nickname = str(nick).split(":")[-1]

    @property
    def canonical_nickname(self):
        return "%s:%s" % (self.owner, self.nickname)

    @property
    def position(self):
        return self._position

    @position.setter
    def position(self, pos):
        value = float(pos)
        if not math.isfinite(value):
            raise ValueError("Remote motor position must be finite.")
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
        self._sig_motors_changed_status.emit(self.canonical_nickname, status)

    def info(self):
        return {
            "owner": self.owner,
            "position": self.position,
            "status": self.status,
            "hardware_status": self.hardware_status,
            "online": self.online,
            "subscribed": self.subscribed,
            "type": self.dev_type,
        }

    def isBusy(self):
        return bool(self.pending_request_ids)

    def getPosition(self):
        return self.position

    def setTargetPosition(self, target):
        value = float(target)
        if not math.isfinite(value):
            raise ValueError("Target position must be finite.")
        self._target = value

    def connectRemote(self):
        return self.parent.connectRemoteMotors([self.canonical_nickname])

    def updateStatus(self):
        return self.connectRemote()

    def releaseRemote(self):
        return self.parent.releaseRemoteMotors([self.canonical_nickname])

    def _send(self, action, args=None):
        if not self.subscribed:
            self._sig_motor_error.emit(
                "Remote motor is not subscribed: %s" % self.canonical_nickname
            )
            return None
        if not self.online:
            self._sig_motor_error.emit(
                "Remote motor is offline: %s" % self.canonical_nickname
            )
            return None
        request_id = self.parent._sendRemoteCommand(
            self.canonical_nickname, action, args or {}
        )
        if request_id is not None:
            self.pending_request_ids.add(request_id)
        return request_id

    def openDevice(self):
        request_id = self._send("open")
        if request_id is not None:
            self.status = "initiating"
        return request_id

    def moveToPosition(self, target_position):
        self.setTargetPosition(target_position)
        request_id = self._send("move", {"position": self._target})
        if request_id is not None:
            self.status = "moving"
        return request_id

    def forceHome(self):
        request_id = self._send("home")
        if request_id is not None:
            self.status = "homing"
        return request_id

    def closeDevice(self):
        # Physical CLOSE is intentionally distinct from releaseRemote().
        return self._send("close")

    def stopDevice(self):
        return self._send("stop")

    def toSocket(self, msg):
        raise RuntimeError("Remote motors no longer use the DDS client socket.")

    def toWorkList(self, cmd, target=None, request_id=None, requester=None):
        if isinstance(cmd, dict):
            action = cmd.get("action")
            target = cmd.get("target", target)
        else:
            action = cmd
        action = self._ACTION_MAP.get(str(action).upper(), str(action).lower())
        if action == "open":
            return self.openDevice()
        if action == "move":
            if target is None:
                target = self._target
            return self.moveToPosition(target)
        if action == "home":
            return self.forceHome()
        if action == "status":
            return self.parent._sendRemoteCommand(
                self.canonical_nickname, "status", {}
            )
        if action == "close":
            return self.closeDevice()
        if action == "stop":
            return self.stopDevice()
        self._sig_motor_error.emit("Unknown remote motor action: %s" % action)
        return None

    def applySubscription(self, subscribed):
        self.subscribed = bool(subscribed)
        if not self.subscribed:
            self.online = False
            self._is_opened = False
            self.status = "released"
        elif not self.online:
            self.status = "offline"
        else:
            # Subscription is separate from hardware status; notify GUI/PMT
            # even when the visible status text itself did not change.
            self._sig_motors_changed_status.emit(
                self.canonical_nickname, self.status
            )

    def applyOffline(self):
        self.online = False
        self.subscribed = False
        self._is_opened = False
        self.pending_request_ids.clear()
        self.status = "offline"

    def applyState(self, status, position=None, online=True):
        was_open = self._is_opened
        self.online = bool(online)
        if position is not None:
            self.position = position
            self._sig_motor_changed_position.emit(
                self.canonical_nickname, self.position
            )
        if not self.online:
            self._is_opened = False
            self.status = "offline"
            return

        state = str(status or "unknown").lower()
        self.hardware_status = state
        if state in ("standby", "moving", "homing", "stopped"):
            self._is_opened = True
        elif state in ("closed", "offline", "unknown"):
            self._is_opened = False
        # "initiating" and "error" do not prove whether OPEN succeeded;
        # preserve the last confirmed physical state until a terminal update.
        self.status = state
        if self._is_opened and not was_open:
            self._sig_motor_initialized.emit(self.canonical_nickname)
        elif was_open and not self._is_opened:
            self._sig_motor_closed.emit(self.canonical_nickname)

    def applyAck(self, request_id):
        if request_id:
            self.pending_request_ids.add(request_id)

    def applyResult(self, request_id, action, result_status="completed",
                    position=None):
        self.pending_request_ids.discard(request_id)
        if result_status != "completed":
            if self.online:
                fallback = self.hardware_status
                if fallback in ("unknown", "initiating", "moving", "homing"):
                    fallback = "standby" if self._is_opened else "closed"
                self.status = fallback
            self._sig_motor_error.emit(
                "%s %s request %s was %s."
                % (self.canonical_nickname, action, request_id, result_status)
            )
            return
        if position is not None:
            self.position = position
            self._sig_motor_changed_position.emit(
                self.canonical_nickname, self.position
            )
        if action == "open":
            was_open = self._is_opened
            self._is_opened = True
            self.hardware_status = "standby"
            self.status = "standby"
            if not was_open:
                self._sig_motor_initialized.emit(self.canonical_nickname)
        elif action == "move":
            self.hardware_status = "standby"
            self.status = "standby"
            self._sig_motor_move_done.emit(
                self.canonical_nickname, self.position
            )
        elif action == "home":
            self.hardware_status = "standby"
            self.status = "standby"
            self._sig_motor_homed.emit(self.canonical_nickname)
        elif action == "close":
            self._is_opened = False
            self.hardware_status = "closed"
            self.status = "closed"
            self._sig_motor_closed.emit(self.canonical_nickname)
        elif action == "stop":
            self.hardware_status = "standby"
            self.status = "standby"
            self._sig_motor_stopped.emit(self.canonical_nickname)

    def applyError(self, request_id, code, message):
        self.pending_request_ids.discard(request_id)
        code = str(code or "REMOTE_ERROR").upper()
        offline_codes = (
            "OFFLINE",
            "OWNER_OFFLINE",
            "OWNER_DISCONNECTED",
            "TARGET_OFFLINE",
            "SESSION_REPLACED",
            "NOT_SUBSCRIBED",
        )
        if code in offline_codes or not self.online:
            self.online = False
            self._is_opened = False
            self.status = "offline"
        elif code == "HARDWARE_ERROR":
            self.status = "error"
        else:
            # Broker validation/authorization/BUSY errors reject the request;
            # they do not change the underlying hardware state.
            fallback = self.hardware_status
            if fallback in ("unknown", "initiating", "moving", "homing"):
                fallback = "standby" if self._is_opened else "closed"
            self.status = fallback
        self._sig_motor_error.emit(
            "%s [%s]: %s" % (self.canonical_nickname, code, message)
        )

    def shutdown(self, wait_ms=0):
        self.pending_request_ids.clear()
