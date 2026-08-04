import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, GObject, Gio

from ..monitors.net_monitor import NetworkMonitor, ActiveSocketInfo

class SocketGObject(GObject.Object):
    """GObject wrapper for ActiveSocketInfo."""
    def __init__(self, info: ActiveSocketInfo):
        super().__init__()
        self.info = info
        self.protocol = info.protocol
        self.local_addr = info.local_addr
        self.remote_addr = info.remote_addr
        self.status = info.status
        self.pid_str = str(info.pid) if info.pid else "N/A"
        self.process_name = info.process_name

class NetworkView(Gtk.Box):
    """Network Sockets tab displaying active network connections, ports, and owning processes."""
    def __init__(self, main_window: Gtk.Window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.main_window = main_window
        self.monitor = NetworkMonitor()

        self.set_margin_start(8)
        self.set_margin_end(8)
        self.set_margin_top(8)
        self.set_margin_bottom(8)

        # Search Bar
        top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.append(top_bar)

        self.search_entry = Gtk.SearchEntry(placeholder_text="Filter network sockets by address, port, protocol, PID, or process...")
        self.search_entry.set_hexpand(True)
        top_bar.append(self.search_entry)

        # Store & Filtering
        self.store = Gio.ListStore.new(SocketGObject)
        self.filter_model = Gtk.FilterListModel.new(self.store, None)

        self.custom_filter = Gtk.CustomFilter.new(self._filter_func)
        self.filter_model.set_filter(self.custom_filter)
        self.search_entry.connect("search-changed", lambda e: self.custom_filter.changed(Gtk.FilterChange.DIFFERENT))

        self.sort_model = Gtk.SortListModel.new(self.filter_model, None)
        self.selection_model = Gtk.SingleSelection.new(self.sort_model)

        self.column_view = Gtk.ColumnView.new(self.selection_model)
        self.column_view.set_show_column_separators(True)
        self.column_view.set_show_row_separators(True)
        self.sort_model.set_sorter(self.column_view.get_sorter())

        scrolled = Gtk.ScrolledWindow(vexpand=True)
        scrolled.set_child(self.column_view)
        self.append(scrolled)

        self._create_columns()

    def _filter_func(self, item: SocketGObject) -> bool:
        query = self.search_entry.get_text().strip().lower()
        if not query:
            return True
        info = item.info
        text = f"{info.protocol} {info.local_addr} {info.remote_addr} {info.status} {info.pid} {info.process_name}".lower()
        return query in text

    def _create_columns(self):
        cols = [
            ("Protocol", lambda s: s.protocol, lambda s: s.protocol),
            ("Local Address:Port", lambda s: s.local_addr, lambda s: s.local_addr),
            ("Remote Address:Port", lambda s: s.remote_addr, lambda s: s.remote_addr),
            ("State", lambda s: s.status, lambda s: s.status),
            ("PID", lambda s: s.pid_str, lambda s: s.info.pid or 0),
            ("Owning Process", lambda s: s.process_name, lambda s: s.process_name.lower()),
        ]

        for title, str_func, sort_key in cols:
            factory = Gtk.SignalListItemFactory()
            factory.connect("setup", lambda f, item: item.set_child(Gtk.Label(xalign=0.0, margin_start=6, margin_end=6)))
            factory.connect("bind", lambda f, item, sf=str_func: item.get_child().set_text(sf(item.get_item())))

            sorter = Gtk.CustomSorter.new(lambda a, b, sk=sort_key: self._compare(a, b, sk))
            column = Gtk.ColumnViewColumn.new(title, factory)
            column.set_sorter(sorter)
            column.set_resizable(True)
            self.column_view.append_column(column)

    def _compare(self, a: SocketGObject, b: SocketGObject, sort_key) -> int:
        ka, kb = sort_key(a), sort_key(b)
        if ka < kb: return -1
        elif ka > kb: return 1
        return 0

    def refresh_data(self):
        sockets = self.monitor.get_active_sockets()
        self.store.remove_all()
        for s in sockets:
            self.store.append(SocketGObject(s))
