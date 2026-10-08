"""LED data: stock g12a_u221 sys_led (gpio-leds) overlay fragment.

Stock DT (g12a_u221_2g, all three _aml_dtb variants identical here):

    gpioleds {
        compatible = "gpio-leds";
        status = "okay";
        sys_led {
            label = "sys_led";
            gpios = <0x13 0x40 0x00>;   /* periphs EE bank, pin 64, active-high */
            default-state = "on";
        };
    };

The kernel gpio-leds driver (CONFIG_LEDS_GPIO=y in the LOS kernel too)
drives the pin HIGH at probe, which is exactly the stock behaviour the
user sees: dim blue at power-on (u-boot leaves the pin floating), full
brightness once the kernel is up. Stock userspace does nothing for this
LED: init.amlogic.board.rc only chmods nodes that do not exist on this
board (net_green/net_red, led_gpio), and the Light HAL 2.0 passthrough
ships no legacy lib. So the whole stock logic is this one DT node.

LOS (deadpool g12a_s905y2) has a *different* gpioleds node (Radxa's own
green/red on the AO bank, status "disabled"), so the driver never probes
and the pin floats forever: the LED stays dim. The overlay below adds a
separate top-level `leds` node (deliberately NOT named `gpioleds`, so it
never merges with the disabled one) with the stock sys_led child.

No phandles are defined in this fragment, so the u-boot +0x100 phandle
quirk (see ir_data.py) does not apply here. The gpios value references
the *base* periphs bank (banks@ff6346c0, phandle 0x15 in both
radxa0/radxa0_tab base DTBs — same SoC, same bank, same pin 64);
overlay property values pass through the applier untouched, so the
literal 0x15 resolves to the base node.
"""

from collections.abc import Sequence

from .fdt import FdtNode, pack_u32s

# periphs EE GPIO bank (banks@ff6346c0) in the deadpool base DTB.
LED_GPIO_CONTROLLER = 0x15
# stock sys_led pin within that bank, active-high (flags 0).
LED_GPIO_PIN = 0x40


def build_led_fragments() -> list[FdtNode]:
    """DTBO overlay fragment (5) for the blue status LED."""
    def node(name: str, props: Sequence[tuple[str, bytes]] = (),
             children: Sequence[FdtNode] = ()) -> FdtNode:
        return {"name": name, "props": list(props), "children": list(children)}

    def u32(name: str, *vals: int) -> tuple[str, bytes]:
        return (name, pack_u32s(list(vals)))

    def string(name: str, text: str) -> tuple[str, bytes]:
        return (name, text.encode() + b"\x00")

    return [node("fragment@5", [string("target-path", "/")], [
        node("__overlay__", (), [
            node("leds", [
                string("compatible", "gpio-leds"),
                string("status", "okay"),
            ], [
                node("sys_led", [
                    string("label", "sys_led"),
                    u32("gpios", LED_GPIO_CONTROLLER, LED_GPIO_PIN, 0),
                    string("default-state", "on"),
                ]),
            ]),
        ]),
    ])]


def tree_has_led(tree: FdtNode) -> bool:
    """True if the overlay tree already carries the sys_led node."""
    found = []

    def walk(node: FdtNode) -> None:
        if node["name"] == "sys_led":
            found.append(True)
        for ch in node["children"]:
            walk(ch)

    walk(tree)
    return bool(found)
