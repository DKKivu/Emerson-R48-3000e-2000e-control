"""Modal dialogs for the R48 controller UI."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from ..models import CANFrame


class RawFrameDialog(tk.Toplevel):
    """Small dialog for sending an arbitrary CAN frame.

    The dialog does not know about the controller; it receives a callable
    that performs the send (Dependency Inversion).
    """

    def __init__(
        self,
        parent: tk.Misc,
        send_callback: Callable[[CANFrame], None],
        log_callback: Callable[[str], None],
        default_id: int,
    ) -> None:
        super().__init__(parent)
        self._send = send_callback
        self._log = log_callback

        self.title("Send raw CAN frame")
        self.geometry("440x300")
        self.transient(parent)
        self.grab_set()

        ttk.Label(self, text="CAN ID (hex):").pack(pady=(10, 0))
        self._id_entry = ttk.Entry(self, width=20)
        self._id_entry.pack()
        self._id_entry.insert(0, f"{default_id:08X}")

        ttk.Label(self, text="Data (hex, space-separated):").pack(pady=(10, 0))
        self._data_entry = ttk.Entry(self, width=44)
        self._data_entry.pack()
        self._data_entry.insert(0, "03 F0 00 21 42 58 00 00")

        ttk.Label(
            self,
            text=(
                "Examples (big-endian float):\n"
                "  48 V online: 03 F0 00 21 42 40 00 00\n"
                "  54 V online: 03 F0 00 21 42 58 00 00\n"
                "  30 A online: 03 F0 00 22 3F 14 A3 D7\n"
                "  Read all:    00 F0 00 80 46 A5 34 00"
            ),
            justify="left",
            foreground="#555",
        ).pack(pady=(8, 0))

        ttk.Button(self, text="Send", command=self._on_send).pack(pady=14)

    def _on_send(self) -> None:
        try:
            can_id = int(self._id_entry.get(), 16)
            data = bytes.fromhex(self._data_entry.get().replace(" ", ""))
            if len(data) > 8:
                raise ValueError("Data must be 8 bytes or fewer")
            frame = CANFrame(can_id, data)
            self._send(frame)
            self._log(
                f"Raw frame sent: ID=0x{can_id:08X} "
                f"DATA={data.hex(' ').upper()}"
            )
            self.destroy()
        except Exception as exc:
            messagebox.showerror("Error", str(exc), parent=self)