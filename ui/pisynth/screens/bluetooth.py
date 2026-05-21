"""Bluetooth pairing-manager screens (#287/#301), split out of the controller (#308).

Mixin for app.App: the per-device pair/connect/forget UI around the `io.Bluetooth`
worker. Reads cross-feature helpers (_confirm, _update_bt_pref, _restart_and_note,
_update_settings, render) via the MRO.
"""
import time

from ..ui.menu import Item, MenuScreen


class BluetoothMixin:
    # ---- Bluetooth pairing manager (ticket #287) — top-level Settings entry ----
    def _open_bluetooth(self):
        self.bt.open()                               # worker: power on + device refresh, off the UI loop
        self._bt_scan = False
        self.stack.append(self._bluetooth_menu())

    @staticmethod
    def _bt_state(paired, connected):
        # "available" was ambiguous (#301: "pairé ou pas ?") → spell it out.
        return "connected" if connected else ("paired" if paired else "not paired")

    def _bt_name(self, mac, name):
        """Best friendly name for a device, remembering it across sessions (#301).
        A resolved name is cached to settings.yaml (bluetooth.known) so known devices
        always show a name — even with scan off or before the worker has queried."""
        if name and name != mac:
            self._remember_bt_name(mac, name)
            return name
        return self.bt_names.get(mac, mac)

    def _bluetooth_menu(self):
        items = [Item("Scan", on_select=self._toggle_scan,
                      value=(lambda: "on" if self._bt_scan else "off"))]
        for mac, name, paired, connected in self.bt.devices():     # cached → instant, no subprocess
            disp = self._bt_name(mac, name)
            state = self._bt_state(paired, connected)
            items.append(Item(
                disp, submenu=True,                                # each device → its own menu (#301)
                on_select=(lambda m=mac, dn=disp, p=paired, c=connected: self._bt_open_device(m, dn, p, c)),
                marker=(lambda c=connected: c),
                value=(lambda s=state: s)))
        return MenuScreen("Bluetooth", items, footer=self.bt.last_result)

    def _rebuild_bt(self):
        """Rebuild the Bluetooth screen from the worker-updated cache, keeping the cursor."""
        if self.cur.title == "Bluetooth":
            keep = self.cur.idx
            self.stack[-1] = self._bluetooth_menu()
            self.cur.idx = max(0, min(keep, len(self.cur.items) - 1))

    def _toggle_scan(self):
        self._bt_scan = not self._bt_scan
        if self._bt_scan:
            self._bt_scan_t0 = time.monotonic()
        self.bt.submit("scan", self._bt_scan, "scanning…" if self._bt_scan else None)
        self._rebuild_bt()

    def _bt_open_device(self, mac, name, paired, connected):
        """Per-device menu (#301): explicit connect/disconnect + Forget, instead of the
        old tap-to-cycle. Title = the device's friendly name."""
        if connected:
            act = Item("Disconnect", on_select=(lambda: self._bt_action("disconnect", mac, "Disconnecting…")))
        elif paired:
            act = Item("Connect", on_select=(lambda: self._bt_action("connect", mac, "Connecting…")))
        else:
            act = Item("Pair & connect", on_select=(lambda: self._bt_action("pair", mac, "Pairing…")))
        self.stack.append(MenuScreen(name, [
            act,
            Item("Forget", on_select=(lambda: self._confirm("Forget " + name, lambda: self._bt_forget(mac)))),
            Item("Status", value=(lambda: self._bt_state(paired, connected))),
            Item("Address", value=(lambda: mac)),
        ]))

    def _bt_back_to_list(self):
        """Pop any device/confirm screens back to the Bluetooth list and refresh it."""
        while len(self.stack) > 1 and self.cur.title != "Bluetooth":
            self.stack.pop()
        self._rebuild_bt()
        self.render()

    def _bt_action(self, action, mac, pending):
        # submit to the worker (never blocks the UI); cache + footer refresh on the idle tick
        self.bt.submit(action, mac, pending)
        self._bt_back_to_list()

    def _bt_forget(self, mac):
        self.bt.submit("remove", mac, "Forgetting…")
        if self.bt_names.pop(mac, None) is not None:
            self._bt_names_dirty = True
        if self.bt_sink == mac:                        # forgot the active audio sink → back to ALSA
            self.bt_sink = ""
            self._update_bt_pref(audio_sink="")
            self._restart_and_note()
        self._bt_back_to_list()

    def _save_bt_names(self):
        """Persist the known-device name map into settings.yaml (merges into the
        bluetooth section, never clobbering audio_sink etc) (#301)."""
        self._update_bt_pref(known=self.bt_names)
        self._bt_names_dirty = False
