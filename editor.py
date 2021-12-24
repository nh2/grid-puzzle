import gi
import json

from dataclasses import dataclass

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from gi.repository import Gdk


@dataclass
class Gap:
    direction: str
    lane: int
    offset: int

@dataclass
class InputState:
    gap: Gap


class GridWindow(Gtk.Window):
    def __init__(self):

        super().__init__(title="Puzzle Grid")

        screen = Gdk.Screen.get_default()
        provider = Gtk.CssProvider()
        style_context = Gtk.StyleContext()
        style_context.add_provider_for_screen(
            screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        css = b"""
        button.field {
            font-size: 1px;
            padding: 0px;
            border: 0px;
            border-radius: 0;
        }
        button.gap {
            background-color: black;
            min-width: 5px;
            min-height: 5px;
        }
        button.gap.disabled {
            background-color: white;
        }
        button.tile {
            background-color: white;
            min-width: 15px;
            min-height: 15px;
        }
        """
        provider.load_from_data(css)

        # Number of tiles
        SIZE_X = 56
        SIZE_Y = 57
        # SIZE_X = 3
        # SIZE_Y = 4

        gaps_vert = {}  # (lane, offset) -> bool
        gaps_horiz = {}  # (lane, offset) -> bool

        buttons_gaps_vert = {}
        buttons_gaps_horiz = {}

        input_state = InputState(gap=Gap(direction="v", lane=0, offset=0))

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add(vbox)

        def update_state_label():
            gap = input_state.gap
            state_label.set_text(f"Position: {gap.direction} {gap.lane} {gap.offset}")

        def set_input_gap(gap):
            input_state.gap = gap
            update_state_label()

        state_label = Gtk.Label(label="Position: ")
        vbox.add(state_label)

        grid = Gtk.Grid()

        def on_gap_clicked(button):
            button.get_style_context().add_class("disabled")
            print("Gap clicked")

        def add_button(top, left, label, css_class, width=1, height=1):
            button = Gtk.Button(label=label)
            button.set_relief(Gtk.ReliefStyle.NONE)
            button.get_style_context().add_class("field")
            button.get_style_context().add_class(css_class)
            grid.attach(button, left=left, top=top, width=width, height=height)
            return button

        def update_button_style(button, gap_active: bool):
            button.get_style_context().remove_class("disabled")
            if not gap_active:
                button.get_style_context().add_class("disabled")

        def set_gap(gap, gap_active: bool):
            gaps_state_dict = {"v": gaps_vert, "h": gaps_horiz}[gap.direction]
            gaps_state_dict[(gap.lane, gap.offset)] = gap_active

            buttons_dict = {"v": buttons_gaps_vert, "h": buttons_gaps_horiz}[gap.direction]
            button = buttons_dict[(gap.lane, gap.offset)]

            update_button_style(button, gap_active)

        def toggle_gap(gap):
            gaps_state_dict = {"v": gaps_vert, "h": gaps_horiz}[gap.direction]
            set_gap(gap, gaps_state_dict[(gap.lane, gap.offset)] ^ True)  # invert

        def make_gap_clicked_function(gap):
            def on_click(button):
                toggle_gap(gap)
                set_input_gap(gap)
            return on_click

        def make_keypress_function():
            def on_keypress(widget, event):
                key_name = Gdk.keyval_name(event.keyval)
                gap = input_state.gap
                print(f"keypress on {gap.direction=} {gap.lane=} {gap.offset=} {key_name=}")
                size = { 'h': SIZE_X, 'v': SIZE_Y }[gap.direction]
                if key_name in ['1', '2', '3', '4', '5', '6', '7', '8', '9']:
                    n = int(key_name)
                    print(f"Ungapping next {n-1} fields, inserting gap after")
                    for i in range(n-1):
                        target_gap = Gap(direction=gap.direction, lane=gap.lane, offset=min(size-1, gap.offset + 1 + i))
                        set_gap(target_gap, gap_active=False)
                    end_gap = Gap(direction=gap.direction, lane=gap.lane, offset=min(size-1, gap.offset + n))
                    set_gap(end_gap, gap_active=True)
                    set_input_gap(end_gap)
            return on_keypress

        # Horizontal gaps
        for lane in range(SIZE_Y):
            for offset in range(SIZE_X + 1):
                left = offset * 2
                top = lane * 2 + 1
                b = add_button(3*top, 3*left, "", "gap", height=3)
                buttons_gaps_horiz[(lane, offset)] = b
                gaps_horiz[(lane, offset)] = True
                b.connect("clicked", make_gap_clicked_function(Gap("h", lane, offset)))
                b.connect("key-press-event", make_keypress_function())

        # Tiles
        for x in range(SIZE_X):
            for y in range(SIZE_Y):
                left = x * 2 + 1
                top = y * 2 + 1
                add_button(3*top, 3*left, "", "tile", width=3, height=3)

        # Vertical gaps
        for lane in range(SIZE_X):
            for offset in range(SIZE_Y + 1):
                left = lane * 2 + 1
                top = offset * 2
                b = add_button(3*top, 3*left, "", "gap", width=3)
                buttons_gaps_vert[(lane, offset)] = b
                gaps_vert[(lane, offset)] = True
                b.connect("clicked", make_gap_clicked_function(Gap("v", lane, offset)))
                b.connect("key-press-event", make_keypress_function())


        vbox.add(grid)

        save_file_path = "field.json"

        # Save button
        save_button = Gtk.Button(label="Save")
        def on_save_click(button):
            def gaps_to_bool_array(gaps_state_dict, num_lanes, num_offsets):
                bools = []
                for lane in range(num_lanes):
                    bools_row = []
                    for offset in range(num_offsets):
                        bools_row.append(gaps_state_dict[(lane, offset)])
                    bools.append(bools_row)
                return bools
            state = {
                'horiz': gaps_to_bool_array(gaps_horiz, num_lanes=SIZE_Y, num_offsets=SIZE_X),
                'vert': gaps_to_bool_array(gaps_vert, num_lanes=SIZE_X, num_offsets=SIZE_Y),
            }
            with open(save_file_path, 'w') as f:
                json.dump(state, f, sort_keys=True, indent=2)
            print(f"Saved to {save_file_path}")

        save_button.connect("clicked", on_save_click)
        vbox.add(save_button)

        load_button = Gtk.Button(label="Load")
        def on_load_click(button):
            print(f"Loading {save_file_path}")
            with open(save_file_path, 'r') as f:
                state = json.load(f)
            for key, gaps_state_dict in [('horiz', gaps_horiz), ('vert', gaps_vert)]:
                bools = state[key]
                for lane, cols in enumerate(bools):
                    for offset, b in enumerate(cols):
                        direction = {'horiz': 'h', 'vert': 'v'}[key]
                        gap = Gap(direction=direction, lane=lane, offset=offset)
                        set_gap(gap, gap_active=b)
                        print(f"Loading {gap=} {b=}")

        load_button.connect("clicked", on_load_click)
        vbox.add(load_button)


def main():
    win = GridWindow()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()


if __name__ == '__main__':
    main()
