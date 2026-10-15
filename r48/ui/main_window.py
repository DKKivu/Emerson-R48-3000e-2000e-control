"""Tkinter main window for the R48 controller.

The window owns a controller (which owns the transport). It knows nothing
about the wire format beyond the protocol constants exposed by the
controller for display purposes.
"""
from __future__ import annotations

import time
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

from ..config import AppConfig, CONFIG
from ..exceptions import ValidationError
from ..models import CANFrame, TelemetryValue
from ..protocol import R48Protocol
from ..transport import WaveshareSerialCAN, list_serial_ports
from ..controller import R48Controller
from .dialogs import RawFrameDialog
from ..settings import load_user_settings, save_user_settings


class R48Application(tk.Tk):
    CARDS = [
        (R48Protocol.PROP_VOUT, "Output voltage", "V"),
        (R48Protocol.PROP_IOUT, "Output current", "A"),
        ("power", "Output power", "W (calc.)"),
        (R48Protocol.PROP_ILIMIT, "Current limit", "A"),
        (R48Protocol.PROP_TEMP, "Temperature", "\u00b0C"),
        (R48Protocol.PROP_VIN, "Input voltage", "V"),
    ]

    ADDR_PRESETS = (
        ["Default (broadcast)"]
        + [f"0x{i:02X}" for i in range(0x00, 0x10)]
        + [f"0x{i:02X}" for i in range(0x10, 0x80, 0x10)]
        + ["0xFF (broadcast)"]
    )

    # --------------------------------------------------------
    # Construction
    # --------------------------------------------------------

    def __init__(self, config: Optional[AppConfig] = None) -> None:
        super().__init__()

        # Use YAML-backed config if available
        self.app_config = config or CONFIG
        self.controller: Optional[R48Controller] = None
        self._polling = False
        self._closing = False

        self.latest: dict = {}
        self.last_update: dict = {}
        self._hold_voltage: Optional[float] = None
        self._hold_current: Optional[float] = None

        self._target_address: Optional[int] = None
        self._discovered: set = set()

        self.title(self.app_config.title)
        self.geometry(f"{self.app_config.width}x{self.app_config.height}")
        self.minsize(980, 780)

        # load user settings
        user = load_user_settings()

        self._user_settings = user

        self._build_ui(user=user)

        self.after(self.app_config.gui_interval_ms, self._process_events)
        self.after(self.app_config.poll_interval_ms, self._poll_telemetry)
        self.after(self.app_config.keepalive_ms, self._keepalive)
        self.after(self.app_config.age_refresh_ms, self._refresh_ages)

        self.protocol("WM_DELETE_WINDOW", self._close)

    # --------------------------------------------------------
    # UI construction
    # --------------------------------------------------------

    def _build_ui(self, user: dict) -> None:
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)

        self._build_connection_panel(root, user=user)
        self._build_telemetry_panel(root)
        self._build_control_panel(root)
        self._build_tabs(root)

    def _build_connection_panel(self, root: ttk.Frame, user: dict) -> None:
        frame = ttk.LabelFrame(root, text="Adapter connection", padding=8)
        frame.pack(fill="x")

        ttk.Label(frame, text="COM port").grid(row=0, column=0, sticky="w")
        initial_port = user.get("last_port") or self.app_config.serial_port or ""
        self.port = tk.StringVar(value=initial_port)
        self.port_combo = ttk.Combobox(
            frame, textvariable=self.port, values=list_serial_ports(), width=12
        )
        self.port_combo.grid(row=0, column=1, padx=4)

        # Populate and pick a sensible default immediately so the UI shows a
        # usable port without requiring the user to press Refresh.
        try:
            ports = list_serial_ports()
            self.port_combo["values"] = ports
            if not initial_port and ports:
                self.port.set(ports[0])
        except Exception:
            # Be forgiving; the Refresh button still allows re-querying.
            pass

        ttk.Button(frame, text="Refresh", command=self._refresh_ports).grid(
            row=0, column=2, padx=4
        )

        ttk.Label(frame, text="USB baud").grid(row=0, column=3, padx=(12, 0))
        self.baud = tk.StringVar(value=str(self.app_config.serial_baud))
        ttk.Combobox(
            frame,
            textvariable=self.baud,
            values=("2000000", "1000000", "921600", "460800", "115200"),
            width=12,
        ).grid(row=0, column=4, padx=4)

        ttk.Label(frame, text="CAN bitrate").grid(row=0, column=5, padx=(12, 0))
        self.can_bitrate = tk.StringVar(value=str(self.app_config.can_bitrate))
        ttk.Combobox(
            frame,
            textvariable=self.can_bitrate,
            values=("1000000", "800000", "500000", "400000", "250000", "200000", "125000", "100000", "50000", "20000", "10000", "5000"),
            width=10,
        ).grid(row=0, column=6, padx=4)

        self.connect_btn = ttk.Button(frame, text="Connect", command=self._connect)
        self.connect_btn.grid(row=0, column=7, padx=4)
        self.disconnect_btn = ttk.Button(
            frame, text="Disconnect", command=self._disconnect, state="disabled"
        )
        self.disconnect_btn.grid(row=0, column=8, padx=4)

        ttk.Label(frame, text="Target PSU address").grid(
            row=1, column=0, sticky="w", pady=(8, 0)
        )

        # initial target from user settings
        last_target = user.get("last_target")
        if last_target is None:
            target_initial = "Default (broadcast)"
        else:
            try:
                target_initial = f"0x{int(last_target):02X}"
            except Exception:
                target_initial = "Default (broadcast)"

        self.target_address = tk.StringVar(value=target_initial)
        self.addr_combo = ttk.Combobox(
            frame, textvariable=self.target_address, values=list(self.ADDR_PRESETS), width=22
        )
        self.addr_combo.grid(row=1, column=1, columnspan=2, padx=4, pady=(8, 0))
        self.addr_combo.bind("<<ComboboxSelected>>", self._on_address_changed)
        self.addr_combo.bind("<Return>", self._on_address_changed)
        self.addr_combo.bind("<FocusOut>", self._on_address_changed)

        self.discovered_label = tk.StringVar(value="Discovered PSUs: (none yet)")
        ttk.Label(frame, textvariable=self.discovered_label, foreground="#555").grid(
            row=1, column=3, columnspan=6, sticky="w", padx=(12, 0), pady=(8, 0)
        )

        self.status = tk.StringVar(value="Disconnected")
        ttk.Label(frame, textvariable=self.status).grid(
            row=2, column=0, columnspan=9, sticky="w", pady=(8, 0)
        )

    def _build_telemetry_panel(self, root: ttk.Frame) -> None:
        frame = ttk.LabelFrame(root, text="Telemetry", padding=8)
        frame.pack(fill="x", pady=8)

        self.card_vars: dict = {}

        for column, (key, title, unit) in enumerate(self.CARDS):
            card = ttk.Frame(frame, relief="groove", padding=8)
            card.grid(row=0, column=column, sticky="nsew", padx=3)
            frame.columnconfigure(column, weight=1, uniform="cards")

            ttk.Label(card, text=title, anchor="center", wraplength=140).pack(fill="x")

            value = tk.StringVar(value="\u2014")
            ttk.Label(card, textvariable=value, font=("Segoe UI", 16, "bold"), anchor="center").pack(
                fill="x", pady=4
            )
            ttk.Label(card, text=unit, anchor="center").pack(fill="x")

            info = tk.StringVar(value="")
            ttk.Label(card, textvariable=info, anchor="center", foreground="#555").pack(fill="x")

            age = tk.StringVar(value="")
            ttk.Label(card, textvariable=age, anchor="center", foreground="#888").pack(fill="x")

            self.card_vars[key] = (value, info, age)

    def _build_control_panel(self, root: ttk.Frame) -> None:
        controls = ttk.LabelFrame(root, text="Rectifier control", padding=10)
        controls.pack(fill="x")

        pc = R48Protocol

        ttk.Label(
            controls,
            text=f"Output voltage ({pc.VOLTAGE_MIN}\u2013{pc.VOLTAGE_MAX} V)",
        ).grid(row=0, column=0, sticky="w")
        self.voltage = tk.StringVar(value="54.0")
        ttk.Entry(controls, textvariable=self.voltage, width=12).grid(row=0, column=1, padx=6, pady=5)
        ttk.Button(controls, text="Set voltage (online)", command=lambda: self._set_voltage(False)).grid(
            row=0, column=2, padx=5
        )
        ttk.Button(controls, text="Set voltage (permanent)", command=lambda: self._set_voltage(True)).grid(
            row=0, column=3, padx=5
        )

        ttk.Label(
            controls,
            text=f"Current limit ({pc.CURRENT_MIN}\u2013{pc.CURRENT_MAX} A)",
        ).grid(row=1, column=0, sticky="w")
        self.current = tk.StringVar(value="30.0")
        ttk.Entry(controls, textvariable=self.current, width=12).grid(row=1, column=1, padx=6, pady=5)
        ttk.Button(controls, text="Set current (online)", command=lambda: self._set_current(False)).grid(
            row=1, column=2, padx=5
        )
        ttk.Button(controls, text="Set current (permanent)", command=lambda: self._set_current(True)).grid(
            row=1, column=3, padx=5
        )

        self.hold = tk.BooleanVar(value=True)
        ttk.Checkbutton(controls, text="Hold online setpoints (re-send every 10 s)", variable=self.hold).grid(
            row=2, column=0, columnspan=4, sticky="w"
        )

        self.auto_poll = tk.BooleanVar(value=True)
        ttk.Checkbutton(controls, text="Automatic telemetry polling (1 second)", variable=self.auto_poll).grid(
            row=3, column=0, columnspan=4, sticky="w"
        )

        ttk.Button(controls, text="Request telemetry now", command=self._request_telemetry).grid(
            row=4, column=0, columnspan=2, sticky="ew", pady=5
        )
        ttk.Button(controls, text="Send raw CAN frame\u2026", command=self._open_raw_sender).grid(
            row=4, column=2, columnspan=2, sticky="ew", pady=5
        )

        fan_frame = ttk.LabelFrame(controls, text="Fan / indicator", padding=6)
        fan_frame.grid(row=0, column=4, rowspan=5, padx=(18, 0), sticky="ns")

        self.fan_full = tk.BooleanVar(value=False)
        self.flash_led = tk.BooleanVar(value=False)

        ttk.Button(fan_frame, text="Fan: Auto", command=lambda: self._set_fan(False)).pack(fill="x", pady=3)
        ttk.Button(fan_frame, text="Fan: Full speed", command=lambda: self._set_fan(True)).pack(fill="x", pady=3)

        self.fan_state = tk.StringVar(value="Fan mode: Auto")
        ttk.Label(fan_frame, textvariable=self.fan_state).pack(pady=(4, 2))

        ttk.Checkbutton(fan_frame, text="Flash locate LED", variable=self.flash_led, command=self._send_control_now).pack(anchor="w", pady=3)

    def _build_tabs(self, root: ttk.Frame) -> None:
        notebook = ttk.Notebook(root)
        notebook.pack(fill="both", expand=True, pady=(8, 0))

        log_tab = ttk.Frame(notebook, padding=6)
        notebook.add(log_tab, text="Diagnostic log")
        self.log = tk.Text(log_tab, height=10, wrap="none", state="disabled", font=("Consolas", 9))
        scrollbar = ttk.Scrollbar(log_tab, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=scrollbar.set)
        self.log.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        props_tab = ttk.Frame(notebook, padding=6)
        notebook.add(props_tab, text="Other properties")

        bar = ttk.Frame(props_tab)
        bar.pack(fill="x")
        ttk.Button(bar, text="Scan properties 0x06\u20130x3F (read-only)", command=self._scan_properties).pack(side="left")
        ttk.Button(bar, text="Clear", command=self._clear_unknown).pack(side="left", padx=6)

        columns = ("id", "src", "float", "raw", "age")
        self.unknown_tree = ttk.Treeview(props_tab, columns=columns, show="headings", height=8)
        for col, title, width in (
            ("id", "Property", 80),
            ("src", "Source", 70),
            ("float", "Value (big-endian float)", 180),
            ("raw", "Raw frame", 240),
            ("age", "Updated", 90),
        ):
            self.unknown_tree.heading(col, text=title)
            self.unknown_tree.column(col, width=width, anchor="w")
        self.unknown_tree.pack(fill="both", expand=True, pady=(6, 0))

        ttk.Button(root, text="Clear log", command=self._clear_log).pack(anchor="e", pady=(5, 0))

    # --------------------------------------------------------
    # Connection
    # --------------------------------------------------------

    def _refresh_ports(self) -> None:
        ports = list_serial_ports()
        self.port_combo["values"] = ports
        if ports and self.port.get() not in ports:
            self.port.set(ports[0])

    def _connect(self) -> None:
        if self.controller is not None:
            return

        try:
            port = self.port.get().strip()
            baud = int(self.baud.get())
            bitrate = int(self.can_bitrate.get())
            if not port:
                raise ValidationError("Select a COM port")

            address = self._parse_address(self.target_address.get())
            self._target_address = address

            transport = WaveshareSerialCAN(port=port, baud=baud, bitrate=bitrate)
            self.controller = R48Controller(transport)
            self.controller.set_target_address(address)
            self.controller.connect()

            self.connect_btn.configure(state="disabled")
            self.disconnect_btn.configure(state="normal")
            self._polling = True

            self._log(
                f"Connected. Target PSU: {self._format_address(address)}. Setpoints use big-endian floats."
            )

            # persist last-used port and target
            try:
                save_user_settings({"last_port": port, "last_target": self._target_address})
            except Exception:
                pass

        except Exception as exc:
            self._log(f"CONNECT ERROR: {exc}")
            self.controller = None
            messagebox.showerror("Connection failed", str(exc))

    def _disconnect(self) -> None:
        self._polling = False
        self._hold_voltage = None
        self._hold_current = None

        controller, self.controller = self.controller, None
        if controller is not None:
            try:
                controller.disconnect()
            except Exception as exc:
                self._log(f"DISCONNECT ERROR: {exc}")

        self.connect_btn.configure(state="normal")
        self.disconnect_btn.configure(state="disabled")
        self.status.set("Disconnected")

    # --------------------------------------------------------
    # Target address
    # --------------------------------------------------------

    @staticmethod
    def _format_address(address: Optional[int]) -> str:
        return "Default (broadcast)" if address is None else f"0x{address:02X}"

    def _parse_address(self, text: str) -> Optional[int]:
        text = text.strip()
        if not text or text.lower().startswith("default"):
            return None
        if text.lower().startswith("0x"):
            text = text[2:]
        text = text.split()[0]
        try:
            value = int(text, 16)
        except ValueError:
            raise ValidationError(f"Cannot parse address: {text!r}")
        if not 0 <= value <= 0xFF:
            raise ValidationError("Address must be 0x00..0xFF")
        return value

    def _on_address_changed(self, _event=None) -> None:
        try:
            address = self._parse_address(self.target_address.get())
        except ValidationError as exc:
            messagebox.showerror("Invalid address", str(exc))
            self.target_address.set(self._format_address(self._target_address))
            return

        if address == self._target_address:
            return

        self._target_address = address
        if self.controller is not None:
            try:
                self.controller.set_target_address(address)
            except Exception as exc:
                self._log(f"ADDRESS ERROR: {exc}")

        self._hold_voltage = None
        self._hold_current = None

        for value_var, info_var, age_var in self.card_vars.values():
            value_var.set("\u2014")
            info_var.set("")
            age_var.set("")
        self.latest.clear()
        self.last_update.clear()
        self._clear_unknown()

        shown = self._format_address(address)
        self._log(f"Target PSU address set to {shown}")
        self.status.set(f"Target PSU: {shown}")

        # persist last-used port and target
        try:
            save_user_settings({"last_port": self.port.get(), "last_target": self._target_address})
        except Exception:
            pass

    def _refresh_discovered_label(self) -> None:
        if not self._discovered:
            self.discovered_label.set("Discovered PSUs: (none yet)")
            return
        items = ", ".join(f"0x{n:02X}" for n in sorted(self._discovered))
        self.discovered_label.set(f"Discovered PSUs: {items}")

    # --------------------------------------------------------
    # Commands
    # --------------------------------------------------------

    def _require_controller(self) -> bool:
        if self.controller is None:
            messagebox.showwarning("Not connected", "Connect the adapter first")
            return False
        return True

    def _perform(self, operation) -> bool:
        if not self._require_controller():
            return False
        try:
            operation()
            return True
        except Exception as exc:
            self._log(f"OPERATION ERROR: {exc}")
            messagebox.showerror("Operation failed", str(exc))
            return False

    def _request_telemetry(self) -> None:
        self._perform(lambda: self.controller.request_telemetry())

    def _set_voltage(self, permanent: bool) -> None:
        try:
            value = float(self.voltage.get())
        except ValueError:
            messagebox.showerror("Invalid voltage", "Enter a valid number")
            return

        mode = "PERMANENTLY" if permanent else "online (temporary)"
        target = self._format_address(self._target_address)
        if not messagebox.askyesno("Confirm voltage", f"Set voltage to {value:.2f} V {mode} on PSU {target}?"):
            return

        if self._perform(lambda: self.controller.set_voltage(value, permanent)):
            self._hold_voltage = None if permanent else value

    def _set_current(self, permanent: bool) -> None:
        try:
            value = float(self.current.get())
        except ValueError:
            messagebox.showerror("Invalid current", "Enter a valid number")
            return

        mode = "PERMANENTLY" if permanent else "online (temporary)"
        target = self._format_address(self._target_address)
        if not messagebox.askyesno("Confirm current", f"Set current limit to {value:.2f} A {mode} on PSU {target}?"):
            return

        if self._perform(lambda: self.controller.set_current(value, permanent)):
            self._hold_current = None if permanent else value

    def _set_fan(self, full_speed: bool) -> None:
        self.fan_full.set(full_speed)
        self._send_control_now()

    def _send_control_now(self) -> None:
        full = self.fan_full.get()
        flash = self.flash_led.get()
        if self._perform(lambda: self.controller.send_control(full, flash)):
            self.fan_state.set("Fan mode: FULL SPEED" if full else "Fan mode: Auto")

    def _open_raw_sender(self) -> None:
        if not self._require_controller():
            return
        RawFrameDialog(parent=self, send_callback=self.controller.send_raw, log_callback=self._log, default_id=R48Protocol.DEFAULT_TX_ID)

    def _scan_properties(self) -> None:
        if not self._require_controller():
            return
        self._log("Scanning properties 0x06..0x3F (read-only)")
        for index, pid in enumerate(range(0x06, 0x40)):
            self.after(index * self.app_config.scan_spacing_ms, lambda p=pid: self._scan_one(p))

    def _scan_one(self, pid: int) -> None:
        if self.controller is None or self._closing:
            return
        try:
            self.controller.request_property(pid)
        except Exception as exc:
            self._log(f"SCAN ERROR: {exc}")

    # --------------------------------------------------------
    # Event loop
    # --------------------------------------------------------

    def _process_events(self) -> None:
        if self._closing:
            return

        if self.controller is not None:
            for kind, payload in self.controller.drain_events(self.app_config.max_events_per_cycle):
                if kind == "log":
                    self._log(payload)
                elif kind == "status":
                    self.status.set(payload)
                elif kind == "error":
                    self._log(f"ERROR: {payload}")
                    self.status.set("Communication error \u2014 see log")
                elif kind == "can_rx":
                    self._handle_rx(payload)

        try:
            self.after(self.app_config.gui_interval_ms, self._process_events)
        except tk.TclError:
            pass

    def _handle_rx(self, frame: CANFrame) -> None:
        source = R48Controller.source_address(frame)
        if source is not None and source not in self._discovered:
            self._discovered.add(source)
            self._refresh_discovered_label()
            self._log(f"Discovered PSU at address 0x{source:02X}")

        if self._target_address is not None and source is not None:
            if source != self._target_address:
                return

        telemetry = self.controller.decode(frame)
        if telemetry is not None:
            self._handle_telemetry(telemetry)

    def _handle_telemetry(self, t: TelemetryValue) -> None:
        self.latest[t.property_id] = t
        self.last_update[t.property_id] = t.received_at

        if not t.known:
            self._update_unknown(t)
            return

        value_var, info_var, _ = self.card_vars[t.property_id]

        if t.property_id == R48Protocol.PROP_ILIMIT:
            amps = R48Protocol.fraction_to_amps(t.value)
            value_var.set(f"{amps:.1f}")
            info_var.set(f"raw {t.value:.4f} = {t.value * 100:.1f} %")
        elif t.property_id == R48Protocol.PROP_TEMP:
            value_var.set(f"{t.value:.1f}")
        else:
            value_var.set(f"{t.value:.2f}")

        self._update_power()

    def _update_power(self) -> None:
        vout = self.latest.get(R48Protocol.PROP_VOUT)
        iout = self.latest.get(R48Protocol.PROP_IOUT)
        value_var, info_var, _ = self.card_vars["power"]
        if vout is None or iout is None:
            return
        value_var.set(f"{vout.value * iout.value:.0f}")
        info_var.set("Vout \u00d7 Iout")

    def _update_unknown(self, t: TelemetryValue) -> None:
        src = t.source_address
        src_str = f"0x{src:02X}" if src is not None else "?"
        iid = f"{src_str}_{t.property_id:02X}"
        values = (
            f"0x{t.property_id:02X}",
            src_str,
            f"{t.value:.6g}",
            t.raw.hex(" ").upper(),
            time.strftime("%H:%M:%S"),
        )
        if self.unknown_tree.exists(iid):
            self.unknown_tree.item(iid, values=values)
        else:
            self.unknown_tree.insert("", "end", iid=iid, values=values)

    def _clear_unknown(self) -> None:
        for item in self.unknown_tree.get_children():
            self.unknown_tree.delete(item)

    def _refresh_ages(self) -> None:
        if self._closing:
            return

        now = time.time()
        for key, (_value, _info, age_var) in self.card_vars.items():
            if key == "power":
                times = [
                    self.last_update.get(R48Protocol.PROP_VOUT),
                    self.last_update.get(R48Protocol.PROP_IOUT),
                ]
                if None in times:
                    continue
                last = min(times)
            else:
                last = self.last_update.get(key)
                if last is None:
                    continue

            age = now - last
            age_var.set(
                "STALE \u2014 no reply"
                if age > self.app_config.stale_after_s
                else f"{age:.1f} s ago"
            )

        try:
            self.after(self.app_config.age_refresh_ms, self._refresh_ages)
        except tk.TclError:
            pass

    # --------------------------------------------------------
    # Periodic tasks
    # --------------------------------------------------------

    def _poll_telemetry(self) -> None:
        if self._closing:
            return
        if self._polling and self.auto_poll.get() and self.controller is not None:
            try:
                self.controller.request_telemetry()
            except Exception as exc:
                self._log(f"POLL ERROR: {exc}")
        try:
            self.after(self.app_config.poll_interval_ms, self._poll_telemetry)
        except tk.TclError:
            pass

    def _keepalive(self) -> None:
        if self._closing:
            return

        if self._polling and self.controller is not None and self.hold.get():
            try:
                if self._hold_voltage is not None:
                    self.controller.set_voltage(self._hold_voltage, permanent=False)
                if self._hold_current is not None:
                    self.controller.set_current(self._hold_current, permanent=False)
                if self.fan_full.get() or self.flash_led.get():
                    self.controller.send_control(self.fan_full.get(), self.flash_led.get())
            except Exception as exc:
                self._log(f"KEEP-ALIVE ERROR: {exc}")

        try:
            self.after(self.app_config.keepalive_ms, self._keepalive)
        except tk.TclError:
            pass

    # --------------------------------------------------------
    # Logging / shutdown
    # --------------------------------------------------------

    def _log(self, message: str) -> None:
        try:
            self.log.configure(state="normal")
            self.log.insert("end", f"{time.strftime('%H:%M:%S')} {message}\n")
            self.log.see("end")
            lines = int(self.log.index("end-1c").split("." )[0])
            if lines > self.app_config.max_log_lines:
                keep = self.app_config.max_log_lines
                self.log.delete("1.0", f"{lines - keep}.0")
            self.log.configure(state="disabled")
        except tk.TclError:
            pass

    def _clear_log(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _close(self) -> None:
        self._closing = True
        self._polling = False

        # persist current settings
        try:
            save_user_settings({"last_port": self.port.get(), "last_target": self._target_address})
        except Exception:
            pass

        controller, self.controller = self.controller, None
        if controller is not None:
            try:
                controller.disconnect()
            except Exception:
                pass
        self.destroy()
