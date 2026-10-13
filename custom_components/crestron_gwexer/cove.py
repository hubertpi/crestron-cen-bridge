"""Exact Cove mapping correlated in scene and local-switch captures.

Only the shared 0x14 feedback signal is used for state. The other signals
and the local-only 0x1d packet are deliberately not assigned semantics.
"""

COVE_ON = bytes.fromhex("05000e00000b200308200105140000ffff")
COVE_OFF = bytes.fromhex("05000e00000b2003082001051400000000")
_FEEDBACK_PREFIX = bytes.fromhex("05000c0000092003062001030014")


def cove_feedback(frame):
    """Return captured on/off feedback, or None for every other frame."""
    if frame == _FEEDBACK_PREFIX + b"\x00":
        return True
    if frame == _FEEDBACK_PREFIX + b"\x80":
        return False
    return None
