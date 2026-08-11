# -*- coding: utf-8 -*-
"""Asynchronous TCP transport dedicated to the standalone motor server."""

import math
import os
import re
import uuid

from PyQt5.QtCore import QIODevice, QObject, QTimer, pyqtSignal
from PyQt5.QtNetwork import QAbstractSocket, QTcpSocket

try:
    from .motor_protocol import (
        DEFAULT_MAX_FRAME_SIZE,
        PROTOCOL_VERSION,
        FrameDecoder,
        ProtocolError,
        encode_frame,
        normalize_json_value,
    )
except ImportError:  # The legacy client imports modules directly from this folder.
    from motor_protocol import (
        DEFAULT_MAX_FRAME_SIZE,
        PROTOCOL_VERSION,
        FrameDecoder,
        ProtocolError,
        encode_frame,
        normalize_json_value,
    )


_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_STATUS_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
_ERROR_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_ACTIONS = frozenset(("status", "open", "move", "home", "close", "stop"))
_RESULT_STATUSES = frozenset(("completed", "failed", "cancelled"))


class MotorTransport(QObject):
    """Motor-server connection with registration and persistent subscriptions.

    Commands are accepted only while :attr:`is_ready` is true.  They are
    written directly to Qt's socket buffer and are never retained by this
    class, so a reconnect cannot replay a motor operation.  Motor inventory
    and desired subscriptions are connection state and are restored after a
    reconnect.
    """

    message_received = pyqtSignal(dict)
    connection_changed = pyqtSignal(bool, str)
    ready_changed = pyqtSignal(bool)
    protocol_error = pyqtSignal(str)

    def __init__(
        self,
        cp,
        client_id,
        local_motors,
        remote_motors,
        parent=None,
        auto_connect=True,
    ):
        super().__init__(parent)

        self.client_id = self._validate_identifier(client_id, "client_id")
        self.local_motors = self._normalize_local_motors(local_motors)
        self._local_motor_ids = {item["id"] for item in self.local_motors}
        self._remote_motors = self._normalize_remote_motors(remote_motors)

        self.enabled = self._get_boolean(cp, "enabled", True)
        self.host = self._get_string(cp, "ip", "127.0.0.1").strip()
        self.port = self._get_integer(cp, "port", 61600)
        self.protocol_version = self._get_integer(cp, "protocol", PROTOCOL_VERSION)
        self.reconnect_interval_ms = self._get_integer(cp, "reconnect_interval_ms", 2000)
        self.max_frame_size = self._get_integer(
            cp, "max_frame_size", DEFAULT_MAX_FRAME_SIZE
        )
        configured_token = self._get_string(cp, "token", "")
        token_env = self._get_string(cp, "token_env", "").strip()
        environment_token = os.getenv(token_env) if token_env else None
        self.token = environment_token if environment_token is not None else configured_token

        if not self.host:
            raise ValueError("[motor_server] ip cannot be empty")
        if not 1 <= self.port <= 65535:
            raise ValueError("[motor_server] port must be between 1 and 65535")
        if self.protocol_version != PROTOCOL_VERSION:
            raise ValueError(
                "unsupported motor protocol %d (client supports %d)"
                % (self.protocol_version, PROTOCOL_VERSION)
            )
        if self.reconnect_interval_ms < 0:
            raise ValueError("reconnect_interval_ms cannot be negative")
        if not 1 <= self.max_frame_size <= 0xFFFFFFFF:
            raise ValueError("max_frame_size must fit an unsigned four-byte length")
        if len(self.token) > 4096:
            raise ValueError("motor server token cannot exceed 4096 characters")

        self.socket = QTcpSocket(self)
        self._decoder = FrameDecoder(self.max_frame_size)
        self._reconnect_timer = QTimer(self)
        self._reconnect_timer.setSingleShot(True)
        self._reconnect_timer.setInterval(self.reconnect_interval_ms)

        self._ready = False
        self._connected = False
        self._phase = "disconnected"
        self._manual_disconnect = False
        self._shutting_down = False
        self._attempt_in_progress = False
        self._disconnect_notified = False
        self._last_socket_error = ""
        self._disconnect_reason = ""

        self.socket.connected.connect(self._on_connected)
        self.socket.disconnected.connect(self._on_disconnected)
        self.socket.readyRead.connect(self._on_ready_read)
        if hasattr(self.socket, "errorOccurred"):
            self.socket.errorOccurred.connect(self._on_socket_error)
        else:  # pragma: no cover - compatibility with old PyQt5 builds.
            self.socket.error.connect(self._on_socket_error)
        self._reconnect_timer.timeout.connect(self.connectServer)

        if auto_connect:
            # Let the owner connect signals before the first asynchronous attempt.
            QTimer.singleShot(0, self.connectServer)

    @property
    def is_ready(self):
        return self._ready

    @property
    def remote_motors(self):
        return list(self._remote_motors)

    def connectServer(self):
        """Start an asynchronous connection attempt; never blocks the GUI thread."""

        if self._shutting_down:
            return False
        if not self.enabled:
            self.connection_changed.emit(False, "motor server is disabled")
            return False

        state = self.socket.state()
        if state in (
            QAbstractSocket.HostLookupState,
            QAbstractSocket.ConnectingState,
            QAbstractSocket.ConnectedState,
        ):
            return True

        self._manual_disconnect = False
        self._reconnect_timer.stop()
        self._decoder.reset()
        self._set_ready(False)
        self._phase = "connecting"
        self._attempt_in_progress = True
        self._disconnect_notified = False
        self._last_socket_error = ""
        self._disconnect_reason = ""
        self.socket.connectToHost(self.host, self.port, QIODevice.ReadWrite)
        return True

    def disconnectServer(self, spontaneous=True):
        """Close the socket.

        ``spontaneous=True`` means an explicit user/application disconnect and
        suppresses auto-reconnect.  Passing false is useful for forcing a fresh
        connection while leaving the reconnect policy active.
        """

        self._manual_disconnect = bool(spontaneous)
        if self._manual_disconnect:
            self._reconnect_timer.stop()
        self._disconnect_reason = (
            "client disconnected" if self._manual_disconnect else "connection reset"
        )
        self._set_ready(False)

        state = self.socket.state()
        if state == QAbstractSocket.UnconnectedState:
            self._connection_lost(self._disconnect_reason)
        elif state == QAbstractSocket.ConnectedState:
            self.socket.disconnectFromHost()
        else:
            self.socket.abort()
        return True

    def shutdown(self):
        """Permanently stop reconnect attempts and release the socket."""

        if self._shutting_down:
            return
        self._shutting_down = True
        self._manual_disconnect = True
        self._reconnect_timer.stop()
        self._disconnect_reason = "shutdown"
        self._set_ready(False)
        had_activity = self._connected or self._attempt_in_progress
        self.socket.abort()
        if had_activity:
            self._connection_lost("shutdown")

    def send_command(self, target, action, args=None, request_id=None):
        """Send one remote motor operation, returning its request id on success."""

        if not self._ready:
            return None
        try:
            target = self._validate_canonical_motor(target)
            if type(action) is not str or not action.strip():
                raise ProtocolError("action must be a non-empty string")
            action = action.strip().lower()
            if action not in _ACTIONS:
                raise ProtocolError("unsupported motor action: %s" % action)
            if args is None:
                args = {}
            args = normalize_json_value(args, "$.args")
            if type(args) is not dict:
                raise ProtocolError("command args must be a JSON object")
            if action == "move":
                if set(args) != {"position"}:
                    raise ProtocolError("move args must contain only position")
                args = {"position": self._normalize_position(args["position"])}
            elif args:
                raise ProtocolError("%s does not accept command args" % action)
            if request_id is None:
                request_id = "%s-%s" % (self.client_id, uuid.uuid4().hex)
            else:
                request_id = self._validate_request_id(request_id)
        except (ProtocolError, ValueError) as exc:
            self.protocol_error.emit(str(exc))
            return None

        message = {
            "type": "command",
            "request_id": request_id,
            "target": target,
            "action": action,
            "args": args,
        }
        if not self._send_message(message, require_ready=True):
            return None
        return request_id

    def publish_state(self, motor, status, position=None):
        try:
            motor = self._validate_local_motor(motor)
            status = self._validate_status(status)
            message = {"type": "state", "motor": motor, "status": status}
            if position is not None:
                message["position"] = self._normalize_position(position)
        except (ProtocolError, ValueError) as exc:
            self.protocol_error.emit(str(exc))
            return False
        return self._send_message(message, require_ready=True)

    def publish_result(
        self, request_id, motor, status="completed", position=None
    ):
        try:
            request_id = self._validate_request_id(request_id)
            motor = self._validate_local_motor(motor)
            status = self._validate_result_status(status)
            message = {
                "type": "result",
                "request_id": request_id,
                "motor": motor,
                "status": status,
            }
            if position is not None:
                message["position"] = self._normalize_position(position)
        except (ProtocolError, ValueError) as exc:
            self.protocol_error.emit(str(exc))
            return False
        return self._send_message(message, require_ready=True)

    def publish_error(self, request_id, motor, code, message):
        try:
            request_id = self._validate_request_id(request_id)
            motor = self._validate_local_motor(motor)
            code = self._validate_nonempty_string(code, "code").upper()
            if not _ERROR_CODE_RE.fullmatch(code):
                raise ProtocolError("code must contain only uppercase letters, numbers, underscores")
            message = self._validate_nonempty_string(message, "message")
            if len(message) > 1024:
                raise ProtocolError("message cannot exceed 1024 characters")
            envelope = {
                "type": "error",
                "request_id": request_id,
                "motor": motor,
                "code": code,
                "message": message,
            }
        except (ProtocolError, ValueError) as exc:
            self.protocol_error.emit(str(exc))
            return False
        return self._send_message(envelope, require_ready=True)

    def subscribe(self, motors):
        """Persist and, when connected, send desired canonical subscriptions."""

        try:
            requested = self._normalize_remote_motors(motors)
        except (ProtocolError, ValueError) as exc:
            self.protocol_error.emit(str(exc))
            return False

        new_motors = [motor for motor in requested if motor not in self._remote_motors]
        self._remote_motors.extend(new_motors)
        if not new_motors:
            return True
        if not self._ready:
            return False
        return self._send_message(
            {"type": "subscribe", "motors": new_motors}, require_ready=True
        )

    def unsubscribe(self, motors):
        """Persist and, when connected, send subscription removals."""

        try:
            requested = self._normalize_remote_motors(motors)
        except (ProtocolError, ValueError) as exc:
            self.protocol_error.emit(str(exc))
            return False

        removed = [motor for motor in requested if motor in self._remote_motors]
        if removed:
            removed_set = set(removed)
            self._remote_motors = [
                motor for motor in self._remote_motors if motor not in removed_set
            ]
        if not removed:
            return True
        if not self._ready:
            return False
        return self._send_message(
            {"type": "unsubscribe", "motors": removed}, require_ready=True
        )

    def _on_connected(self):
        self._attempt_in_progress = False
        self._connected = True
        self._disconnect_notified = False
        self._last_socket_error = ""
        self._decoder.reset()
        self._phase = "hello_sent"
        self.connection_changed.emit(True, "connected")

        hello = {
            "type": "hello",
            "protocol": self.protocol_version,
            "client_id": self.client_id,
            "token": self.token,
        }
        if not self._send_message(hello, require_ready=False):
            self._protocol_failure("could not send motor-server hello")

    def _on_disconnected(self):
        reason = self._disconnect_reason or self._last_socket_error or "server disconnected"
        self._connection_lost(reason)

    def _on_socket_error(self, _socket_error):
        self._last_socket_error = self.socket.errorString() or "socket error"
        # For failed connection attempts Qt can emit error without disconnected.
        QTimer.singleShot(0, self._finish_socket_error)

    def _finish_socket_error(self):
        if self.socket.state() == QAbstractSocket.UnconnectedState:
            self._connection_lost(self._last_socket_error or "socket error")

    def _on_ready_read(self):
        data = bytes(self.socket.readAll())
        try:
            messages = self._decoder.feed(data)
        except (ProtocolError, TypeError, ValueError) as exc:
            self._protocol_failure(str(exc))
            return
        for message in messages:
            if not self._handle_message(message):
                return

    def _handle_message(self, message):
        message_type = message.get("type")

        if message_type == "ping":
            pong = {"type": "pong"}
            # Echo common correlation fields without making them mandatory.
            for field in ("nonce", "timestamp"):
                if field in message:
                    pong[field] = message[field]
            return self._send_message(pong, require_ready=False)

        if message_type == "pong":
            return True

        if message_type == "hello_ack":
            if self._phase != "hello_sent":
                self._protocol_failure("unexpected hello_ack during %s" % self._phase)
                return False
            protocol = message.get("protocol", self.protocol_version)
            if type(protocol) is not int or protocol != self.protocol_version:
                self._protocol_failure("motor-server protocol version mismatch")
                return False
            if message.get("accepted", True) is not True:
                self._protocol_failure(str(message.get("message", "connection rejected")))
                return False
            self._phase = "register_sent"
            if not self._send_message(
                {"type": "register", "motors": self.local_motors},
                require_ready=False,
            ):
                self._protocol_failure("could not send motor inventory")
                return False
            return True

        if message_type == "registered":
            if self._phase != "register_sent":
                self._protocol_failure("unexpected registered during %s" % self._phase)
                return False
            if self._remote_motors:
                self._phase = "subscribe_sent"
                if not self._send_message(
                    {"type": "subscribe", "motors": list(self._remote_motors)},
                    require_ready=False,
                ):
                    self._protocol_failure("could not send motor subscriptions")
                    return False
            else:
                self._phase = "ready"
                self._set_ready(True)
            return True

        if message_type == "subscribed" and self._phase == "subscribe_sent":
            self._phase = "ready"
            self._set_ready(True)
            self.message_received.emit(message)
            return True

        # State snapshots may precede the subscribed acknowledgement.  All
        # non-handshake messages are delivered unchanged to MotorController.
        self.message_received.emit(message)
        return True

    def _send_message(self, message, require_ready):
        if require_ready and not self._ready:
            return False
        if self.socket.state() != QAbstractSocket.ConnectedState:
            return False
        try:
            frame = encode_frame(message, self.max_frame_size)
        except (ProtocolError, TypeError, ValueError) as exc:
            self.protocol_error.emit(str(exc))
            return False

        written = self.socket.write(frame)
        if written != len(frame):
            reason = self.socket.errorString() or "socket write failed"
            self.protocol_error.emit(reason)
            return False
        return True

    def _connection_lost(self, reason):
        was_active = self._connected or self._attempt_in_progress or self._phase != "disconnected"
        self._connected = False
        self._attempt_in_progress = False
        self._phase = "disconnected"
        self._decoder.reset()
        self._set_ready(False)

        if was_active and not self._disconnect_notified:
            self._disconnect_notified = True
            self.connection_changed.emit(False, str(reason))

        if not self._manual_disconnect and not self._shutting_down and self.enabled:
            self._schedule_reconnect()

    def _schedule_reconnect(self):
        if self._reconnect_timer.isActive():
            return
        self._reconnect_timer.start(max(0, self.reconnect_interval_ms))

    def _protocol_failure(self, reason):
        reason = str(reason)
        self.protocol_error.emit(reason)
        self._last_socket_error = reason
        self.socket.abort()
        self._connection_lost(reason)

    def _set_ready(self, ready):
        ready = bool(ready)
        if self._ready == ready:
            return
        self._ready = ready
        self.ready_changed.emit(ready)

    def _validate_local_motor(self, motor):
        motor = self._validate_identifier(motor, "motor")
        if motor not in self._local_motor_ids:
            raise ProtocolError("motor '%s' is not in the local inventory" % motor)
        return motor

    @staticmethod
    def _validate_identifier(value, field):
        if type(value) is not str:
            raise ValueError("%s must be a string" % field)
        value = value.strip()
        if not value or not _IDENTIFIER_RE.fullmatch(value):
            raise ValueError("invalid %s: %r" % (field, value))
        return value

    @classmethod
    def _validate_canonical_motor(cls, motor):
        if type(motor) is not str:
            raise ValueError("target motor must be a string")
        motor = motor.strip()
        if motor.count(":") != 1:
            raise ValueError("target motor must have the form owner:motor")
        owner, local_motor = motor.split(":", 1)
        owner = cls._validate_identifier(owner, "motor owner")
        local_motor = cls._validate_identifier(local_motor, "motor id")
        return "%s:%s" % (owner, local_motor)

    @classmethod
    def _normalize_remote_motors(cls, motors):
        if motors is None:
            motors = []
        elif type(motors) is str:
            motors = [motors]
        if type(motors) is not list:
            raise ValueError("remote_motors must be a list of owner:motor strings")
        normalized = []
        for motor in motors:
            canonical = cls._validate_canonical_motor(motor)
            if canonical not in normalized:
                normalized.append(canonical)
        if len(normalized) > 256:
            raise ValueError("at most 256 remote motors may be listed")
        return normalized

    @classmethod
    def _normalize_local_motors(cls, motors):
        if type(motors) is not list:
            raise ValueError("local_motors must be a list")
        if len(motors) > 256:
            raise ValueError("at most 256 local motors may be registered")
        normalized = []
        known = set()
        for index, motor in enumerate(motors):
            if type(motor) is not dict:
                raise ValueError("local_motors[%d] must be a dict" % index)
            motor_id = cls._validate_identifier(motor.get("id"), "local motor id")
            if motor_id in known:
                raise ValueError("duplicate local motor id: %s" % motor_id)
            minimum = cls._normalize_position(motor.get("min"), "min")
            maximum = cls._normalize_position(motor.get("max"), "max")
            if minimum > maximum:
                raise ValueError("local motor %s has min greater than max" % motor_id)
            normalized.append({"id": motor_id, "min": minimum, "max": maximum})
            known.add(motor_id)
        return normalized

    @staticmethod
    def _normalize_position(value, field="position"):
        try:
            value = normalize_json_value(value, "$.%s" % field)
        except ProtocolError:
            raise
        if type(value) not in (int, float) or type(value) is bool:
            raise ProtocolError("%s must be a finite number" % field)
        value = float(value)
        if not math.isfinite(value):
            raise ProtocolError("%s must be a finite number" % field)
        return value

    @staticmethod
    def _validate_nonempty_string(value, field):
        if type(value) is not str or not value.strip():
            raise ProtocolError("%s must be a non-empty string" % field)
        return value.strip()

    @classmethod
    def _validate_request_id(cls, request_id):
        request_id = cls._validate_nonempty_string(request_id, "request_id")
        if not _REQUEST_ID_RE.fullmatch(request_id):
            raise ProtocolError("request_id contains unsupported characters")
        return request_id

    @classmethod
    def _validate_status(cls, status):
        status = cls._validate_nonempty_string(status, "status").lower()
        if not _STATUS_RE.fullmatch(status):
            raise ProtocolError("status contains unsupported characters")
        return status

    @classmethod
    def _validate_result_status(cls, status):
        status = cls._validate_status(status)
        if status not in _RESULT_STATUSES:
            raise ProtocolError("invalid result status: %s" % status)
        return status

    @staticmethod
    def _get_string(cp, option, fallback):
        try:
            # raw=True is important for opaque tokens that may contain '%'.
            return cp.get("motor_server", option, raw=True, fallback=fallback)
        except (AttributeError, TypeError, ValueError):
            return fallback

    @classmethod
    def _get_integer(cls, cp, option, fallback):
        value = cls._get_string(cp, option, str(fallback))
        try:
            return int(value)
        except (TypeError, ValueError):
            raise ValueError("[motor_server] %s must be an integer" % option)

    @classmethod
    def _get_boolean(cls, cp, option, fallback):
        value = cls._get_string(cp, option, "true" if fallback else "false")
        if type(value) is bool:
            return value
        normalized = str(value).strip().lower()
        if normalized in ("1", "yes", "true", "on"):
            return True
        if normalized in ("0", "no", "false", "off"):
            return False
        raise ValueError("[motor_server] %s must be a boolean" % option)
