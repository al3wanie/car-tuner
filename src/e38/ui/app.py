"""E38 Tuner — Main Textual Application."""

import os
import sys
import logging

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Header, Footer, Static, Button, Label,
    DataTable, Input, Select, ProgressBar, Switch,
    TabbedContent, TabPane, RichLog, ListView, ListItem,
)
from textual.screen import Screen
from textual import on

from rich.text import Text
from rich.panel import Panel
from rich.table import Table as RichTable

from ..comm.j2534 import J2534, discover_j2534_devices
from ..comm.gmlan import GMLAN
from ..comm.obdlink import OBDLinkAdapter, find_obdlink_ports
from ..flash.reader import read_calibration, read_full_flash
from ..flash.writer import write_calibration
from ..flash.backup import create_backup, list_backups, load_backup, verify_backup
from ..calibration.binary import load_bin, save_bin, sha256
from ..calibration.parameters import CalibrationEditor
from ..calibration.tables import Table2D, Table1D
from ..definitions.base_e38 import PARAMS, TABLES, BITS
from ..definitions.dtc_codes import DTCS
from ..exceptions import E38Error

log = logging.getLogger(__name__)

# Project root for backups
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class HomeScreen(Screen):
    """Main dashboard screen."""

    BINDINGS = [
        Binding("c", "connect", "Connect J2534"),
        Binding("b", "connect_bt", "Connect OBDLink"),
        Binding("o", "open_file", "Open .bin"),
        Binding("d", "demo_mode", "Demo Mode"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="home-container"):
            yield Static(
                Panel(
                    "[bold red]E38 ECU Tuner[/bold red]\n"
                    "[dim]Professional LS Engine Tuning Tool[/dim]\n\n"
                    "[bold white]v1.0.0[/bold white]",
                    title="E38 Tuner",
                    border_style="red",
                ),
                id="banner",
            )
            with Horizontal(id="home-buttons"):
                yield Button("J2534 Connect [C]", id="btn-connect", variant="primary")
                yield Button("OBDLink BT [B]", id="btn-obdlink", variant="success")
                yield Button("Open .bin [O]", id="btn-open", variant="default")
                yield Button("Demo Mode [D]", id="btn-demo", variant="warning")
            yield Static("", id="ecu-info")
            yield Static(
                "[dim]C = J2534 adapter | B = OBDLink MX+ Bluetooth | "
                "O = Open .bin file | D = Demo mode[/dim]",
                id="home-hint",
            )
        yield Footer()

    @on(Button.Pressed, "#btn-connect")
    def action_connect(self):
        self.app.push_screen(ConnectScreen())

    @on(Button.Pressed, "#btn-obdlink")
    def action_connect_bt(self):
        self.app.push_screen(OBDLinkScreen())

    @on(Button.Pressed, "#btn-open")
    def action_open_file(self):
        self.app.push_screen(FileOpenScreen())

    @on(Button.Pressed, "#btn-demo")
    def action_demo_mode(self):
        # Create synthetic calibration for testing
        demo_data = bytearray(262144)  # 256KB of zeros
        self.app.editor = CalibrationEditor(demo_data, PARAMS, TABLES, BITS, DTCS)
        self.app.ecu_info = {
            "vin": "DEMO_MODE",
            "calibration_id": "DEMO_12345678",
            "os_id": "DEMO_OS",
            "hardware_number": "E38_DEMO",
            "battery_voltage": 14.2,
        }
        self.app.push_screen(TuningScreen())


class ConnectScreen(Screen):
    """J2534 device connection screen."""

    BINDINGS = [Binding("escape", "app.pop_screen", "Back")]

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="connect-container"):
            yield Static("[bold]Scanning for J2534 devices...[/bold]", id="scan-status")
            yield ListView(id="device-list")
            yield Button("Refresh", id="btn-refresh", variant="default")
            yield Static("", id="connect-log")
        yield Footer()

    def on_mount(self):
        self._scan_devices()

    def _scan_devices(self):
        devices = discover_j2534_devices()
        listview = self.query_one("#device-list", ListView)
        listview.clear()

        if not devices:
            self.query_one("#scan-status", Static).update(
                "[yellow]No J2534 devices found.[/yellow]\n"
                "Install a J2534 driver (Tactrix, VXDIAG, etc.)"
            )
            return

        self.query_one("#scan-status", Static).update(
            f"[green]Found {len(devices)} device(s):[/green]"
        )
        self.app._j2534_devices = devices
        for i, dev in enumerate(devices):
            listview.append(
                ListItem(Label(f"{dev['name']} ({dev['vendor']})"), id=f"dev-{i}")
            )

    @on(Button.Pressed, "#btn-refresh")
    def refresh_devices(self):
        self._scan_devices()

    @on(ListView.Selected, "#device-list")
    def on_device_selected(self, event):
        idx = int(event.item.id.split("-")[1])
        dev = self.app._j2534_devices[idx]
        log_widget = self.query_one("#connect-log", Static)

        log_widget.update(f"[yellow]Connecting to {dev['name']}...[/yellow]")

        try:
            j2534 = J2534()
            j2534.open(dev["dll_path"], dev["name"])
            j2534.connect()

            gmlan = GMLAN(j2534)
            gmlan.start_diagnostic_session()

            ecu_info = gmlan.read_ecu_info()

            self.app._j2534 = j2534
            self.app._gmlan = gmlan
            self.app.ecu_info = ecu_info

            log_widget.update(
                f"[green]Connected![/green]\n"
                f"VIN: {ecu_info['vin']}\n"
                f"Calibration: {ecu_info['calibration_id']}\n"
                f"OS: {ecu_info['os_id']}\n"
                f"Battery: {ecu_info['battery_voltage']:.1f}V"
            )

            # Auto-proceed to read screen
            self.app.push_screen(ReadFlashScreen())

        except E38Error as e:
            log_widget.update(f"[red]Connection failed: {e}[/red]")
        except Exception as e:
            log_widget.update(f"[red]Error: {e}[/red]")


class OBDLinkScreen(Screen):
    """OBDLink MX+ Bluetooth connection screen."""

    BINDINGS = [Binding("escape", "app.pop_screen", "Back")]

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll(id="obdlink-container"):
            yield Static(
                "[bold]OBDLink MX+ Connection[/bold]\n\n"
                "[green]SAFE:[/green] Reading ECU calibration over Bluetooth\n"
                "[red]RISKY:[/red] Writing/flashing over Bluetooth — use J2534 for flashing\n",
                id="obdlink-info",
            )
            yield Static("[yellow]Scanning serial ports...[/yellow]", id="bt-scan-status")
            yield ListView(id="port-list")
            yield Static("[dim]Or enter COM port manually:[/dim]")
            yield Input(placeholder="COM port (e.g., COM5)", id="com-input")
            yield Button("Connect", id="btn-bt-connect", variant="primary")
            yield Static("", id="bt-log")
        yield Footer()

    def on_mount(self):
        self._scan_ports()

    def _scan_ports(self):
        ports = find_obdlink_ports()
        listview = self.query_one("#port-list", ListView)
        listview.clear()

        if not ports:
            self.query_one("#bt-scan-status", Static).update(
                "[yellow]No serial ports found.[/yellow]\n"
                "Make sure OBDLink MX+ is paired via Bluetooth Settings.\n"
                "Enter the COM port manually below."
            )
            return

        self.query_one("#bt-scan-status", Static).update(
            f"[green]Found {len(ports)} port(s):[/green]"
        )
        self.app._bt_ports = ports
        for i, p in enumerate(ports):
            listview.append(
                ListItem(Label(f"{p['port']} — {p['description']}"), id=f"port-{i}")
            )

    @on(ListView.Selected, "#port-list")
    def on_port_selected(self, event):
        idx = int(event.item.id.split("-")[1])
        port = self.app._bt_ports[idx]["port"]
        self._connect_port(port)

    @on(Button.Pressed, "#btn-bt-connect")
    def on_manual_connect(self):
        port = self.query_one("#com-input", Input).value.strip()
        if port:
            self._connect_port(port)

    def _connect_port(self, port):
        log_widget = self.query_one("#bt-log", Static)
        log_widget.update(f"[yellow]Connecting to {port}...[/yellow]")

        try:
            adapter = OBDLinkAdapter()
            adapter.connect(port)

            ecu_info = adapter.read_ecu_info()

            self.app._obdlink = adapter
            self.app.ecu_info = ecu_info
            self.app._connection_type = "obdlink"

            log_widget.update(
                f"[green]Connected via OBDLink![/green]\n"
                f"Device: {adapter.device_name}\n"
                f"Firmware: {adapter.firmware_version}\n"
                f"VIN: {ecu_info['vin']}\n"
                f"Calibration: {ecu_info['calibration_id']}\n"
                f"Battery: {ecu_info['battery_voltage']:.1f}V"
            )

            self.app.push_screen(OBDLinkReadScreen())

        except Exception as e:
            log_widget.update(f"[red]Connection failed: {e}[/red]")


class OBDLinkReadScreen(Screen):
    """Read ECU via OBDLink."""

    BINDINGS = [Binding("escape", "app.pop_screen", "Back")]

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            yield Static(
                "[bold]Read ECU via OBDLink MX+[/bold]\n\n"
                "[green]Reading is SAFE over Bluetooth.[/green]\n"
                "This will read the 256KB calibration (~3-5 min over BT).",
            )
            yield ProgressBar(total=100, id="bt-read-progress", show_eta=True)
            yield Button("Read Calibration", id="btn-bt-read", variant="primary")
            yield Static("", id="bt-read-status")
        yield Footer()

    @on(Button.Pressed, "#btn-bt-read")
    def read_cal(self):
        status = self.query_one("#bt-read-status", Static)
        progress = self.query_one("#bt-read-progress", ProgressBar)
        adapter = self.app._obdlink

        def update(done, total):
            pct = int(done / total * 100)
            progress.update(progress=pct)
            status.update(f"Reading... {done}/{total} bytes ({pct}%)")

        try:
            status.update("[yellow]Reading calibration from ECU...[/yellow]")
            cal_data = adapter.read_calibration(progress_cb=update)

            # Auto-backup
            backup_path, _ = create_backup(cal_data, self.app.ecu_info, PROJECT_ROOT)
            status.update(
                f"[green]Read complete! {len(cal_data)} bytes[/green]\n"
                f"Backup: {backup_path}"
            )

            self.app.editor = CalibrationEditor(cal_data, PARAMS, TABLES, BITS, DTCS)
            self.app.push_screen(TuningScreen())

        except Exception as e:
            status.update(f"[red]Read failed: {e}[/red]")


class FileOpenScreen(Screen):
    """Screen for opening a .bin file for offline editing."""

    BINDINGS = [Binding("escape", "app.pop_screen", "Back")]

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            yield Static("[bold]Open Calibration File[/bold]")
            yield Input(placeholder="Path to .bin file (e.g., backups/e38/file.bin)", id="file-path")
            yield Button("Open", id="btn-open-file", variant="primary")
            yield Static("", id="file-status")
            yield Static("\n[bold]Saved Backups:[/bold]", id="backup-header")
            yield ListView(id="backup-list")
        yield Footer()

    def on_mount(self):
        backups = list_backups(PROJECT_ROOT)
        listview = self.query_one("#backup-list", ListView)
        self.app._backup_list = backups

        for i, b in enumerate(backups):
            label = f"{b.get('filename', '?')} — {b.get('vin', '?')} ({b.get('timestamp', '?')})"
            listview.append(ListItem(Label(label), id=f"backup-{i}"))

    @on(Button.Pressed, "#btn-open-file")
    def open_file(self):
        path = self.query_one("#file-path", Input).value.strip()
        self._load_file(path)

    @on(ListView.Selected, "#backup-list")
    def on_backup_selected(self, event):
        idx = int(event.item.id.split("-")[1])
        backup = self.app._backup_list[idx]
        self._load_file(backup["bin_path"])

    def _load_file(self, path):
        status = self.query_one("#file-status", Static)
        try:
            data = load_bin(path)
            if len(data) == 262144:
                status.update(f"[green]Loaded calibration: {len(data)} bytes[/green]")
            elif len(data) == 2097152:
                # Extract calibration section from full flash
                data = data[0x1C0000:0x200000]
                status.update(f"[green]Loaded full flash, extracted calibration: {len(data)} bytes[/green]")
            else:
                status.update(f"[yellow]Warning: unexpected size {len(data)} bytes. Proceeding anyway.[/yellow]")

            self.app.editor = CalibrationEditor(data, PARAMS, TABLES, BITS, DTCS)
            self.app.ecu_info = {
                "vin": "Offline",
                "calibration_id": os.path.basename(path),
                "os_id": "File",
                "hardware_number": "E38",
                "battery_voltage": 0,
            }
            self.app.loaded_file = path
            self.app.push_screen(TuningScreen())

        except FileNotFoundError:
            status.update(f"[red]File not found: {path}[/red]")
        except Exception as e:
            status.update(f"[red]Error loading file: {e}[/red]")


class ReadFlashScreen(Screen):
    """Flash read progress screen."""

    BINDINGS = [Binding("escape", "app.pop_screen", "Back")]

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            yield Static("[bold]Read ECU Calibration[/bold]")
            yield Static("", id="read-status")
            yield ProgressBar(total=100, id="read-progress", show_eta=True)
            with Horizontal():
                yield Button("Read Calibration (256KB)", id="btn-read-cal", variant="primary")
                yield Button("Read Full Flash (2MB)", id="btn-read-full", variant="warning")
        yield Footer()

    @on(Button.Pressed, "#btn-read-cal")
    def read_cal(self):
        self._read(full=False)

    @on(Button.Pressed, "#btn-read-full")
    def read_full(self):
        self._read(full=True)

    def _read(self, full=False):
        status = self.query_one("#read-status", Static)
        progress = self.query_one("#read-progress", ProgressBar)

        def update_progress(done, total):
            pct = int(done / total * 100)
            progress.update(progress=pct)
            status.update(f"Reading... {done}/{total} bytes ({pct}%)")

        try:
            gmlan = self.app._gmlan
            status.update("[yellow]Reading ECU flash...[/yellow]")

            if full:
                data = read_full_flash(gmlan, progress_cb=update_progress)
                cal_data = data[0x1C0000:0x200000]
            else:
                cal_data = read_calibration(gmlan, progress_cb=update_progress)
                data = cal_data

            # Auto-backup
            backup_path, _ = create_backup(data, self.app.ecu_info, PROJECT_ROOT)
            status.update(
                f"[green]Read complete! {len(data)} bytes[/green]\n"
                f"Backup saved: {backup_path}"
            )

            self.app.editor = CalibrationEditor(cal_data, PARAMS, TABLES, BITS, DTCS)
            self.app.push_screen(TuningScreen())

        except E38Error as e:
            status.update(f"[red]Read failed: {e}[/red]")
        except Exception as e:
            status.update(f"[red]Error: {e}[/red]")


class TuningScreen(Screen):
    """Main tuning parameter browser."""

    BINDINGS = [
        Binding("escape", "go_back", "Back"),
        Binding("s", "save_file", "Save .bin"),
        Binding("w", "write_ecu", "Write ECU"),
        Binding("p", "apply_preset", "Preset"),
        Binding("f", "show_diff", "Show Changes"),
        Binding("r", "revert", "Revert All"),
        Binding("t", "edit_tables", "Tables"),
        Binding("d", "manage_dtcs", "DTCs"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            # Sidebar - Categories
            with Vertical(id="sidebar"):
                yield Static("[bold]Categories[/bold]", id="cat-header")
                yield ListView(id="category-list")
            # Main content - Parameters
            with VerticalScroll(id="main-content"):
                yield Static("", id="tuning-header")
                yield DataTable(id="param-table")
        with Horizontal(id="tuning-footer"):
            yield Button("Save .bin [S]", id="btn-save", variant="primary")
            yield Button("Write ECU [W]", id="btn-write", variant="error")
            yield Button("Preset [P]", id="btn-preset", variant="success")
            yield Button("Tables [T]", id="btn-tables", variant="default")
            yield Button("DTCs [D]", id="btn-dtcs", variant="default")
            yield Button("Changes [F]", id="btn-diff", variant="default")
            yield Button("Revert [R]", id="btn-revert", variant="warning")
        yield Footer()

    def on_mount(self):
        editor = self.app.editor
        ecu = self.app.ecu_info

        # Header info
        self.query_one("#tuning-header", Static).update(
            f"[bold]ECU:[/bold] {ecu.get('vin', 'N/A')} | "
            f"[bold]Cal:[/bold] {ecu.get('calibration_id', 'N/A')} | "
            f"[bold]OS:[/bold] {ecu.get('os_id', 'N/A')}"
        )

        # Populate categories
        categories = editor.get_categories()
        listview = self.query_one("#category-list", ListView)
        for cat in categories:
            listview.append(ListItem(Label(cat), id=f"cat-{cat.replace('/', '-')}"))

        # Setup parameter table
        table = self.query_one("#param-table", DataTable)
        table.add_columns("Parameter", "Value", "Units", "Range", "Description")
        table.cursor_type = "row"

        if categories:
            self._show_category(categories[0])

    @on(ListView.Selected, "#category-list")
    def on_category_selected(self, event):
        cat = event.item.id.replace("cat-", "").replace("-", "/")
        self._show_category(cat)

    def _show_category(self, category):
        editor = self.app.editor
        table = self.query_one("#param-table", DataTable)
        table.clear()

        self._current_category = category
        self._param_rows = []

        # Scalar parameters
        params = editor.get_params_by_category(category)
        for name, pdef in sorted(params.items()):
            value = editor.get_param(name)
            style = "bold red" if pdef.dangerous else ""
            table.add_row(
                Text(name, style=style),
                Text(f"{value:.2f}", style="bold"),
                pdef.units,
                f"[{pdef.min_value:.0f} - {pdef.max_value:.0f}]",
                pdef.description[:50],
                key=f"p:{name}",
            )
            self._param_rows.append(("param", name))

        # Bit parameters
        bits = editor.get_bits_by_category(category)
        for name, bdef in sorted(bits.items()):
            enabled = editor.get_bit(name)
            status = Text("ENABLED", style="bold green") if enabled else Text("DISABLED", style="bold red")
            table.add_row(
                name,
                status,
                "on/off",
                "",
                bdef.description[:50],
                key=f"b:{name}",
            )
            self._param_rows.append(("bit", name))

        # Tables in this category
        tables = editor.get_tables_by_category(category)
        for name, tdef in sorted(tables.items()):
            table.add_row(
                Text(f"[TABLE] {name}", style="bold cyan"),
                f"{tdef.rows}x{tdef.cols}",
                tdef.cell_units,
                "",
                tdef.description[:50],
                key=f"t:{name}",
            )
            self._param_rows.append(("table", name))

    @on(DataTable.RowSelected, "#param-table")
    def on_row_selected(self, event):
        key = event.row_key.value
        if not key:
            return

        kind, name = key.split(":", 1)

        if kind == "p":
            self.app.push_screen(ParamEditScreen(name))
        elif kind == "b":
            # Toggle bit
            editor = self.app.editor
            current = editor.get_bit(name)
            editor.set_bit(name, not current)
            self._show_category(self._current_category)
        elif kind == "t":
            self.app.push_screen(TableEditScreen(name))

    @on(Button.Pressed, "#btn-save")
    def action_save_file(self):
        self.app.push_screen(SaveScreen())

    @on(Button.Pressed, "#btn-write")
    def action_write_ecu(self):
        self.app.push_screen(WriteFlashScreen())

    @on(Button.Pressed, "#btn-preset")
    def action_apply_preset(self):
        self.app.push_screen(PresetScreen())

    @on(Button.Pressed, "#btn-tables")
    def action_edit_tables(self):
        self.app.push_screen(TableListScreen())

    @on(Button.Pressed, "#btn-dtcs")
    def action_manage_dtcs(self):
        self.app.push_screen(DTCScreen())

    @on(Button.Pressed, "#btn-diff")
    def action_show_diff(self):
        self.app.push_screen(DiffScreen())

    @on(Button.Pressed, "#btn-revert")
    def action_revert(self):
        self.app.editor.revert()
        self._show_category(getattr(self, "_current_category", "Security"))

    def action_go_back(self):
        if self.app.editor and self.app.editor.is_modified():
            self.app.push_screen(ConfirmExitScreen())
        else:
            self.app.pop_screen()


class ParamEditScreen(Screen):
    """Edit a single scalar parameter."""

    BINDINGS = [Binding("escape", "app.pop_screen", "Back")]

    def __init__(self, param_name):
        super().__init__()
        self.param_name = param_name

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            yield Static("", id="param-info")
            yield Input(placeholder="Enter new value", id="param-input")
            yield Button("Apply", id="btn-apply", variant="primary")
            yield Static("", id="param-result")
        yield Footer()

    def on_mount(self):
        info = self.app.editor.get_param_info(self.param_name)
        warning = "\n[bold red]WARNING: This is a dangerous parameter![/bold red]" if info["dangerous"] else ""

        self.query_one("#param-info", Static).update(
            f"[bold]{info['name']}[/bold]\n"
            f"{info['description']}\n\n"
            f"Current value: [bold]{info['value']:.4f}[/bold] {info['units']}\n"
            f"Range: [{info['min']:.2f} - {info['max']:.2f}] {info['units']}"
            f"{warning}"
        )
        self.query_one("#param-input", Input).value = f"{info['value']:.4f}"

    @on(Button.Pressed, "#btn-apply")
    def apply_value(self):
        result = self.query_one("#param-result", Static)
        try:
            value = float(self.query_one("#param-input", Input).value)
            self.app.editor.set_param(self.param_name, value)
            result.update(f"[green]Set {self.param_name} = {value}[/green]")
        except Exception as e:
            result.update(f"[red]Error: {e}[/red]")


class TableEditScreen(Screen):
    """2D table editor with visual display."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("a", "apply_changes", "Apply"),
    ]

    def __init__(self, table_name):
        super().__init__()
        self.table_name = table_name

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            yield Static("", id="table-info")
            yield DataTable(id="table-grid")
            with Horizontal():
                yield Button("Apply Changes [A]", id="btn-apply-table", variant="primary")
                yield Button("Scale All %", id="btn-scale", variant="default")
                yield Input(placeholder="Scale %", id="scale-input", value="100")
            yield Static("", id="table-result")
        yield Footer()

    def on_mount(self):
        editor = self.app.editor
        tdef = editor.tables[self.table_name]
        table_obj = editor.get_table(self.table_name)

        self.query_one("#table-info", Static).update(
            f"[bold]{self.table_name}[/bold] — {tdef.description}\n"
            f"Size: {tdef.rows}x{tdef.cols} | Units: {tdef.cell_units}"
        )

        grid = self.query_one("#table-grid", DataTable)
        self._table_obj = table_obj

        if isinstance(table_obj, Table2D):
            # Column headers
            cols = ["RPM \\ Load"] + [f"{table_obj.col_axis[c]:.0f}" for c in range(table_obj.cols)]
            grid.add_columns(*cols)

            for r in range(table_obj.rows):
                row_label = f"{table_obj.row_axis[r]:.0f}"
                cells = [f"{table_obj.cells[r][c]:.2f}" for c in range(table_obj.cols)]
                grid.add_row(row_label, *cells)

        elif isinstance(table_obj, Table1D):
            cols = ["Index"] + [f"{table_obj.axis[c]:.0f}" for c in range(min(table_obj.size, 32))]
            grid.add_columns(*cols)
            cells = [f"{table_obj.values[c]:.2f}" for c in range(min(table_obj.size, 32))]
            grid.add_row("Value", *cells)

    @on(Button.Pressed, "#btn-apply-table")
    def action_apply_changes(self):
        result = self.query_one("#table-result", Static)
        try:
            self.app.editor.set_table(self.table_name, self._table_obj)
            result.update(f"[green]Table {self.table_name} saved![/green]")
        except Exception as e:
            result.update(f"[red]Error: {e}[/red]")

    @on(Button.Pressed, "#btn-scale")
    def scale_table(self):
        result = self.query_one("#table-result", Static)
        try:
            pct = float(self.query_one("#scale-input", Input).value)
            factor = pct / 100.0
            self._table_obj.scale_all(factor)
            result.update(f"[green]Scaled all cells by {pct}%[/green]")
            # Refresh display
            self.on_mount()
        except Exception as e:
            result.update(f"[red]Error: {e}[/red]")


class TableListScreen(Screen):
    """List all available tables."""

    BINDINGS = [Binding("escape", "app.pop_screen", "Back")]

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            yield Static("[bold]All Tuning Tables[/bold]")
            yield DataTable(id="table-list")
        yield Footer()

    def on_mount(self):
        table = self.query_one("#table-list", DataTable)
        table.add_columns("Table Name", "Size", "Units", "Category", "Description")
        table.cursor_type = "row"

        for name, tdef in sorted(TABLES.items()):
            table.add_row(
                name,
                f"{tdef.rows}x{tdef.cols}",
                tdef.cell_units,
                tdef.category,
                tdef.description[:60],
                key=name,
            )

    @on(DataTable.RowSelected, "#table-list")
    def on_table_selected(self, event):
        if event.row_key.value:
            self.app.push_screen(TableEditScreen(event.row_key.value))


class DTCScreen(Screen):
    """DTC management screen."""

    BINDINGS = [Binding("escape", "app.pop_screen", "Back")]

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            yield Static("[bold]DTC Management[/bold]")
            with Horizontal():
                yield Button("Disable All DTCs", id="btn-disable-all", variant="error")
                yield Button("Enable All DTCs", id="btn-enable-all", variant="success")
                yield Button("LS Swap Preset", id="btn-ls-swap", variant="warning")
            yield DataTable(id="dtc-table")
        yield Footer()

    def on_mount(self):
        self._refresh_dtcs()

    def _refresh_dtcs(self):
        editor = self.app.editor
        table = self.query_one("#dtc-table", DataTable)
        table.clear(columns=True)
        table.add_columns("Code", "Status", "Name", "Category")
        table.cursor_type = "row"

        for code, ddef in sorted(DTCS.items()):
            enabled = editor.get_dtc_enabled(code)
            status = Text("ENABLED", style="bold green") if enabled else Text("DISABLED", style="bold red")
            table.add_row(code, status, ddef.name, ddef.category, key=code)

    @on(DataTable.RowSelected, "#dtc-table")
    def on_dtc_selected(self, event):
        code = event.row_key.value
        if code:
            editor = self.app.editor
            current = editor.get_dtc_enabled(code)
            editor.set_dtc_enabled(code, not current)
            self._refresh_dtcs()

    @on(Button.Pressed, "#btn-disable-all")
    def disable_all(self):
        self.app.editor.disable_all_dtcs()
        self._refresh_dtcs()

    @on(Button.Pressed, "#btn-enable-all")
    def enable_all(self):
        self.app.editor.enable_all_dtcs()
        self._refresh_dtcs()

    @on(Button.Pressed, "#btn-ls-swap")
    def ls_swap_preset(self):
        """Disable DTCs commonly needed for LS swap."""
        editor = self.app.editor
        ls_swap_disable = [
            "P1621", "P1626", "P1631", "P0513",  # VATS
            "P0440", "P0441", "P0442", "P0443", "P0446",  # EVAP
            "P0449", "P0452", "P0453", "P0455", "P0496",  # EVAP
            "P0401", "P0404", "P0405",  # EGR
            "P0410", "P0411", "P0412", "P0418",  # AIR
            "P0420", "P0430",  # Catalyst monitors
            "P06DD", "P0657",  # AFM
        ]
        for code in ls_swap_disable:
            if code in DTCS:
                editor.set_dtc_enabled(code, False)

        # Also disable VATS and emissions systems
        if "VATS Enabled" in editor.bits:
            editor.set_bit("VATS Enabled", False)
        if "VATS Passlock Enabled" in editor.bits:
            editor.set_bit("VATS Passlock Enabled", False)
        if "EGR Enabled" in editor.bits:
            editor.set_bit("EGR Enabled", False)
        if "EVAP Enabled" in editor.bits:
            editor.set_bit("EVAP Enabled", False)
        if "AIR Pump Enabled" in editor.bits:
            editor.set_bit("AIR Pump Enabled", False)
        if "Catalyst Monitor Enabled" in editor.bits:
            editor.set_bit("Catalyst Monitor Enabled", False)
        if "AFM/DoD Enabled" in editor.bits:
            editor.set_bit("AFM/DoD Enabled", False)

        self._refresh_dtcs()


class PresetScreen(Screen):
    """Apply a tuning preset."""

    BINDINGS = [Binding("escape", "app.pop_screen", "Back")]

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            yield Static("[bold]Tuning Presets[/bold]\n")
            yield Button(
                "LS 6.0 HD → VTC 4800 Manual Swap",
                id="btn-preset-ls-manual",
                variant="success",
            )
            yield Static(
                "\n[dim]Applies: VATS off, emissions off, manual trans setup,\n"
                "rev/speed limits, idle, fans, fuel, spark, DTCs — all in one click[/dim]",
            )
            yield Static("", id="preset-result")
            yield RichLog(id="preset-log", highlight=True, markup=True)
        yield Footer()

    @on(Button.Pressed, "#btn-preset-ls-manual")
    def apply_ls_manual(self):
        result = self.query_one("#preset-result", Static)
        log_widget = self.query_one("#preset-log", RichLog)

        try:
            from ..presets.ls_swap_manual import apply as apply_preset

            result.update("[yellow]Applying LS 6.0 HD manual swap preset...[/yellow]")
            changes = apply_preset(self.app.editor)

            for line in changes:
                log_widget.write(line)

            result.update(
                "[bold green]PRESET APPLIED![/bold green]\n"
                "Review changes, then Save or Write to ECU."
            )

        except Exception as e:
            result.update(f"[red]Preset failed: {e}[/red]")


class DiffScreen(Screen):
    """Show all changes made to calibration."""

    BINDINGS = [Binding("escape", "app.pop_screen", "Back")]

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            yield Static("[bold]Calibration Changes[/bold]")
            yield RichLog(id="diff-log", highlight=True, markup=True)
        yield Footer()

    def on_mount(self):
        editor = self.app.editor
        log_widget = self.query_one("#diff-log", RichLog)

        changes = editor.get_changes()
        byte_diffs = editor.get_byte_diff()

        if not changes and not byte_diffs:
            log_widget.write("[dim]No changes made.[/dim]")
            return

        log_widget.write(f"[bold]{len(changes)} parameter changes:[/bold]\n")
        for ch in changes:
            if ch["type"] == "param":
                log_widget.write(
                    f"  {ch['name']}: {ch['old']:.4f} → {ch['new']:.4f}"
                )
            elif ch["type"] == "bit":
                log_widget.write(f"  {ch['name']}: {ch['old']} → {ch['new']}")
            elif ch["type"] == "dtc":
                status = "ENABLED" if ch["enabled"] else "DISABLED"
                log_widget.write(f"  {ch['code']} ({ch['name']}): {status}")
            elif ch["type"] == "table":
                log_widget.write(f"  [TABLE] {ch['name']}: modified")

        log_widget.write(f"\n[bold]{len(byte_diffs)} bytes changed[/bold]")


class SaveScreen(Screen):
    """Save calibration to .bin file."""

    BINDINGS = [Binding("escape", "app.pop_screen", "Back")]

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            yield Static("[bold]Save Calibration[/bold]")
            yield Input(
                placeholder="Output path (e.g., my_tune.bin)",
                id="save-path",
                value="tuned_calibration.bin",
            )
            yield Button("Save", id="btn-save-file", variant="primary")
            yield Static("", id="save-result")
        yield Footer()

    @on(Button.Pressed, "#btn-save-file")
    def save_file(self):
        result = self.query_one("#save-result", Static)
        try:
            path = self.query_one("#save-path", Input).value.strip()
            data = self.app.editor.export()
            save_bin(path, data)
            h = sha256(data)
            result.update(
                f"[green]Saved {len(data)} bytes to {path}[/green]\n"
                f"SHA-256: {h[:32]}..."
            )
        except Exception as e:
            result.update(f"[red]Error: {e}[/red]")


class WriteFlashScreen(Screen):
    """Write calibration to ECU with safety confirmations."""

    BINDINGS = [Binding("escape", "app.pop_screen", "Back")]

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            yield Static("", id="write-info")
            yield Static("", id="write-warning")
            yield Input(placeholder='Type "FLASH" to confirm', id="confirm-input")
            yield Button("Write to ECU", id="btn-flash", variant="error")
            yield ProgressBar(total=100, id="write-progress", show_eta=True)
            yield Static("", id="write-result")
        yield Footer()

    def on_mount(self):
        editor = self.app.editor
        changes = editor.get_changes()
        byte_diffs = editor.get_byte_diff()

        is_bt = hasattr(self.app, "_connection_type") and self.app._connection_type == "obdlink"
        conn_info = "[bold yellow]VIA OBDLINK BLUETOOTH[/bold yellow]" if is_bt else "[bold]VIA J2534[/bold]"

        self.query_one("#write-info", Static).update(
            f"[bold]Changes Summary[/bold]\n"
            f"Parameter changes: {len(changes)}\n"
            f"Bytes modified: {len(byte_diffs)}\n"
            f"Connection: {conn_info}\n"
            f"Battery: {self.app.ecu_info.get('battery_voltage', 0):.1f}V"
        )

        if is_bt:
            self.query_one("#write-warning", Static).update(
                "[bold red]WARNING: BLUETOOTH FLASH[/bold red]\n"
                "1. Connect battery charger — maintain 13V+\n"
                "2. Keep laptop within 1 meter of OBDLink\n"
                "3. Do NOT touch laptop, phone, or move during flash\n"
                "4. Do NOT disconnect OBDLink from OBD port\n"
                "5. Pre-flight test will check BT stability first\n"
                "6. 256-byte blocks with retry for safety"
            )
        else:
            self.query_one("#write-warning", Static).update(
                "[bold red]WARNING: Writing to ECU![/bold red]\n"
                "Ensure stable 12V+ power supply.\n"
                "Do NOT disconnect during flash."
            )

    @on(Button.Pressed, "#btn-flash")
    def flash_ecu(self):
        result = self.query_one("#write-result", Static)
        confirm = self.query_one("#confirm-input", Input).value.strip()

        if confirm != "FLASH":
            result.update('[red]Type "FLASH" to confirm[/red]')
            return

        # Check which connection type we have
        has_j2534 = hasattr(self.app, "_gmlan") and self.app._gmlan is not None
        has_obdlink = hasattr(self.app, "_obdlink") and self.app._obdlink is not None

        if not has_j2534 and not has_obdlink:
            result.update("[red]Not connected to ECU. Use Save instead for offline editing.[/red]")
            return

        progress = self.query_one("#write-progress", ProgressBar)

        def update_progress(done, total, phase):
            pct = int(done / total * 100) if total else 0
            progress.update(progress=pct)
            phase_labels = {
                "preflight": "Pre-flight checks",
                "check": "Checking ECU",
                "erase": "Erasing flash",
                "write": "Writing calibration",
                "verify": "Verifying flash",
            }
            label = phase_labels.get(phase, phase)
            result.update(f"[yellow]{label}: {done}/{total} bytes ({pct}%)[/yellow]")

        try:
            cal_data = self.app.editor.export()

            if has_obdlink:
                # OBDLink Bluetooth flash
                result.update(
                    "[yellow]Flashing via OBDLink Bluetooth...[/yellow]\n"
                    "[bold]DO NOT move laptop or disconnect![/bold]"
                )
                self.app._obdlink.write_calibration(
                    cal_data,
                    verify=True,
                    progress_cb=update_progress,
                )
            else:
                # J2534 flash
                result.update("[yellow]Flashing via J2534...[/yellow]")
                write_calibration(
                    self.app._gmlan,
                    cal_data,
                    verify=True,
                    progress_cb=update_progress,
                )

            result.update(
                "[bold green]FLASH COMPLETE![/bold green]\n"
                "Calibration written and verified successfully.\n"
                "Cycle ignition to apply changes."
            )

        except E38Error as e:
            result.update(f"[bold red]FLASH FAILED: {e}[/bold red]")
        except Exception as e:
            result.update(f"[bold red]ERROR: {e}[/bold red]")


class ConfirmExitScreen(Screen):
    """Confirm exit with unsaved changes."""

    BINDINGS = [Binding("escape", "app.pop_screen", "Cancel")]

    def compose(self) -> ComposeResult:
        with Container():
            yield Static(
                "[bold yellow]You have unsaved changes![/bold yellow]\n\n"
                "Exit without saving?"
            )
            with Horizontal():
                yield Button("Save & Exit", id="btn-save-exit", variant="primary")
                yield Button("Discard & Exit", id="btn-discard-exit", variant="error")
                yield Button("Cancel", id="btn-cancel-exit", variant="default")

    @on(Button.Pressed, "#btn-save-exit")
    def save_and_exit(self):
        self.app.pop_screen()  # Remove confirm screen
        self.app.push_screen(SaveScreen())

    @on(Button.Pressed, "#btn-discard-exit")
    def discard_and_exit(self):
        self.app.pop_screen()  # Remove confirm screen
        self.app.pop_screen()  # Remove tuning screen

    @on(Button.Pressed, "#btn-cancel-exit")
    def cancel(self):
        self.app.pop_screen()


class E38TunerApp(App):
    """E38 ECU Tuner — Professional LS Engine Tuning Tool."""

    TITLE = "E38 ECU Tuner v1.0"
    CSS_PATH = "styles/theme.css"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("?", "help", "Help"),
    ]

    def __init__(self, bin_file=None, demo=False, preset=None, **kwargs):
        super().__init__(**kwargs)
        self.editor = None
        self.ecu_info = {}
        self._j2534 = None
        self._gmlan = None
        self._obdlink = None
        self._connection_type = None
        self._j2534_devices = []
        self._bt_ports = []
        self._backup_list = []
        self.loaded_file = bin_file
        self._demo = demo
        self._preset = preset

    def on_mount(self):
        if self._demo:
            demo_data = bytearray(262144)
            self.editor = CalibrationEditor(demo_data, PARAMS, TABLES, BITS, DTCS)
            self.ecu_info = {
                "vin": "DEMO_MODE",
                "calibration_id": "DEMO_12345678",
                "os_id": "DEMO_OS",
                "hardware_number": "E38_DEMO",
                "battery_voltage": 14.2,
            }
            self.push_screen(TuningScreen())
        elif self.loaded_file:
            try:
                data = load_bin(self.loaded_file)
                if len(data) == 2097152:
                    data = data[0x1C0000:0x200000]
                self.editor = CalibrationEditor(data, PARAMS, TABLES, BITS, DTCS)
                self.ecu_info = {
                    "vin": "File",
                    "calibration_id": os.path.basename(self.loaded_file),
                    "os_id": "File",
                    "hardware_number": "E38",
                    "battery_voltage": 0,
                }
                self.push_screen(TuningScreen())
            except Exception as e:
                self.push_screen(HomeScreen())
        else:
            self.push_screen(HomeScreen())

    def action_help(self):
        self.notify(
            "C=Connect | O=Open file | D=Demo\n"
            "S=Save | W=Write ECU | T=Tables\n"
            "D=DTCs | F=Changes | R=Revert | Q=Quit",
            title="Keyboard Shortcuts",
            timeout=10,
        )

    def on_unmount(self):
        if self._j2534:
            try:
                self._j2534.close()
            except Exception:
                pass
