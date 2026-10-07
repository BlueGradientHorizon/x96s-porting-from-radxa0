# Железо и симптомы

## Железо

### Стик X96S 2/16 (ревизия платы 2.4GHz, данные сняты вживую по adb)

- Стик 98x33x13: HDMI 2.1, 1x USB-A, 1x microUSB (питание + adb),
  TF-слот, выносной ИК-глазок на 3.5мм, одна кнопка (reset).
- SoC Amlogic S905Y2 (G12A, 12нм), 4x Cortex-A53 до 1.8ГГц, Mali-G31 MP2.
  Device-tree стока: `g12a_u221_2g`.
- 2GB LPDDR4 (`MemTotal 2057352 kB`), 16GB Samsung eMMC (`AWMB3R`).
- WiFi/BT: **Realtek RTL8723BS**, SDIO `024c:b723`, драйвер `8723bs`
  v5.2.17.1, FW29, **только 2.4GHz b/g/n**. Ревизия без 5GHz (у slimBOXtv
  отдельные прошивки `2GB 2.4GHz` / `2GB 5GHz`!). BT `...:8D` в паре с
  WLAN `...:8C` (combo-чип, одна антенна).
- ИК: встроенный в SoC `meson-remote ff808040.rc`, NEC, кастомы
  `0xFB04` (основной), `0xFE01`, `0xBD02`; `aml_keypad /dev/input/event0`,
  `/dev/amremote`.
- USB-A — **только USB 2.0** несмотря на синий пластик: `usb2` root-hub
  есть, но `amlogic-new-usb3-v2: This phy has no usb port`, maxchild 0.
- Сток: Android 9 AOSP (slimBOXtv ATV 9.16, `faraday`/`X96S_P`), ядро
  4.9.113 armv7l.

### Донор Radxa Zero (под него собран Lineage)

Тот же S905Y2 (ядро/GPU/VPU/HDMI общие), но обвязка другая:

| Узел | Radxa Zero | X96S | Итог |
|---|---|---|---|
| WiFi/BT | Broadcom BCM43436/43455 (`brcmfmac`) | Realtek RTL8723BS | 0% (вендор, драйвер, прошивки, SDIO-пины) |
| ИК | штатного нет (только GPIO) | meson-remote + глазок + кеймапы | нода/табы только от стика |
| USB | настоящий USB3.0 host | только USB2 | USB2-периферия везде ок |
| Boot | кнопка USB BOOT, MaskROM | reset игнорируется неродным u-boot, burn через тестпоинт eMMC | см. 3.4 |

Вывод: образы Zero стартуют (SoC один), но WiFi/BT и ИК мертвы.

### Сырые замеры со стока (2026-09-30)

Подключение: `adb devices` -> `<серийник> device product:faraday
model:X96S_P device:faraday` (серийники и MACи ниже замаскированы —
per-unit данные, в репо им не место). Тулзы: `adb` из platform-tools
(точный путь на моей машине — в AGENTS.md).

Базовые пропсы:
```
ro.product.model = X96S_P
ro.product.board = faraday
ro.product.brand = Amlogic / vendor Droidlogic
ro.hardware = amlogic
ro.build.display.id = X96S_P_20200903-1822
ro.build.version.release = 9 (SDK 28)
ro.product.version = slimBOXtv ATV 9.16
ro.build.host = slimboxtv / user SlimHouse
kernel = Linux 4.9.113 SMP PREEMPT Thu Sep 3 18:27:01 CST 2020 armv7l
cpuinfo = 4x ARMv7 Cortex-A53 rev 4 (0xd03) — S905Y2
device-tree = g12a_u221_2g
MemTotal = 2057352 kB (~2 GB)
eMMC = /sys/block/mmcblk0: name AWMB3R, cid 15010041… (серийник eMMC
  замаскирован), size 30535680 секторов (~14.6 GiB), MID 0x15 = Samsung
/data = 10G (доступно 8.0G)
display = 1920x1080@60, density 320
```

WiFi (вывод важен для [docs/4-wifi.md](4-wifi.md): чип тот же, что чиним):
```
lsmod: 8723bs 1949696 0
/sys/module/8723bs/version: v5.2.17.1_26955.20180307_COEX20180201-6f52
dmesg:
  Wifi: bcmdhd_init_wlan_mem 1.579.77.41.9
  aml_wifi wifi: [wifi_power_ioctl] wifi interface dev type: sdio
  RTW: rtl8723bs v5.2.17.1_26955.20180307_COEX20180201-6f52
  RTW: Chip Version Info: CHIP_8723B_Normal_Chip_TSMC_F_CUT_1T1R_RomVer(0)
  RTW: rtl8723b_FirmwareDownload fw: FW_NIC, size: 32272, fw_ver=29
  RTW: rtw_ndev_init(wlan0) if1 mac_addr=44:ef:bf:XX:XX:XX (efuse-MAC
    конкретного экземпляра; у тебя будут свои байты)
  Hal_EfuseParseBTCoexistInfo_8723B: Enable BT-coex, ant_num=1
SDIO: /sys/bus/sdio/devices/sdio:0001:1 -> .../ffE05000.sd2/mmc_host/sdio,
  vendor=0x024c (Realtek), device=0xb723
ifconfig wlan0: HWaddr 44:ef:bf:XX:XX:XX Driver rtl8723bs, IP <из DHCP>
iw phy phy0 info — только Band 1: 2412-2472 MHz [1-13], HT20/HT40,
  MCS 0-7. Band 2 (5 GHz) отсутствует полностью.
BT адрес идёт следующим за WLAN (combo-чип, одна антенна).
```

ИК (вывод важен для [docs/2-remote.md](2-remote.md)):
```
/proc/bus/input/devices:
  I: Bus=0010 Vendor=0001 Product=0001 Version=0100
  N: Name="aml_keypad"
  P: Phys=keypad/input0
  S: Sysfs=/devices/platform/ff808040.rc/input/input0
  H: Handlers=kbd mouse0 event0
  + cec_input (HDMI-CEC) и virtual-search — не ИК.
/dev: crw------- 240, 0 /dev/amremote
  /sys/class/remote/amremote, /sys/class/meson-irblaster/irblaster1
  (передатчик не распаян/не используется)
dmesg:
  meson-remote: Driver init
  meson-remote: remote_probe
  meson-remote ff808040.rc: protocol = 0x1       # 0x1 = NEC
  meson-remote ff808040.rc: platform_data irq =46
  meson-remote ff808040.rc: custom_number = 3
  meson-remote ff808040.rc: ptable->custom_name = amlogic-remote-1 / custom_code = 0xfb04 / map_size = 50
  meson-remote ff808040.rc: ptable->custom_name = amlogic-remote-2 / custom_code = 0xfe01 / map_size = 45
  meson-remote ff808040.rc: ptable->custom_name = amlogic-remote-3 / custom_code = 0xbd02 / map_size = 17
Конфиги: /vendor/etc/remote.cfg (work_mode=0x1, repeat_enable=0),
  remote-0xfb04.tab, remote.tab1/2/3. Основной пульт — 0xfb04 (50 кнопок).
Живая проверка: adb shell getevent -lt /dev/input/event0 + жать пульт.
```

USB (вывод важен: порт только 2.0):
```
ls -l /sys/bus/usb/devices/: usb1 -> .../ff500000.dwc3/xhci-hcd.0.auto/usb1,
  usb2 -> .../xhci-hcd.0.auto/usb2
usb1: speed=480, version=2.00, maxchild=2; usb2: speed=5000, version=3.00, maxchild=0
dmesg: dwc3 ff500000.dwc3: Configuration mismatch. dr_mode forced to host
  amlogic-new-usb3-v2 ffe09080.usb3phy: This phy has no usb port
Тест с флешкой Toshiba TransMemory: usb 1-1: new high-speed USB device,
  /dev/block/sda -> /mnt/media_rw/E0FD-4E64, speed=480.
Вывод: всё воткнутое падает на usb1/480; usb2 без портов.
```

Команды для повторения (в каталоге с `adb`):
```powershell
.\adb.exe shell "lsmod; dmesg | grep -i -E 'rtl8723|wifi.*sdio|meson-remote|fb04|xhci|dwc3'"
.\adb.exe shell "cat /sys/bus/sdio/devices/*/vendor; cat /sys/bus/sdio/devices/*/device; iw phy phy0 info | head -n 60"
.\adb.exe shell "cat /proc/bus/input/devices; cat /vendor/etc/remote.cfg; ls -l /dev/amremote"
.\adb.exe shell "ls -l /sys/bus/usb/devices/; cat /sys/bus/usb/devices/usb*/speed"
```

## Симптомы на Lineage 22.2 (ядро 4.9.337 armv8l)

- `dhd.ko` (Broadcom) циклит `wifi_platform_set_power`, падает `-19`
  (+~11с к загрузке); SDIO `024c:b723` без драйвера.
- `/dev/amremote` нет, `meson-remote` молчит (нет DT-ноды).
- TV-сборка висит на `Searching for accessories...` (BT-пульта нет).
  Обход: Tablet-сборка `radxa0_tab` (сетап проходится USB-клавой).

