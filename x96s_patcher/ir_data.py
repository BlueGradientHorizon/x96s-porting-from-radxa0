"""IR data: stock g12a_u221_2g keymaps + fixed X96S remote tab2."""

from collections.abc import Sequence
from typing import Any

from .fdt import FdtNode, pack_u32s

# pinctrl node of the AO pinmux in the deadpool base dtb
IR_PINCTRL_TARGET = 0x97
# NOTE on phandles: this u-boot's fdt overlay applier relocates overlay
# node phandles by +0x100 but leaves property *values* untouched, so every
# reference below is pre-compensated (explicit value = node value + 0x100).
# Values verified live via /proc/device-tree.
IR_PIN_PHANDLE = 0x100
IR_PIN_REF = 0x200
IR_MAPS_PHANDLE = 0x110
IR_MAPS_REF = 0x210
IR_MAP_PHANDLES = (0x111, 0x112, 0x113)
IR_MAP_REFS = (0x211, 0x212, 0x213)

# stock keymaps: (scancode << 16) | linux_keycode, copied from the
# g12a_u221_2g device tree (see README.md)
IR_MAPS: list[dict[str, Any]] = [
    {
        "name": "map_0",
        "mapname": "amlogic-remote-1",
        "customcode": 0xfb04,
        "release_delay": 80,
        "extra": [],
        "keymap": [
            0x0047000b, 0x00130002, 0x00100003, 0x00110004, 0x000f0005, 0x000c0006, 0x000d0007, 0x000b0008,
            0x00080009, 0x0009000a, 0x005c0061, 0x0051003d, 0x0050003e, 0x0040003f, 0x004d0040, 0x00430041,
            0x00170042, 0x00000043, 0x00010044, 0x00160057, 0x0049000e, 0x00060082, 0x00140083, 0x00440067,
            0x001d006c, 0x001c0069, 0x0048006a, 0x0053007d, 0x00450068, 0x0019006d, 0x00520077, 0x0005007a,
            0x0059007b, 0x001b0078, 0x00040079, 0x001a0074, 0x000a000f, 0x000e0071, 0x001f0066, 0x001e0084,
            0x00070085, 0x00120086, 0x00540087, 0x00020088, 0x004f001e, 0x00420030, 0x005d002e, 0x004c0020,
            0x00580089, 0x0055008c,
        ],
    },
    {
        "name": "map_1",
        "mapname": "amlogic-remote-2",
        "customcode": 0xfe01,
        "release_delay": 80,
        "extra": [('fn_key_scancode', 0), ('cursor_left_scancode', 81), ('cursor_right_scancode', 80), ('cursor_up_scancode', 22), ('cursor_down_scancode', 26), ('cursor_ok_scancode', 19)],
        "keymap": [
            0x0001000b, 0x004e0002, 0x000d0003, 0x000c0004, 0x004a0005, 0x00090006, 0x00080007, 0x00460008,
            0x00050009, 0x0004000a, 0x0049003f, 0x0048004e, 0x004d004b, 0x0003004c, 0x0043004d, 0x00450040,
            0x000f0041, 0x00440042, 0x00120043, 0x004b0044, 0x00260045, 0x00160067, 0x001a006c, 0x00510069,
            0x0050006a, 0x0013001c, 0x0019009e, 0x004c007d, 0x00400074, 0x00410071, 0x00180073, 0x00100072,
            0x00110066, 0x000a006f, 0x0042000e, 0x004700d7, 0x000e0046, 0x0059007a, 0x0058007b, 0x00540078,
            0x0052007c, 0x005a0077, 0x00550079, 0x00000064, 0x001b00bc,
        ],
    },
    {
        "name": "map_2",
        "mapname": "amlogic-remote-3",
        "customcode": 0xbd02,
        "release_delay": 80,
        "extra": [],
        "keymap": [
            0x00ca0067, 0x00d2006c, 0x00990069, 0x00c1006a, 0x00ce0061, 0x00450074, 0x00c50085, 0x00800071,
            0x00d0000f, 0x00d6007d, 0x00950066, 0x00dd0068, 0x008c006d, 0x00890083, 0x009c0082, 0x009a0078,
            0x00cd0079,
        ],
    },
]

# Corrected keymap file for the physical X96S remote (custom 0xFE01).
# scancode -> linux keycode, Android mapping verified against Generic.kl.
# Baked into vendor.new.dat.br (replaces the foreign remote.tab2).
FIXED_TAB2 = """custom_name = amlogic-remote-2
custom_code = 0xfe01
release_delay = 80
fn_key_scancode = 0x00
cursor_left_scancode = 0x51
cursor_right_scancode = 0x50
cursor_up_scancode = 0x16
cursor_down_scancode = 0x1a
cursor_ok_scancode = 0x13

key_begin
\t0x40 116
\t0x41 113
\t0x16 103
\t0x1a 108
\t0x51 105
\t0x50 106
\t0x13 28
\t0x11 172
\t0x4c 580
\t0x19 158
\t0x10 114
\t0x18 115
\t0x43 139
\t0x00 100
\t0x44 66
key_end
"""


def build_ir_fragments() -> list[FdtNode]:
    """DTBO overlay fragments (2..4) for the IR receiver."""
    def node(name: str, props: Sequence[tuple[str, bytes]] = (),
             children: Sequence[FdtNode] = ()) -> FdtNode:
        return {"name": name, "props": list(props), "children": list(children)}

    def u32(name: str, *vals: int) -> tuple[str, bytes]:
        return (name, pack_u32s(list(vals)))

    def string(name: str, text: str) -> tuple[str, bytes]:
        return (name, text.encode() + b"\x00")

    frags = []
    frags.append(node("fragment@2", [u32("target", IR_PINCTRL_TARGET)], [
        node("__overlay__", (), [
            node("remote_pin", [u32("phandle", IR_PIN_PHANDLE)], [
                node("mux", [
                    string("groups", "remote_input_ao"),
                    string("function", "remote_input_ao"),
                ]),
            ]),
        ]),
    ]))
    frags.append(node("fragment@3", [string("target-path", "/")], [
        node("__overlay__", (), [
            node("rc@0xff808040", [
                string("compatible", "amlogic, aml_remote"),
                string("dev_name", "meson-remote"),
                u32("reg", 0, 0xFF808040, 0, 0x44, 0, 0xFF808000, 0, 0x20),
                string("status", "okay"),
                u32("protocol", 1),
                u32("led_blink", 1),
                u32("led_blink_frq", 100),
                u32("interrupts", 0, 196, 1),
                string("pinctrl-names", "default"),
                u32("pinctrl-0", IR_PIN_REF),
                u32("map", IR_MAPS_REF),
                u32("max_frame_time", 200),
            ]),
        ]),
    ]))
    maps_children = [
        u32("mapnum", len(IR_MAPS)),
        u32("map0", IR_MAP_REFS[0]),
        u32("map1", IR_MAP_REFS[1]),
        u32("map2", IR_MAP_REFS[2]),
        u32("phandle", IR_MAPS_PHANDLE),
    ]
    map_nodes = []
    for tab, ph in zip(IR_MAPS, IR_MAP_PHANDLES):
        props: list[tuple[str, bytes]] = [
            string("mapname", tab["mapname"]),
            u32("customcode", tab["customcode"]),
            u32("release_delay", tab["release_delay"]),
        ]
        for key, val in tab["extra"]:
            props.append(u32(key, val))
        props.append(u32("size", len(tab["keymap"])))
        props.append(("keymap", pack_u32s(tab["keymap"])))
        props.append(u32("phandle", ph))
        map_nodes.append(node(tab["name"], props))
    frags.append(node("fragment@4", [string("target-path", "/")], [
        node("__overlay__", (), [
            node("custom_maps", maps_children, map_nodes),
        ]),
    ]))
    return frags


def tree_has_rc(tree: FdtNode) -> bool:
    found = []

    def walk(node: FdtNode) -> None:
        if node["name"] == "rc@0xff808040":
            found.append(True)
        for ch in node["children"]:
            walk(ch)

    walk(tree)
    return bool(found)
