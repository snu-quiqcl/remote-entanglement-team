"""Motor controller facade backed by the standalone Motor Server."""

import math

from PyQt5.QtCore import QObject, QTimer, pyqtSignal

try:
    from .motor_handler import MotorHandler
    from .remote_motor_handler import RemoteMotorHandler
    from .motor_transport import MotorTransport
except (ImportError, ValueError):
    # The legacy application adds devices/MOTORS directly to sys.path.
    from motor_handler import MotorHandler
    from remote_motor_handler import RemoteMotorHandler
    from motor_transport import MotorTransport


version = "4.0"
qtimer_interval = 250


class MotorController(QObject):
    """Own local motor workers and remote motor proxies.

    DDS/RF continue to use the legacy client socket, but MOTOR traffic never
    does.  Local motor calls remain available when the Motor Server is offline.
    """

    _sig_motors_initialized = pyqtSignal(int, str)
    _sig_motors_positions = pyqtSignal(dict)
    _sig_remote_control = pyqtSignal()  # Legacy signal kept for compatibility.
    _sig_transport_connection = pyqtSignal(bool, str)
    _sig_transport_ready = pyqtSignal(bool)

    _SUPPORTED_ACTIONS = frozenset(
        ("status", "open", "move", "home", "close", "stop")
    )
    _BUSY_STATES = frozenset(("initiating", "moving", "homing"))

    def __init__(self, socket=None, gui=None):
        super().__init__()
        if socket is None or not hasattr(socket, "cp"):
            raise ValueError("MotorController requires a parent with a .cp config parser.")

        # Retain this reference only for config/lifecycle compatibility.  It is
        # never used to send motor messages.
        self.sck = socket
        self.cp = socket.cp
        self.gui = gui
        self._status = "standby"
        self._is_opened = False
        self._gui_opened = False
        self._shutting_down = False
        self._transport_ready = False
        self._transport_connected = False
        self._transport_reason = "not connected"
        self._motors = {}
        self._local_motor_keys = set()
        self._remote_motor_keys = set()
        self._remote_motor_owners = {}
        self._motors_under_request = []
        self._motors_under_homing = []
        self._motors_under_loading = []
        self._pending_local = {}       # local id -> inbound execute context
        self._pending_remote = {}      # request id -> target/action

        self.user_name = self.cp.get("client", "nickname").strip()
        self.device = self.cp.get("device", "motors", fallback="MOTORS")
        self._motors = self._getMotorDictToLoad()

        self.pos_checker = QTimer(self)
        self.pos_checker.setSingleShot(True)
        self.pos_checker.timeout.connect(self.checkPositionsUnderMoving)

        local_inventory = []
        for nick in sorted(self._local_motor_keys):
            motor = self._motors[nick]
            local_inventory.append({
                "id": nick,
                "min": motor.position_min,
                "max": motor.position_max,
            })

        configured_client_id = self.cp.get(
            "motor_server", "client_id", fallback=self.user_name
        ).strip()
        if configured_client_id != self.user_name:
            raise ValueError(
                "[motor_server] client_id must match [client] nickname "
                "for exact motor ownership routing."
            )
        self.motor_client_id = configured_client_id
        self.transport = MotorTransport(
            self.cp,
            configured_client_id,
            local_inventory,
            sorted(self._remote_motor_keys),
            parent=self,
            auto_connect=True,
        )
        # Alias helps external diagnostics migrate without knowing the internal
        # attribute selected for this version.
        self.motor_transport = self.transport
        self.transport.message_received.connect(self._onTransportMessage)
        self.transport.connection_changed.connect(self._onTransportConnection)
        self.transport.ready_changed.connect(self._onTransportReady)
        self.transport.protocol_error.connect(self._onProtocolError)

        print("Motor Controller v%s (%s)" % (version, self.user_name))

    def _config_float(self, options, fallback):
        for option in options:
            if self.cp.has_option("motors", option):
                try:
                    value = float(self.cp.get("motors", option))
                except (TypeError, ValueError):
                    continue
                if math.isfinite(value):
                    return value
        return float(fallback)

    def _motorBounds(self, nickname):
        lower = self._config_float(
            (nickname + "_min", nickname + "_position_min", "position_min"),
            0.0,
        )
        upper = self._config_float(
            (nickname + "_max", nickname + "_position_max", "position_max"),
            13.0,
        )
        if lower > upper:
            self._detectedError(
                "Invalid bounds for %s; using [0, 13]." % nickname
            )
            return 0.0, 13.0
        return lower, upper

    def _getMotorDictToLoad(self):
        motor_dict = {}
        motor_type = self.cp.get("motors", "motor_type", fallback="Dummy")
        for option in self.cp.options("motors"):
            if option.endswith("_serno"):
                nickname = option[:-6]
                serial = self.cp.get("motors", option)
                lower, upper = self._motorBounds(nickname)
                motor = MotorHandler(
                    self,
                    serial,
                    dev_type=motor_type,
                    nick=nickname,
                    position_min=lower,
                    position_max=upper,
                )
                self._connectLocalMotor(motor)
                motor_dict[nickname] = motor
                self._local_motor_keys.add(nickname)
            elif option.endswith("_owner"):
                nickname = option[:-6]
                owner = self.cp.get("motors", option).strip()
                canonical = "%s:%s" % (owner, nickname)
                motor = RemoteMotorHandler(self, owner, "remote", nickname)
                self._connectRemoteMotor(motor)
                motor_dict[canonical] = motor
                self._remote_motor_keys.add(canonical)
                self._remote_motor_owners.setdefault(owner, []).append(nickname)
        return motor_dict

    def _connectLocalMotor(self, motor):
        motor._sig_motor_initialized.connect(self._initializedMotor)
        motor._sig_motor_move_done.connect(self._completedMotorMoving)
        motor._sig_motor_error.connect(self._detectedError)
        motor._sig_motor_homed.connect(self._homedMotor)
        motor._sig_motor_changed_position.connect(self._localPositionChanged)
        motor._sig_motors_changed_status.connect(self._localStatusChanged)
        motor._sig_motor_command_finished.connect(self._localCommandFinished)
        motor._sig_motor_command_error.connect(self._localCommandError)

    def _connectRemoteMotor(self, motor):
        motor._sig_motor_initialized.connect(self._initializedMotor)
        motor._sig_motor_move_done.connect(self._completedMotorMoving)
        motor._sig_motor_error.connect(self._detectedError)
        motor._sig_motor_homed.connect(self._homedMotor)
        motor._sig_motor_changed_position.connect(self._remotePositionChanged)

    def _addMotor(self, serno, dev_type, nickname):
        lower, upper = self._motorBounds(nickname)
        motor = MotorHandler(
            self, serno, dev_type, nickname, lower, upper
        )
        self._connectLocalMotor(motor)
        return motor

    def _addRemoteMotor(self, owner, dev_type, nickname):
        motor = RemoteMotorHandler(self, owner, dev_type, nickname)
        self._connectRemoteMotor(motor)
        return motor

    def addMotor(self, serno_or_owner, dev_type, nickname, remote_flag=0):
        if remote_flag:
            canonical = "%s:%s" % (serno_or_owner, nickname)
            if canonical in self._motors:
                raise ValueError("Motor already exists: %s" % canonical)
            self._motors[canonical] = self._addRemoteMotor(
                serno_or_owner, dev_type, nickname
            )
            self._remote_motor_keys.add(canonical)
            self._remote_motor_owners.setdefault(serno_or_owner, []).append(nickname)
            self.transport.subscribe([canonical])
        else:
            # Runtime inventory mutation cannot safely alter an authenticated
            # registration; require restart after changing local hardware.
            raise RuntimeError(
                "Adding a local motor at runtime is unsupported; update config and restart."
            )

    def _removeMotor(self, nickname):
        motor_key = self._resolveMotorNick(nickname)
        if motor_key is None:
            return
        motor = self._motors.pop(motor_key)
        if motor_key in self._remote_motor_keys:
            self.transport.unsubscribe([motor_key])
            self._remote_motor_keys.discard(motor_key)
        else:
            motor.shutdown()
            self._local_motor_keys.discard(motor_key)

    def _fullMotorNick(self, nick):
        if isinstance(nick, str) and nick.count(":") == 1:
            return nick
        return "%s:%s" % (self.user_name, nick)

    def _resolveMotorNick(self, nick):
        """Resolve only exact keys or this client's own canonical local key."""
        if not isinstance(nick, str):
            return None
        nick = nick.strip()
        if nick in self._motors:
            return nick
        if nick.count(":") == 1:
            owner, local_nick = nick.split(":", 1)
            if owner == self.user_name and local_nick in self._local_motor_keys:
                return local_nick
        return None

    def _localFromExecuteTarget(self, message):
        canonical = message.get("canonical_target")
        target = message.get("target")
        if isinstance(canonical, str) and canonical.count(":") == 1:
            owner, local_nick = canonical.split(":", 1)
            if owner != self.user_name:
                return None
            if target is not None and target != local_nick:
                return None
            return local_nick if local_nick in self._local_motor_keys else None
        # A server execute must be canonicalized; never turn OTHER:px into px.
        return None

    def openGui(self):
        try:
            from .Motor_Controller_GUI_v4 import MotorController_GUI
        except (ImportError, ValueError):
            from Motor_Controller_GUI_v4 import MotorController_GUI
        self.gui = MotorController_GUI(controller=self)
        self._gui_opened = True

    # ------------------------------------------------------------------
    # Transport lifecycle and message handling
    def _onTransportConnection(self, connected, reason):
        self._transport_connected = bool(connected)
        self._transport_reason = str(reason)
        self._sig_transport_connection.emit(bool(connected), str(reason))
        if not connected:
            self._markRemoteOffline()

    def _onTransportReady(self, ready):
        self._transport_ready = bool(ready)
        self._sig_transport_ready.emit(bool(ready))
        if not ready:
            self._markRemoteOffline()
            return
        # State changes while offline/handshaking are not queued.  Publish one
        # authoritative snapshot as soon as registration is ready.
        for nick in sorted(self._local_motor_keys):
            motor = self._motors[nick]
            self.transport.publish_state(nick, motor.status, motor.position)

    def _onProtocolError(self, message):
        self._detectedError("Motor protocol error: %s" % message)

    def _markRemoteOffline(self):
        if self._shutting_down:
            self._pending_remote.clear()
            self._pending_local.clear()
            for canonical in self._remote_motor_keys:
                self._motors[canonical].applyOffline()
            return
        for request_id, context in list(self._pending_remote.items()):
            target = context["target"]
            self._motors[target].applyError(
                request_id, "OFFLINE", "Motor Server connection was lost."
            )
            self._clearOperationTracking(target, context["action"])
        self._pending_remote.clear()
        # Owner-side execute requests belong to the disconnected session and
        # must not keep a local motor BUSY after reconnect.
        self._pending_local.clear()
        for canonical in self._remote_motor_keys:
            self._motors[canonical].applyOffline()

    def _onTransportMessage(self, message):
        if not isinstance(message, dict):
            self._onProtocolError("received a non-object message")
            return
        message_type = str(message.get("type", "")).lower()
        if message_type == "execute":
            self._handleExecute(message)
        elif message_type == "state":
            self._handleRemoteState(message)
        elif message_type == "result":
            self._handleRemoteResult(message)
        elif message_type == "error":
            self._handleRemoteError(message)
        elif message_type in ("command_ack", "ack"):
            self._handleRemoteAck(message)
        elif message_type == "subscribed":
            self._handleSubscription(message, True)
        elif message_type == "unsubscribed":
            self._handleSubscription(message, False)
        else:
            self._onProtocolError("unknown motor message type: %s" % message_type)

    def _handleSubscription(self, message, subscribed):
        for canonical in message.get("motors", []):
            if canonical in self._remote_motor_keys:
                self._motors[canonical].applySubscription(subscribed)
                if subscribed and self.transport.is_ready:
                    # A state update and the subscription snapshot originate
                    # on different server sessions and can cross in flight.
                    # A cache STATUS request sent after the acknowledgement
                    # gives this proxy a final authoritative snapshot.
                    self._sendRemoteCommand(canonical, "status", {})

    def _handleRemoteState(self, message):
        canonical = message.get("motor")
        if canonical not in self._remote_motor_keys:
            # State for another owner/local motor must never mutate ours.
            return
        motor = self._motors[canonical]
        try:
            motor.applyState(
                message.get("status", "unknown"),
                message.get("position"),
                message.get("online", True),
            )
        except (TypeError, ValueError) as exc:
            self._onProtocolError(str(exc))

    def _handleRemoteAck(self, message):
        request_id = message.get("request_id")
        context = self._pending_remote.get(request_id)
        if context is not None and context["action"] != "status":
            self._motors[context["target"]].applyAck(request_id)

    def _handleRemoteResult(self, message):
        request_id = message.get("request_id")
        context = self._pending_remote.pop(request_id, None)
        if context is None:
            return
        target = context["target"]
        if message.get("motor") not in (None, target):
            self._onProtocolError("result target does not match request")
            return
        result_status = str(message.get("status", "failed")).lower()
        motor = self._motors[target]
        motor.applyResult(
            request_id,
            context["action"],
            result_status,
            message.get("position"),
        )
        if result_status != "completed":
            self._detectedError(
                "Remote request %s ended with %s." % (request_id, result_status)
            )
            self._clearOperationTracking(target, context["action"])

    def _handleRemoteError(self, message):
        request_id = message.get("request_id")
        context = self._pending_remote.pop(request_id, None)
        canonical = message.get("motor")
        if context is not None:
            canonical = context["target"]
        if canonical in self._remote_motor_keys:
            action = context["action"] if context is not None else None
            self._motors[canonical].applyError(
                request_id,
                message.get("code", "REMOTE_ERROR"),
                message.get("message", "Remote motor error"),
            )
            self._clearOperationTracking(canonical, action)
        else:
            self._detectedError(
                "Motor server error [%s]: %s" % (
                    message.get("code", "REMOTE_ERROR"),
                    message.get("message", "Unknown error"),
                )
            )

    def _handleExecute(self, message):
        request_id = message.get("request_id")
        local_nick = self._localFromExecuteTarget(message)
        action = str(message.get("action", "")).lower()
        if local_nick is None:
            # With a valid server this cannot occur.  We cannot publish an error
            # for an unregistered local id through the strict transport API.
            self._onProtocolError("execute target is not owned by this client")
            return
        if not request_id or action not in self._SUPPORTED_ACTIONS:
            self.transport.publish_error(
                request_id or "invalid-request",
                local_nick,
                "INVALID_COMMAND",
                "Unsupported motor action: %s" % action,
            )
            return

        motor = self._motors[local_nick]
        if action == "status":
            self.transport.publish_state(
                local_nick, motor.status, motor.position
            )
            self.transport.publish_result(
                request_id, local_nick, "completed", motor.position
            )
            return

        if action != "stop" and (
            local_nick in self._pending_local
            or motor.status in self._BUSY_STATES
            or motor.isBusy()
        ):
            self.transport.publish_error(
                request_id,
                local_nick,
                "BUSY",
                "Motor %s is busy." % local_nick,
            )
            return

        args = message.get("args") or {}
        target = args.get("position") if action == "move" else None
        self._pending_local[local_nick] = {
            "request_id": request_id,
            "action": action,
            "requester": message.get("requester"),
        }
        work = motor.toWorkList(
            action,
            target=target,
            request_id=request_id,
            requester=message.get("requester"),
        )
        if work is None:
            # Validation/STOP failures can synchronously emit
            # _localCommandError, which already publishes the correlated
            # error and removes the context.  Only provide a fallback if no
            # callback handled it.
            context = self._pending_local.pop(local_nick, None)
            if context is not None:
                self.transport.publish_error(
                    request_id,
                    local_nick,
                    "INVALID_ARGUMENT",
                    "Command could not be queued.",
                )

    def _sendRemoteCommand(self, target, action, args=None):
        if target not in self._remote_motor_keys:
            self._detectedError("Unknown remote motor: %s" % target)
            return None
        if not self.transport.is_ready:
            self._detectedError("Motor Server is not ready.")
            return None
        request_id = self.transport.send_command(target, action, args or {})
        if request_id is not None:
            self._pending_remote[request_id] = {
                "target": target,
                "action": str(action).lower(),
            }
        return request_id

    # ------------------------------------------------------------------
    # Local worker callbacks
    def _localStatusChanged(self, nick, status):
        if nick in self._local_motor_keys:
            motor = self._motors[nick]
            self.transport.publish_state(nick, status, motor.position)

    def _localPositionChanged(self, nick, position):
        if nick not in self._local_motor_keys:
            return
        self._sig_motors_positions.emit({nick: position})
        self.transport.publish_state(
            nick, self._motors[nick].status, position
        )

    def _remotePositionChanged(self, canonical, position):
        if canonical in self._remote_motor_keys:
            self._sig_motors_positions.emit({canonical: position})

    def _localCommandFinished(self, nick, action, request_id, result):
        if request_id is None:
            return
        context = self._pending_local.get(nick)
        if context is None or context["request_id"] != request_id:
            return
        self._pending_local.pop(nick, None)
        motor = self._motors[nick]
        self.transport.publish_state(nick, motor.status, motor.position)
        self.transport.publish_result(
            request_id, nick, "completed", motor.position
        )

    def _localCommandError(self, nick, action, request_id, message):
        if request_id is None:
            self._clearOperationTracking(nick, action)
            return
        context = self._pending_local.get(nick)
        if context is None or context["request_id"] != request_id:
            # A STOP pre-empts and replaces the active server request.  The
            # interrupted worker may finish unwinding afterwards; never report
            # that stale request as a new hardware failure.
            self._clearOperationTracking(nick, action)
            return
        self._pending_local.pop(nick, None)
        self.transport.publish_state(
            nick, self._motors[nick].status, self._motors[nick].position
        )
        self.transport.publish_error(
            request_id, nick, "HARDWARE_ERROR", message
        )
        self._clearOperationTracking(nick, action)

    def _initializedMotor(self, nick):
        motor_key = self._resolveMotorNick(nick)
        if motor_key is None:
            return
        if motor_key in self._motors_under_loading:
            self._motors_under_loading.remove(motor_key)
        self._sig_motors_initialized.emit(
            len(self._motors_under_loading), motor_key
        )
        self._sig_motors_positions.emit(
            {motor_key: self._motors[motor_key].position}
        )

    def _completedMotorMoving(self, nick, position):
        motor_key = self._resolveMotorNick(nick)
        if motor_key is None:
            return
        self._removeMovingMotor(motor_key)

    def _homedMotor(self, nick):
        motor_key = self._resolveMotorNick(nick)
        if motor_key is None:
            return
        if motor_key in self._motors_under_homing:
            self._motors_under_homing.remove(motor_key)
        self._removeMovingMotor(motor_key)

    def _removeMovingMotor(self, motor_key):
        while motor_key in self._motors_under_request:
            self._motors_under_request.remove(motor_key)

    def _clearOperationTracking(self, motor_key, action=None):
        self._removeMovingMotor(motor_key)
        if motor_key in self._motors_under_homing:
            self._motors_under_homing.remove(motor_key)
        if motor_key in self._motors_under_loading:
            self._motors_under_loading.remove(motor_key)
            self._sig_motors_initialized.emit(
                len(self._motors_under_loading), motor_key
            )

    def _detectedError(self, msg):
        if self.gui is not None and hasattr(self.gui, "toStatusBar"):
            self.gui.toStatusBar(str(msg))
        else:
            print("[MOTOR] %s" % msg)

    # ------------------------------------------------------------------
    # Public facade used by GUI, PMT aligner, scanner and shifter
    def getPosition(self, nickname):
        motor_key = self._resolveMotorNick(nickname)
        if motor_key is None:
            raise KeyError("Unknown motor: %s" % nickname)
        return self._motors[motor_key].getPosition()

    @staticmethod
    def _asMotorList(motor_list):
        if motor_list is None:
            return []
        if isinstance(motor_list, str):
            return [motor_list]
        return list(motor_list)

    def _remoteUsable(self, motor_key):
        motor = self._motors[motor_key]
        return self.transport.is_ready and motor.subscribed and motor.online

    def _rejectBusy(self, motor_key):
        motor = self._motors[motor_key]
        if not motor.isBusy():
            return False
        motor._sig_motor_error.emit("Motor %s is busy." % motor_key)
        return True

    def isRemoteMotorAvailable(self, nickname):
        motor_key = self._resolveMotorNick(nickname)
        return bool(
            motor_key in self._remote_motor_keys and self._remoteUsable(motor_key)
        )

    def connectRemoteMotors(self, motor_list=None, owner=None):
        if motor_list is None and owner is None:
            targets = sorted(self._remote_motor_keys)
        elif owner is not None:
            targets = [
                "%s:%s" % (owner, nick)
                for nick in self._remote_motor_owners.get(owner, [])
            ]
        else:
            targets = self._asMotorList(motor_list)
        targets = [target for target in targets if target in self._remote_motor_keys]
        if not targets:
            return False
        for target in targets:
            motor = self._motors[target]
            if not motor.online:
                motor.status = "subscribing"
        return self.transport.subscribe(targets)

    def releaseRemoteMotors(self, motor_list=None, owner=None):
        if motor_list is None and owner is None:
            targets = sorted(self._remote_motor_keys)
        elif owner is not None:
            targets = [
                "%s:%s" % (owner, nick)
                for nick in self._remote_motor_owners.get(owner, [])
            ]
        else:
            targets = self._asMotorList(motor_list)
        targets = [target for target in targets if target in self._remote_motor_keys]
        if not targets:
            return False
        result = self.transport.unsubscribe(targets)
        for target in targets:
            self._motors[target].applySubscription(False)
        return result

    # Backward-compatible name.  It now releases a subscription and never
    # sends a physical CLOSE command.
    disconnectRemoteMotors = releaseRemoteMotors

    def openDevice(self, motor_list):
        valid = []
        for requested in self._asMotorList(motor_list):
            motor_key = self._resolveMotorNick(requested)
            if motor_key is None:
                self._detectedError("Unknown motor: %s" % requested)
                continue
            if motor_key in self._remote_motor_keys and not self._remoteUsable(motor_key):
                self._detectedError("Remote motor is unavailable: %s" % motor_key)
                continue
            if self._rejectBusy(motor_key):
                continue
            valid.append(motor_key)
        self._sig_motors_initialized.emit(len(valid), "")
        for motor_key in valid:
            if motor_key not in self._motors_under_loading:
                self._motors_under_loading.append(motor_key)
            if self._motors[motor_key].toWorkList("open") is None:
                self._motors_under_loading.remove(motor_key)

    def moveToPosition(self, motor_dict):
        if not isinstance(motor_dict, dict):
            self._detectedError("Motor move request must be a dictionary.")
            return
        for requested, target in motor_dict.items():
            motor_key = self._resolveMotorNick(requested)
            if motor_key is None:
                self._detectedError("Unknown motor: %s" % requested)
                continue
            motor = self._motors[motor_key]
            if motor_key in self._remote_motor_keys and not self._remoteUsable(motor_key):
                self._detectedError("Remote motor is unavailable: %s" % motor_key)
                continue
            if self._rejectBusy(motor_key):
                continue
            if not motor._is_opened:
                self._detectedError("Motor is not opened yet: %s" % motor_key)
                continue
            work = motor.toWorkList("move", target=target)
            if work is None:
                continue
            if motor_key not in self._motors_under_request:
                self._motors_under_request.append(motor_key)
        if self._motors_under_request and not self.pos_checker.isActive():
            self.pos_checker.start(qtimer_interval)

    def homePosition(self, motor_list):
        for requested in self._asMotorList(motor_list):
            motor_key = self._resolveMotorNick(requested)
            if motor_key is None:
                self._detectedError("Unknown motor: %s" % requested)
                continue
            motor = self._motors[motor_key]
            if motor_key in self._remote_motor_keys and not self._remoteUsable(motor_key):
                self._detectedError("Remote motor is unavailable: %s" % motor_key)
                continue
            if self._rejectBusy(motor_key):
                continue
            if not motor._is_opened:
                self._detectedError("Motor is not opened yet: %s" % motor_key)
                continue
            if motor.toWorkList("home") is not None:
                if motor_key not in self._motors_under_homing:
                    self._motors_under_homing.append(motor_key)

    homeDevice = homePosition

    def closeDevice(self, motor_list=None):
        # A no-argument close is used by older application shutdown code.  Do
        # not close somebody else's physical motors in that case.
        targets = (
            sorted(self._local_motor_keys)
            if motor_list is None
            else self._asMotorList(motor_list)
        )
        for requested in targets:
            motor_key = self._resolveMotorNick(requested)
            if motor_key is None:
                self._detectedError("Unknown motor: %s" % requested)
                continue
            if motor_key in self._remote_motor_keys and not self._remoteUsable(motor_key):
                self._detectedError("Remote motor is unavailable: %s" % motor_key)
                continue
            if self._rejectBusy(motor_key):
                continue
            self._motors[motor_key].toWorkList("close")

    def stopMotor(self, nickname):
        motor_key = self._resolveMotorNick(nickname)
        if motor_key is None:
            self._detectedError("Unknown motor: %s" % nickname)
            return None
        if motor_key in self._remote_motor_keys and not self._remoteUsable(motor_key):
            self._detectedError("Remote motor is unavailable: %s" % motor_key)
            return None
        return self._motors[motor_key].toWorkList("stop")

    def stopMotors(self, motor_list):
        return [self.stopMotor(nick) for nick in self._asMotorList(motor_list)]

    def checkPositionsUnderMoving(self):
        positions = {}
        for motor_key in list(self._motors_under_request):
            motor = self._motors.get(motor_key)
            if motor is None:
                self._removeMovingMotor(motor_key)
                continue
            try:
                positions[motor_key] = motor.getPosition()
            except Exception as exc:
                self._detectedError("Could not read %s: %s" % (motor_key, exc))
        if positions:
            self._sig_motors_positions.emit(positions)
        if self._motors_under_request:
            self.pos_checker.start(qtimer_interval)

    def toWorkList(self, work):
        """Compatibility adapter for in-process legacy callers such as Shifter."""
        if not isinstance(work, (list, tuple)) or len(work) < 3:
            self._detectedError("Invalid legacy motor work item: %r" % (work,))
            return
        work_type = str(work[0]).upper()
        command = str(work[1]).upper()
        data = work[2]
        requester = work[3] if len(work) > 3 else None
        if work_type == "C":
            if command == "MOVE":
                self.moveToPosition(dict(zip(data[::2], data[1::2])))
            elif command == "OPEN":
                self.openDevice(data)
            elif command == "HOME":
                self.homePosition(data)
            elif command == "CLOSE":
                self.closeDevice(data)
            elif command == "STOP":
                self.stopMotors(data)
            elif command == "CON":
                self.connectRemoteMotors(data)
            elif command == "DCN":
                self.releaseRemoteMotors(data)
            else:
                self._detectedError("Unknown legacy motor command: %s" % command)
        elif work_type == "Q" and command in ("POS", "STATUS"):
            flat = []
            for requested in data:
                motor_key = self._resolveMotorNick(requested)
                if motor_key is None:
                    continue
                flat.extend((requested, self._motors[motor_key].getPosition()))
            if requester is not None and hasattr(requester, "toMessageList"):
                requester.toMessageList(["D", "MOTORS", command, flat])

    def run(self):
        # Kept only because old code may call it after _sig_remote_control.
        return

    def toSocket(self, msg):
        self._detectedError("Legacy DDS MOTOR socket output is disabled.")
        return False

    def shutdown(self):
        if self._shutting_down:
            return
        self._shutting_down = True
        self.pos_checker.stop()
        # Stop remote traffic first; local device cleanup is independent.
        self.transport.shutdown()
        for canonical in self._remote_motor_keys:
            self._motors[canonical].shutdown()
        for nick in self._local_motor_keys:
            self._motors[nick].shutdown(wait_ms=15000)
        self._pending_local.clear()
        self._pending_remote.clear()
