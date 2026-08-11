# -*- coding: utf-8 -*-
"""Wire helpers for the standalone motor-server protocol.

Frames are a four-byte, unsigned, big-endian payload length followed by one
UTF-8 JSON object.  This module deliberately does not import NumPy; scalar
objects such as ``numpy.float64`` are converted through their ``item`` method
before the JSON primitive check is applied.
"""

import json
import math
import struct


PROTOCOL_VERSION = 1
HEADER_SIZE = 4
DEFAULT_MAX_FRAME_SIZE = 1024 * 1024
MAX_JSON_DEPTH = 64


class ProtocolError(ValueError):
    """Raised when a frame or JSON value violates the motor protocol."""


def _validate_max_frame_size(max_frame_size):
    if type(max_frame_size) is not int or max_frame_size <= 0:
        raise ValueError("max_frame_size must be a positive integer")
    if max_frame_size > 0xFFFFFFFF:
        raise ValueError("max_frame_size exceeds the four-byte frame limit")
    return max_frame_size


def normalize_json_value(value, path="$", _active=None, _depth=0):
    """Return *value* as strict JSON primitives, normalizing scalar wrappers.

    Only ``dict``, ``list``, ``str``, ``int``, ``float``, ``bool`` and
    ``None`` are accepted.  Tuples, sets, bytes, arbitrary objects and
    non-finite floats are rejected.  An otherwise unsupported object gets one
    chance to expose a scalar with an ``item()`` method (the NumPy scalar API).
    """

    if _depth > MAX_JSON_DEPTH:
        raise ProtocolError("JSON nesting exceeds %d at %s" % (MAX_JSON_DEPTH, path))

    value_type = type(value)
    if value is None or value_type in (str, bool, int):
        return value

    if value_type is float:
        if not math.isfinite(value):
            raise ProtocolError("non-finite float at %s" % path)
        return value

    if _active is None:
        _active = set()

    if value_type is list:
        object_id = id(value)
        if object_id in _active:
            raise ProtocolError("circular list at %s" % path)
        _active.add(object_id)
        try:
            return [
                normalize_json_value(item, "%s[%d]" % (path, index), _active, _depth + 1)
                for index, item in enumerate(value)
            ]
        finally:
            _active.remove(object_id)

    if value_type is dict:
        object_id = id(value)
        if object_id in _active:
            raise ProtocolError("circular object at %s" % path)
        _active.add(object_id)
        try:
            normalized = {}
            for key, item in value.items():
                if type(key) is not str:
                    raise ProtocolError("JSON object key at %s must be a string" % path)
                normalized[key] = normalize_json_value(
                    item, "%s.%s" % (path, key), _active, _depth + 1
                )
            return normalized
        finally:
            _active.remove(object_id)

    item_method = getattr(value, "item", None)
    if callable(item_method):
        try:
            scalar = item_method()
        except Exception as exc:
            raise ProtocolError("could not normalize scalar at %s: %s" % (path, exc))
        if scalar is value:
            raise ProtocolError("item() returned the original object at %s" % path)
        return normalize_json_value(scalar, path, _active, _depth + 1)

    raise ProtocolError("unsupported JSON value %s at %s" % (value_type.__name__, path))


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ProtocolError("duplicate JSON object key: %s" % key)
        result[key] = value
    return result


def _reject_nonstandard_constant(value):
    raise ProtocolError("non-standard JSON constant: %s" % value)


def encode_frame(message, max_frame_size=DEFAULT_MAX_FRAME_SIZE):
    """Encode one protocol message into a complete length-prefixed frame."""

    max_frame_size = _validate_max_frame_size(max_frame_size)
    normalized = normalize_json_value(message)
    if type(normalized) is not dict:
        raise ProtocolError("a protocol message must be a JSON object")
    message_type = normalized.get("type")
    if type(message_type) is not str or not message_type.strip():
        raise ProtocolError("a protocol message requires a non-empty string 'type'")

    try:
        payload = json.dumps(
            normalized,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ProtocolError("could not encode JSON: %s" % exc)

    if not payload:
        raise ProtocolError("empty JSON payload")
    if len(payload) > max_frame_size:
        raise ProtocolError(
            "frame payload is %d bytes; limit is %d" % (len(payload), max_frame_size)
        )
    return struct.pack(">I", len(payload)) + payload


def decode_payload(payload, max_frame_size=DEFAULT_MAX_FRAME_SIZE):
    """Decode and validate one JSON payload (without the length header)."""

    max_frame_size = _validate_max_frame_size(max_frame_size)
    if not isinstance(payload, (bytes, bytearray, memoryview)):
        raise TypeError("payload must be bytes-like")
    payload = bytes(payload)
    if not payload:
        raise ProtocolError("empty frame payload")
    if len(payload) > max_frame_size:
        raise ProtocolError(
            "frame payload is %d bytes; limit is %d" % (len(payload), max_frame_size)
        )

    try:
        text = payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ProtocolError("payload is not valid UTF-8: %s" % exc)

    try:
        message = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonstandard_constant,
        )
    except ProtocolError:
        raise
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ProtocolError("invalid JSON payload: %s" % exc)

    message = normalize_json_value(message)
    if type(message) is not dict:
        raise ProtocolError("a protocol message must be a JSON object")
    message_type = message.get("type")
    if type(message_type) is not str or not message_type.strip():
        raise ProtocolError("a protocol message requires a non-empty string 'type'")
    return message


class FrameDecoder(object):
    """Incremental decoder for data received from a TCP byte stream."""

    def __init__(self, max_frame_size=DEFAULT_MAX_FRAME_SIZE):
        self.max_frame_size = _validate_max_frame_size(max_frame_size)
        self._buffer = bytearray()

    @property
    def buffered_bytes(self):
        return len(self._buffer)

    def reset(self):
        self._buffer.clear()

    def feed(self, data):
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise TypeError("data must be bytes-like")
        if data:
            self._buffer.extend(data)

        messages = []
        while len(self._buffer) >= HEADER_SIZE:
            payload_size = struct.unpack(">I", self._buffer[:HEADER_SIZE])[0]
            if payload_size == 0:
                self.reset()
                raise ProtocolError("zero-length frame")
            if payload_size > self.max_frame_size:
                self.reset()
                raise ProtocolError(
                    "declared frame size %d exceeds limit %d"
                    % (payload_size, self.max_frame_size)
                )

            frame_size = HEADER_SIZE + payload_size
            if len(self._buffer) < frame_size:
                break
            payload = bytes(self._buffer[HEADER_SIZE:frame_size])
            del self._buffer[:frame_size]
            messages.append(decode_payload(payload, self.max_frame_size))
        return messages


# Descriptive aliases used by some callers and tests.
encode_message = encode_frame
MotorFrameDecoder = FrameDecoder
