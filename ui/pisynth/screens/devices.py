"""Shared output-device helpers (#308 dedup).

The synth output picker (screens.audio) and the metronome output picker
(screens.metronome) were built identically — same "default + ALSA cards + BT sinks"
list and the same label resolution. Factored here so the two can't drift. State is read
through getter callables so markers stay live (the original behaviour).
"""
from ..core.audio import list_audio_cards, list_bt_sinks
from ..ui.menu import Item


def output_label(card, bt_sink, bt_names, default):
    """Friendly name of an output: BT sink (cached name) → ALSA card label → `default`."""
    if bt_sink:
        return bt_names.get(bt_sink, bt_sink)
    if not card:
        return default
    for name, label in list_audio_cards():
        if name == card:
            return label
    return card                                  # configured but not currently present


def output_picker_items(default_label, get_card, get_bt, on_default, on_card, on_bt):
    """[default, ALSA cards…, connected BT sinks…] items for an output picker. Exactly
    one is active; choosing a BT sink clears the card and vice-versa (handled by the
    on_* callbacks). BT rows are tagged 'BT' (#282/#287/#301)."""
    items = [Item(default_label, on_select=on_default,
                  marker=(lambda: not get_card() and not get_bt()))]
    for name, label in list_audio_cards():
        items.append(Item(
            label, on_select=(lambda n=name: on_card(n)),
            marker=(lambda n=name: get_card() == n and not get_bt())))
    for mac, label in list_bt_sinks():
        items.append(Item(
            label, on_select=(lambda m=mac, l=label: on_bt(m, l)),
            marker=(lambda m=mac: get_bt() == m), value=(lambda: "BT")))
    return items
