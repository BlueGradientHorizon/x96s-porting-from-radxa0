# X96S — бортовой журнал

Вся инфа о ТВ-стике X96S 2/16 и о том, что предпринималось чтобы
заставить работать X, Y, Z под LineageOS 22.2 (radxa0, Android 15).
Цель: портировщик или ИИ-агент повторяет любой результат пошагово.

Готовое на сегодня: **пульт** (разделы 5–6, скрипт `fix_x96s.py`,
раздел 8). В планах: WiFi/BT.

## 1. Железо

### 1.1. Стик X96S 2/16 (ревизия платы 2.4GHz, данные сняты вживую по adb)

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

### 1.2. Донор Radxa Zero (под него собран Lineage)

Тот же S905Y2 (ядро/GPU/VPU/HDMI общие), но обвязка другая:

| Узел | Radxa Zero | X96S | Итог |
|---|---|---|---|
| WiFi/BT | Broadcom BCM43436/43455 (`brcmfmac`) | Realtek RTL8723BS | 0% (вендор, драйвер, прошивки, SDIO-пины) |
| ИК | штатного нет (только GPIO) | meson-remote + глазок + кеймапы | нода/табы только от стика |
| USB | настоящий USB3.0 host | только USB2 | USB2-периферия везде ок |
| Boot | кнопка USB BOOT, MaskROM | reset игнорируется неродным u-boot, burn через тестпоинт eMMC | см. 3.4 |

Вывод: образы Zero стартуют (SoC один), но WiFi/BT и ИК мертвы.

### 1.3. Сырые замеры со стока (бывший X96S_live_check.md, 2026-09-30)

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

WiFi (вывод важен для §8: чип тот же, что чиним):
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

ИК (вывод важен для §5-6):
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

## 2. Симптомы на Lineage 22.2 (ядро 4.9.337 armv8l)

- `dhd.ko` (Broadcom) циклит `wifi_platform_set_power`, падает `-19`
  (+~11с к загрузке); SDIO `024c:b723` без драйвера.
- `/dev/amremote` нет, `meson-remote` молчит (нет DT-ноды).
- TV-сборка висит на `Searching for accessories...` (BT-пульта нет).
  Обход: Tablet-сборка `radxa0_tab` (сетап проходится USB-клавой).

## 3. Доступ к железу

platform-tools, USB Burning Tool 2.x (драйвер WorldCup), Python 3.8+
(только stdlib), Rust+git (разово, для `ampack`), паяльник, лупа.

### 3.1. ADB

- Сток: microUSB к ПК (`X96S_P`), рут есть (userdebug).
- Lineage: Developer options (USB + Network), `adb root` работает.
- Recovery: adb включается пунктом меню (в новых сборках вручную!).
  Sideload — `Apply from ADB`.
- Втыкание 3.5мм ИК-глазка наживую роняет USB-adb (`offline`): джек
  коротит питание, USB PHY ресетится, SoC жив. Лечение:
  `adb reconnect offline` / перетык microUSB. Глазок — только на
  обесточенном!

### 3.2. UART (главный инструмент восстановления)

На обороте платы 4 пада `VCC GND RX TX` (рядом подпись 3.3V).
Мост из ESP32-C3 Super Mini:

```cpp
void setup() {
  Serial.begin(115200);
  Serial1.begin(115200, SERIAL_8N1, 20, 21); // 20=RX моста, 21=TX моста
}
void loop() {
  while (Serial.available()) Serial1.write(Serial.read());
  while (Serial1.available()) Serial.write(Serial1.read());
}
```

Arduino IDE: `ESP32C3 Dev Module`, `USB CDC On Boot: Enabled`.
Только 3 провода (GND-GND, TX_стика→GPIO20, RX_стика→GPIO21),
VCC не подключать. PuTTY 115200 8N1.

### 3.3. U-Boot (вендорный 2015.01, `g12a_radxa0_v1#`)

- Вход: держать Enter/Space + подать питание (autoboot ~0-1с).
- `run recovery_from_flash` — в рекавери без кнопок.
- `usb start 0` + `fatload/fatwrite usb 0 <addr> <file> [size]` +
  `store read|write <name> <addr> <off> <size>` (dtbo = `0x800000`).
  Конкретный пример — откат битого dtbo заведомо целым с USB-флешки
  (флешка с `dtbo.img` из любой прошивки Lineage в полноразмерном
  USB-порту стика):
  ```
  usb start 0
  fatload usb 0 0x1000000 dtbo.img
  store write dtbo 0x1000000 0 0x800000
  reset
  ```
- Консоль ядра: `setenv initargs "${initargs} console=ttyS0,115200"`
  + `saveenv` (cmdline собирается из `initargs`, править boot.img
  бесполезно — u-boot его перезаписывает).
- Не вставлять многострочный текст в терминал: так был стерт
  загрузчик (`store erase ...` из help!). Лечится повторной прошивкой
  `aml_install_package.img` (WorldCup появляется сам).

### 3.4. Burn mode и установка Lineage (всё в Windows)

1. `aml_install_package.img` → USB Burning Tool → `Resetting board [OK]`.
2. Цикл питания с USB-клавой → Lineage Recovery.
3. `fastboot -w wipe-super super_empty.img`, Format data,
   `adb -d sideload lineage-*.zip`, reboot (первая загрузка ~1–2 мин:
   ~1 мин обычно, ~2 мин после вайпа `/data` — замерено секундомером).
4. Тестпоинт eMMC — рядом с чипом Samsung (на другой стороне платы
   от UART; фото есть на 4pda для соседней ревизии, контакты совпали):
   замкнуть пинцетом в момент подачи питания, держать до детекта
   WorldCup в Burning Tool. Наживую — просто ребут.

## 4. Диагностика (эталонные команды, в каталоге с `adb`)

```powershell
.\adb.exe shell "lsmod | grep 8723bs; dmesg | grep -iE 'rtl8723|meson-remote|fb04|xhci'"
.\adb.exe shell "cat /sys/bus/sdio/devices/*/vendor; cat /sys/bus/sdio/devices/*/device"
.\adb.exe shell "cat /proc/bus/input/devices; ls -l /dev/amremote"
.\adb.exe shell "getevent -lt /dev/input/event0"   # жать кнопки пульта
```

## 5. Пульт (ИК), часть 1: DTBO-оверлей (уровень ядра)

### 5.1. Что нужно ядру

Драйвер `meson-remote` (`CONFIG_AMLOGIC_MESON_REMOTE=y`) в ядре есть,
но в deadpool-DTB (`g12a_s905y2_deadpool`) нет ноды — драйвер не
матчится. Нужны, по running-стоку:

- `rc@0xff808040` (`compatible "amlogic, aml_remote"`, `protocol 1`,
  два MEM-ресурса `<0xff808040 0x44>` + `<0xff808000 0x20>`,
  `interrupts <GIC_SPI 196>` = `<0 196 1>`);
- `remote_pin` pinctrl (`remote_input_ao`) — pinctrl ОБЯЗАТЕЛЕН
  (без него probe падает `-22`; проверено);
- `custom_maps` (phandle из `map`) с `mapnum/map0..2` и тремя map-нодами
  (size/mapname/customcode/release_delay/keymap) — без них
  `please config correct mapnum item` и probe `-1`.

Эталон взят из стокового DTB: `_aml_dtb` из burn-образа
(`ampack unpack sbx_....img` → `meson1.dtb`, внутри gzip, 3 DTB
`u221_1g/2g/4g`; наш — `g12a_u221_2g`). Нода там `/rc@0xff808040`,
кеймапы — `/custom_maps`.
Проверка живьем: `ls /proc/device-tree/rc@*/`, `/dev/amremote`,
`aml_keypad` в `/proc/bus/input/devices`.

### 5.2. Phandle-quirk загрузчика (важно!)

U-boot 2015.01 сдвигает phandle оверлея на **+0x100**, а значения-ссылки
не трогает. Доказано вживую (`/proc/device-tree`: rc 0x101→0x201,
pinctrl-0 остался литералом). Поэтому в оверлее:

- `remote_pin: phandle 0x100`, ссылка `pinctrl-0 = 0x200`;
- `custom_maps: 0x110`, ссылка `map = 0x210`;
- `map_0/1/2: 0x111/0x112/0x113`, ссылки `map0..2 = 0x211/0x212/0x213`.

Явные `phandle` в оверлее, ломающие мерж (бутлуп!), не использовать
кроме этих. `reg`/`interrupts` — полными ячейками под `#cells=2`
корня и 3-cell GIC (урезанные копии валят дерево в немой ребут!).

### 5.3. Куда класть и как шить

- В прошивке: `dtbo.img` (mkdtbo v0, 1 entry) → `package_extract_file`
  raw в `by-name/dtbo`, контрольных сумм нет. `dtb.img` (store,
  crc32!) и блочные `*.new.dat.br` НЕ ТРОГАТЬ (кроме vendor-фикса ниже).
- Вручную: `dd if=dtbo.img of=/dev/block/by-name/dtbo` (рут,
  `dtbo.img` достать из любой прошивки Lineage) + reboot.
  Текущий dtbo_partition перед этим сдампить в файл!
- Бутлуп чинится из UART+USB-флешки (раздел 3.3), рекавери при этом
  тоже может лупиться — только UART.

## 6. Пульт (ИК), часть 2: userspace-таблицы (уровень Android)

Ядро ищет по DT-таблицам, но на boot `remotecfg{1,2,3}`
(`/vendor/bin/remotecfg`, `init.amlogic.system.rc`) перезаливают таблицы
через ioctl из **файлов** `/vendor/etc/remote.tab{1,2,3}`. Стоковый DT
полон, но файл tab2 в Lineage — от чужого пульта (нет 0x51/0x50, кривые
коды). Поэтому пофикшенный скриптом `remote.tab2` запекается прямо в
`vendor.new.dat.br` (раздел 8) — после прошивки пульт работает сразу,
без шагов на девайсе.

Запасной путь без перепрошивки (для подбора кодов!): файлы можно
подсунуть живьем — путь задается пропсом (дефолт `/vendor/etc`):
`persist.vendor.amlogic.remotecfg.path`. Рабочая схема:
`/data/remote/{remote.cfg,remote.tab1,remote.tab2,remote.tab3}` +
`setprop persist.vendor.amlogic.remotecfg.path /data/remote` +
`chcon u:object_r:vendor_configs_file:s0` на файлы (SELinux строгий,
проверено avc-denial) + `stop/start remotecfg{1,2,3}` (перезагрузка
таблиц наживую, без ребута). Внимание: проп и файлы переживают
перепрошивку без вайпа и **затеняют** запеченный фикс — для чистого
теста убирать (`rm -rf /data/remote`, пустой проп).

### 6.1. Кеймап нашего пульта (custom 0xFE01, Linux-коды, Generic.kl)

| Кнопка | scancode | Linux | Android |
|---|---|---|---|
| питание | 0x40 | 116 | POWER |
| mute | 0x41 | 113 | VOLUME_MUTE |
| вверх | 0x16 | 103 | DPAD_UP |
| вниз | 0x1a | 108 | DPAD_DOWN |
| влево | 0x51 | 105 | DPAD_LEFT |
| вправо | 0x50 | 106 | DPAD_RIGHT |
| OK | 0x13 | 28 | ENTER |
| домой | 0x11 | 172 | HOME (102 дает MOVE_HOME!) |
| recents | 0x4c | 580 | APP_SWITCH |
| назад | 0x19 | 158 | BACK |
| громк- | 0x10 | 114 | VOLUME_DOWN |
| громк+ | 0x18 | 115 | VOLUME_UP |
| настройки | 0x43 | 139 | MENU (прямого SETTINGS в evdev нет) |
| KD (0x44), мышь (0x0) | — | — | не маппятся (см. ограничения) |

### 6.2. Ограничения (честно)

- Кнопка мыши (переключение крестовина/курсор): режим зашит в драйвер
  через DT `cursor_*_scancode`, но драйвер их не читает (memset 0xFF) —
  без пересборки ядра не включить. Кнопка молчит.
- KD: назначение неизвестно, пропущена.
- `repeat_enable=0` (как в стоке): удержание не повторяет.

## 7. Файлы в рабочей папке (инвентарь)

- `fix_x96s.py` — тонкая точка входа (аргументы + вызов).
  Вся логика — в пакете `x96s_patcher/` (раздел 8):
  `errors`/`workdir` (база), `fdt` (парсер DTB), `ir_data`
  (кеймапы+таб пульта), `ext4` (механика debugfs), `vendor_img`
  (общий хелпер vendor-фиксов), `amlogic` (парсер/сборщик
   burn-пакетов), `fixes/` (по файлу на фикс
   с саморегистрацией + targets `ota`/`aip`), `pipeline`
   (детект типа пакета + обе ветки), `cli`.
- `bootloader-x96s.bin` — пересобранный u-boot (FIP, плата
  `g12a_radxa0_v1` + C-хук окна в `board_late_init`; payload
  для скрипта: `bootloader.img` в ПОР, `bootloader.PARTITION`
  в ПОА; ищется рядом с launch dir).
- `8723bs-4.9.337.ko` — собранный драйвер WiFi (payload для скрипта,
  ищется рядом с launch dir; НЕ стрипать!).
- `apply_x96s.py` — патчи исходников драйвера (раздел 8, repro).
- `dotconfig` — точный конфиг ядра с живого девайса (`/proc/config.gz`).
- `remote.tab2` — исправленный таб нашего пульта (эталонная копия;
  в скрипт текст встроен).
- `stock-dtb-raw.bin` — стоковый DTB-референс.
- `bt_fw/` — BT-прошивки и конфиг со стока (см. §12).
- `flash/` — всё для прошивки:
  `X96S_P_20200903-1822.img` (сток), `sbx_x96s_2gb_2.4Ghz_atv_9_16.img`
  (slimBOXtv-кастом), `super_empty.img`, подпапки `los-22.2-radxa0/`
  и `los-22.2-radxa0_tab/` (в каждой `aml_install_package.img` +
  оригинал `lineage-*-signed.zip`; `-x96s-fix.zip` собирается
  скриптом в `out/`).
- `out/` — собранные `-x96s-fix.zip` (ПОР) и
  `-radxa0[_tab]-x96s-fix.img` (ПОА) (артефакты сборки, в GitHub
  не едут — см. `.gitignore`).

## 8. fix_x96s.py

```
fix_x96s.py FIRMWARE.(zip|img)   # тип определяется по содержимому
fix_x96s.py --list               # список фиксов (с targets ota/aip)
```

Архитектура (пакет `x96s_patcher`, только stdlib + `pip install
brotli` для vendor-фикса; `fix_x96s.py` в корне — лишь импорт
`main` из `x96s_patcher.cli`):

Один аргумент — либо ПОР (recovery OTA zip), либо ПОА (Amlogic
USB-burn пакет); тип определяется по содержимому (updater-script
vs магия `0x27B51956`), печатается в консоль. Бегут только фиксы,
чьи targets покрывают тип пакета (`@register("имя", "описание",
("ota",) / ("aip",), needs=(...))` — см. карту в `x96s_patcher/__init__.py`):

- ПОР: все 4 фикса (см. реестр ниже) → `out/<stem>-x96s-fix.zip`;
- ПОА: `dtbo` (та же `fix_remote_dtbo`, но применённая
  к слоту `dtbo.PARTITION` внутри пакета) и `bootloader`
  (пересобранный u-boot в слоте `bootloader.PARTITION`, окно
  `update 700 750` вшито C-хуком мимо env) →
  `out/<stem>-<device>-x96s-fix.img` (девайс — из fingerprint
  в футере dtbo: `radxa0`/`radxa0_tab`; оба LOS-ПОА называются
  `aml_install_package.img`, без суффикса перезаписали бы друг
  друга). Штатный флоу: burn fixed-ПОА через USB Burning Tool →
  рекавери (пульт работает там чисто на dtbo, доказано живьём:
  `remotecfg` в рекавери отсутствует, `/vendor/etc/remote*` нет,
  а сканкоды из `meson-remote` сыплются) → sideload fixed-ПОР.

- `errors` — `FixError`; `workdir` — tmp-каталог в **launch dir**,
  удаляется в любом исходе;
- `fdt` — минимальный парсер/сериализатор FDT; `ir_data` — данные
  `IR_MAPS`, исправленный `FIXED_TAB2`, строитель фрагментов оверлея;
- `ext4` — механика: `debugfs` (rm/write/sif/ea, контроль по тексту),
  `e2fsck`, замена файлов с сохранением режимов/xattrs, генерация
  transfer-листов полным `new`-покрытием;
- `vendor_img.patch_vendor_image` — общий хелпер vendor-фиксов
  (brotli → замена → сжатие quality 6 → перегенерация листа);
- `fixes/` — по модулю на фикс (`dtbo`, `vendor_tabs`,
  `vendor_wifi_rc`, `vendor_wifi_ko`, `bootloader`), контракт
  `func(ctx, entries) -> (replacements, changed, summary)`.
  Ключи `entries` — КАНОНИЧЕСКИЕ имена файлов (`dtbo.img`,
  `vendor.new.dat.br`, …), общие для обоих типов пакетов: пайплайн
  сам отображает слоты транспорта на них (в OTA-зипе `dtbo.img`
  лежит как есть, в burn-пакете — как `dtbo.PARTITION`).
  Фикс объявляет `targets` (типы пакетов) и `needs` (какие файлы
  читает); нет нужного файла в пакете или чужой тип — фикс скипается
  с явной пометкой N/A в консоли (так vendor-фиксы ведут себя в ПОА:
  слота нет — чинить нечего; трейсбеков `KeyError` больше нет). Регистрация — `@register("имя", "описание",
  targets, needs)`. Порядок импортов в `fixes/__init__.py` =
  порядок прогона. Новый фикс = новый файл + одна строка импорта,
  больше ничего;
- `pipeline.cmd_patch` — детект типа, оркестрация (проверка
  updater-script / магии+CRC пакета, прогон реестра,
  пересборка с сохранением метаданных записей,
  `testzip` для zip / повторный parse для img,
  no-op при повторном прогоне); `cli` — argparse
  (`--list`, `--skip`).
- `amlogic` — свой парсер/сборщик burn-пакетов (без cargo-зависимостей;
  ampack читался только как спека): шапка 64 байта LE
  (`crc32`/`version` 1|2/`magic 0x27B51956`/`size`/`align`/`count`),
  записи фикс. длины (128 байт v1 / 576 байт v2: id/type/coff/off/size,
  `main`/`sub`-строки, `verify`, `is_backup`/`backup_id`), тело с
  паддингом нулями до align. CRC шапки = отражённый CRC32 байт `[4:]`
  с init `0xFFFFFFFF` и БЕЗ финального xor
  (т.е. `zlib.crc32(d[4:]) ^ 0xFFFFFFFF`, сверено с заголовками).
  Писатель сохраняет порядок/версию/align/флаги входа 1:1, смещения,
  размер и CRC пересчитывает; бэкапам доверяет как есть (вендорский
  пакер шарит оффсеты даже при разных данных — пересчёт по равенству
  байт воспроизвёл бы неверно); VERIFY-записи кладутся вплотную без
  паддинга (доказано невыровненными оффсетами в стоке), остальное —
  по align. Round-trip нетронутого пакета побайтов (проверено на
  обоих LOS v1; V2 только парсится — запись V2 запрещена loud-ошибкой,
  нам она не нужна). Замена в ПОА только same-size (слот eMMC
  фиксирован) и только при `verify == 0`, иначе отказ вместо порчи.
- Реестр сейчас:
  - `dtbo`: мерж оверлея в `dtbo.img` (raw-прошивка через
    `package_extract_file`, контрольных сумм нет). Идемпотентно —
    повторный прогон видит rc-ноду и пропускает. Размер файла не
    меняется (добивка нулями).
  - `vendor-tabs`: `vendor.new.dat.br` → brotli-decode → raw ext4 →
    поиск единственного `remote.tab2` (custom 0xFE01, 755 байт) →
    замена на исправленный (219 байт + пробелы до исходной длины,
    блоки и transfer.list те же — там только `new`-диапазоны без
    хэшей) → brotli-encode (quality 6, размер как у стока).
    Подпись zip ломается штатно (recovery: `Signature verification
    failed` → Yes, как для любых кастомных зипов).
- НЕ ТРОГАЮТСЯ: остальные `*.new.dat.br`, `boot.img`, `dtb.img`
  (store с crc32!), `vbmeta`, `bootloader`, updater-script,
  transfer-листы. Исходник только читается.
- Проверено: оба nightly патчатся (dtbo + vendor), zip валидны
  (`testzip`), побайтовые сверки (префикс/суффикс образа, табы,
  оверлей == боевому), исходники нетронуты, tmp чистятся даже на
  ошибках, повторный прогон идемпотентен.

### Как добавлен WiFi-фикс (готово, работает из коробки)

Драйвер 8723bs v5.2.17.1 собран из исходников rockchip_wlan под
4.9.337-aarch64 (vermagic совпал 1:1, стоковый .ko был 32-бит и не
подошел). Правки исходников (`apply_x96s.py`, применяется один раз
на чистое дерево):
- порт procfs (`proc_ops` -> `file_operations`, в 4.9 его нет);
- питание и переенумерация: `extern_wifi_set_enable` + `sdio_reinit()`
  (DOWN-UP как в стоке, иначе карта молчит после power-cycle);
- шим под вендорный Broadcom-HAL: модуль линкуется как `dhd.o`
  (HAL хардкодит пути `/sys/module/dhd/...`) + dummy-параметр
  `firmware_path` (HAL пишет туда при configureChip, значение
  игнорируется — прошивка вшита в драйвер);
- сборка с `CONFIG_POWER_SAVING=n` (дефолты ACTIVE/IPS_NONE; с PS=MAX
  шли пачки `_sd_read FAIL(-84)`).
Исключение из правила «Makefile не трогать»: переименование цели
(`dhd-y`) — иначе имя модуля не сменить. Стоковый .ko НЕ использовать,
собранный НЕ стрипать (`strip` ломает ELF для загрузчика 4.9 —
`Module len truncated`, проверено).

Запекание (скрипт линуксовый, запускать на Linux-хосте;
требует debugfs/e2fsck/python3-brotli — проверяет сам в самом начале):
- transfer-листы состоят только из `new`-команд (full-OTA, без хэшей),
  updater-script сверяет только имена файлов — поэтому раскладка
  блоков свободна: правим на уровне файлов, листы генерируем заново.
- `vendor_dlkm.new.dat.br`: `dhd.ko` (Broadcom, тут мертвый груз)
  перезаписывается нашим драйвером настоящим ext4-драйвером
  (`debugfs`: штатная аллокация, режим и `security.selinux`
  сохраняются), затем `e2fsck -f` дочиста. Никаких дыр/leak.
- `vendor.new.dat.br`: `init.amlogic.wifi_buildin.rc` — ранний
  `on boot` insmod + `chmod 0666` на ноду `firmware_path`.
  Обе строки load-bearing (доказано живьём, см. ниже). Плюс
  `remote.tab2`. Внешние прошивки НЕ нужны.
  MAC нигде не зашит: драйвер берёт efuse-MAC чипа, у каждого
  экземпляра свой.

Почему именно так (корень стены TV, доказан по логам 2026-10-03):
вендорный HAL при `configureChip` открывает на ЗАПИСЬ
`/sys/module/dhd/parameters/firmware_path`. Было два слоя отказа:
(1) `ENOENT` — наш модуль звался `8723bs` (лечится именем `dhd`);
(2) `EACCES` — нода `0644 root:root`, а HAL работает от юзера `wifi`.
`0666` прямо в `module_param` не компилируется (ядро запрещает
world-writable параметры: `VERIFY_OCTAL_PERMISSIONS`), поэтому
`chmod 0666` в rc сразу после insmod. Решающий эксперимент: возврат
`0644` + сброс значения -> `Permission denied` + `configureChip`
code 9; стоковая станза `on property:vendor.bcm_wifi=bcm` в
`init.amlogic.wifi.rc` пермы НЕ чинит (фаерится до создания ноды
и не перефаерится). `wlan.driver.status=ok` на успех не влияет.
Миф «случайный MAC при раннем probe» убит чтением исходников:
`rtw_check_invalid_mac_address` реджектит нули/FF/мультикаст/
локальный бит — драйвер отдаёт либо efuse-MAC, либо пишет
`invalid mac addr` в dmesg; «левые» MAC в `ip link` — рандомизация
самого Android, не драйвера.

### Почему включение wifi сделано именно так (а не как в стоке)

Сток грузит драйвер один раз и поздно: первое включение wifi
(~t=76) -> power DOWN-UP + reinit + insmod фреймворком, probe
сразу чистый. Так можно, потому что к t=76 система устаканилась
и чип гарантированно отвечает. У нас драйвер грузится рано
(`on boot`, probe ~t=7.3): Broadcom-HAL строит карту интерфейсов
один раз при своём старте и позднюю загрузку не усыновляет
никогда (проверено rmmod/insmod-циклом) — поэтому insmod обязан
быть ранним. Ранний probe при этом стабильно чистый: DOWN-UP +
синхронный reinit в `module_init` (как сток, но без единого слипа —
эксперименты А/Б 2026-10-04 убрали 1.5-с settle и все паузы,
3/3 холодных бута: DOWN/UP ~t=7.2, probe ~t=7.3), efuse-MAC
с первого раза, ноль `-84`.
Если чип разово не ответил — штатный SelfRecovery фреймворка
ретраит сам. Никаких сервисов, скриптов, поллинга и слипов:
один insmod в rc + штатные механизмы. Коннект к настроенной точке поднимается
сам, ~10 с после лаунчера (замерено секундомером; у стока весь
коннект вообще на t≈85+).

- `vendor.transfer.list` / `vendor_dlkm.transfer.list` перегенерируются
  полным `new`-покрытием по размеру ФАЙЛА (в образах есть паддинг нулями
   за концом ФС — стоковый лист его покрывает, наш тоже). updater-script
   не трогается. Идемпотентность — содержательная: прогон на уже
   пофикшенном зипе заканчивается no-op (`already fixed, copied
   unchanged`). Побайтового равенства между двумя сборками подряд
   нет (mtime перезаписанных файлов в образах = время сборки),
   на установку это не влияет (в листах только `new` без хэшей).
- Проверено: loop-mount образов самим ядром 4.9 + `insmod` с loop =
  wlan0 (md5 сходится с payload, сразу WPA-handshake); затем прошивка
  грузится, wifi поднимается сам, коннект к домашней точке.
- wififix-метод через sideload УСТАРЕЛ и не работает (в рекавери
  /vendor read-only) — вместо него хирургия образов внутри скрипта.
- BT: та же микруха по UART/H5 (`hciattach`/`rtk_hciattach`?) — отдельно.

### Почему vendor-фиксы не едут в ПОА (доказано, вопрос закрыт)

Автор slimBOXtv пихает всё в ПОА потому, что у него есть куда:
его пакет (Android 9, статическая разметка) везёт физические
`system` 1.1 ГБ + `vendor` 229 МБ + `product` + `odm` отдельными
`PARTITION`-слотами с `VERIFY`-парами (проверено парсером).
У Lineage (Android 15, dynamic partitions) этих слотов нет:
физическая таблица из его же `dtb` — `logo/recovery/misc/dtbo/
cri_data/frp/rsv/metadata/vbmeta/param/boot/tee/super/cache/data`,
а `system/vendor/product/odm/system_ext/vendor_dlkm` создаются как
ЛОГИЧЕСКИЕ внутри `super` файлом `dynamic_partitions_op_list`
в момент установки (`add vendor …; resize vendor 104595456`).
В ПОА при этом лежит `super` 4696 байт — заглушка `super_empty`.
Burning Tool шьёт по физической таблице — vendor-байтам там не
соответствует никакой адрес. Это не ограничение парсера, а схема
разметки: статика ушла в `super`, а `super` едет только через ПОР.
Полное покрытие = два носителя: ПОА (загрузочная статика + dtbo)
и ПОР (динамика). Единственный теоретический обход — собирать
полный образ `super` через `lpmake` — отдельный проект, не этот.

### Сборка драйвера с нуля (repro)

Почему без модификаций никак (все четыре причины вынужденные):

| Причина | Сток (Android 9) | Lineage |
|---|---|---|
| битность/vermagic | родной 32-битный `.ko` | пересборка обязана (ядро aarch64, `modversions`, `MODULE_FORCE_LOAD` выкл) |
| procfs API | родной 2018 (`file_operations`) | зеркало портировали вперёд под новые ядра — откатываем `proc_ops` обратно |
| DOWN-UP + reinit | делает фреймворк (`wifi_power_ioctl`, t≈74–76) | делать некому (HAL чужой) — драйвер делает сам в `module_init` |
| `dhd`-шим | не нужен (стек Realtek-aware) | требует бинарь Broadcom-HAL |

То есть стоковый драйвер немодифицирован (версия совпадает с апстримом
1:1) — модифицирована *система вокруг него*. На Lineage систему заменить
нельзя (бинарь), поэтому её функции вшиты в сам `.ko` плюс шим.

Исходники:
- Ядро: `https://github.com/LineageOS/android_kernel_amlogic_linux-4.9`,
  ветка `lineage-22.2` (это `TARGET_KERNEL_SOURCE` из
  `device/amlogic/g12-common/BoardConfigCommon.mk`). Точный конфиг —
  только с живого девайса (`/proc/config.gz`), не дефолтный!
- Драйвер: `https://github.com/youling257/rockchip_wlan` (один коммит —
  чистый импорт `rtl8723bs v5.2.17.1_26955.20180307`, та же версия что
  в стоке), нужен подкаталог `rtl8723bs`. Зеркало: `openlumi/rtl8723bs`
  (тоже уже под новые ядра — не брать).
- Почему нельзя взять готовый .ko: стоковый 32-бит (ARMv7), ядро
  Lineage 64-бит (aarch64) — несовместимы в принципе;
  `MODULE_FORCE_LOAD` в ядре выключен, чужой .ko не встанет никак.

Стенд: виртуалка Ubuntu 22.04/24.04 (4+ ГБ RAM, 30+ ГБ диска),
сеть бриджом + SSH. Пакеты:
`build-essential git bc flex bison libssl-dev libelf-dev gcc-aarch64-linux-gnu gcc-arm-linux-gnueabihf`
(второй — только как `CROSS_COMPILE_ARM32` для compat vDSO).

Команды:
```bash
git clone --depth 1 --branch lineage-22.2 \
  https://github.com/LineageOS/android_kernel_amlogic_linux-4.9.git ~/k
# конфиг ТОЛЬКО через exec-out (adb shell калечит бинарник переводами строк!),
# на Linux обязательно распаковать (иначе silentoldconfig падает):
adb exec-out "cat /proc/config.gz" > config.gz
scp config.gz linux-host:~/.kconfig-x96s   # или как удобно
# на Linux:
zcat ~/.kconfig-x96s > ~/k/.config
cd ~/k && make ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- \
  CROSS_COMPILE_ARM32=arm-linux-gnueabihf- modules_prepare
# долгая часть (20-40 мин), она же генерит Module.symvers с CRC:
cd ~/k && make ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- \
  CROSS_COMPILE_ARM32=arm-linux-gnueabihf- \
  KCFLAGS="-Wno-error -Wno-error=implicit-function-declaration -Wno-error=implicit-int" \
  modules -j$(nproc)
```

Патчи драйвера — готовые: скрипт `apply_x96s.py`
(`python3 apply_x96s.py ~/8723bs`, сверен с боевым деревом —
отличается только убранным дебагом). `CONFIG_PROC_DEBUG` в
`include/autoconf.h` НЕ выключать (тест-хуки зовутся из боевого кода,
без них не линкуется). Остальное — только через `apply_x96s.py`
(единственное исключение: переименование цели в `dhd.o` правит
сам `Makefile` — иначе имя модуля не сменить, см. § выше).
Ниже то же самое в виде диффов.

Патч 1 — порт procfs (`struct proc_ops` есть только с ядра 5.6),
одной строкой:
```bash
cd ~/8723bs && sed -i 's/struct proc_ops/struct file_operations/g; s/\.proc_open/.open/g; s/\.proc_read/.read/g; s/\.proc_lseek/.llseek/g; s/\.proc_release/.release/g; s/\.proc_write/.write/g' os_dep/linux/rtw_proc.c
```
(меняет 1 сигнатуру + 7 структур `rtw_*_proc_ops`, имена вида
`rtw_drv_proc_seq_proc_ops` остаются).

Патч 2 — питание и переенумерация (`os_dep/linux/sdio_intf.c`):
```diff
--- a/os_dep/linux/sdio_intf.c
+++ b/os_dep/linux/sdio_intf.c
@@ -31,10 +31,22 @@
 #include <linux/acpi.h>
 #include <linux/acpi_gpio.h>
 #include "rtw_android.h"
+
 #endif
 static int wlan_en_gpio = -1;
 #endif /* CONFIG_PLATFORM_INTEL_BYT */
 
+#include <linux/of.h>
+#include <linux/of_device.h>
+#include <linux/mmc/host.h>
+#include <linux/string.h>
+
+/* X96S: platform wifi power + MMC rescan (see probe below). */
+extern int extern_wifi_set_enable(int is_on);
+struct mmc_host;
+extern void mmc_detect_change(struct mmc_host *host, unsigned long delay);
+extern void sdio_reinit(void);
+
 #ifndef dev_to_sdio_func
 #define dev_to_sdio_func(d)     container_of(d, struct sdio_func, dev)
 #endif
@@ -828,6 +840,19 @@
 
 
 
+
+	/* X96S (amlogic g12a): keep the on-board RTL8723BS powered;
+	 * the card was revived by sdio_reinit() in module_init. */
+	{
+		extern_wifi_set_enable(1);
+		if (func->card && func->card->host) {
+			unsigned long deadline;
+			mmc_detect_change(func->card->host, 0);
+			deadline = jiffies + msecs_to_jiffies(1500);
+			while (time_before(jiffies, deadline))
+				msleep(100);
+		}
+	}
 	dvobj = sdio_dvobj_init(func, id);
 	if (dvobj == NULL) {
 		goto exit;
@@ -1090,11 +1115,19 @@
 
 }
 
+static void x96s_power_and_rescan(void)
+{
+	extern_wifi_set_enable(1);
+	msleep(300);
+	sdio_reinit();
+	msleep(500);
+}
+
 static int rtw_drv_entry(void)
 {
 	int ret = 0;
 
 	RTW_PRINT("module init start\n");
 	dump_drv_version(RTW_DBGDUMP);
 #ifdef BTCOEXVERSION
 	RTW_PRINT(DRV_NAME" BT-Coex version = %s\n", BTCOEXVERSION);
@@ -1117,6 +1158,7 @@
 	rtw_ndev_notifier_register();
 	rtw_inetaddr_notifier_register();
 
+	x96s_power_and_rescan();
 	ret = sdio_register_driver(&sdio_drvpriv.r871xs_drv);
 	if (ret != 0) {
 		sdio_drvpriv.drv_registered = _FALSE;
```
Зачем каждая часть: `extern_wifi_set_enable` — включает питание чипа
через штатный aml_wifi-драйвер (иначе тишина); `sdio_reinit()` —
amlogic-ресет SDIO именно для Realtek 024C (оживляет карту после
power-cycle, который устраивает dhd при загрузке); паузы дают
переенумерации завершиться.
Патч 3 — шим под Broadcom-HAL (`os_dep/linux/os_intfs.c` +
`Makefile`): dummy-параметр `firmware_path` (charp 0644) и
переименование цели в `dhd.o` (`dhd-y := $(8723bs-y)`).

Сборка драйвера (2-5 мин; power-save выключен — см. ниже зачем):
```bash
cd ~/8723bs && make KSRC=~/k ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- \
  CROSS_COMPILE_ARM32=arm-linux-gnueabihf- CONFIG_POWER_SAVING=n \
  USER_EXTRA_CFLAGS="-Wno-error -Wno-error=header-guard -Wno-error=address -Wno-error=format -Wno-error=stringop-overflow -Wno-error=stringop-truncation -Wno-error=implicit-fallthrough -Wno-error=unused-but-set-variable -Wno-error=misleading-indentation -Wno-error=comment -Wno-error=return-mismatch"
```

### Как поднимает wifi сток (эталон, снято живьём 2026-10-02)

- t=1.5с: `aml_wifi` probe (power_on_pin=482 — тот же пин, что
  в дедпульном DT; наша прошивка дёргает настоящий WL_REG_ON).
- t=74-75с: `usb_power_control` power DOWN, затем UP +
  `sdio_reinit` + `wifi_power_ioctl up`. Никто не трогает wifi
  раньше минуты! Затем фреймворк/HAL грузит 8723bs.ko (t≈76)
  (в init-rc никакого insmod wifi-драйвера нет вообще).
- Probe девственно чист: efuse читается с первого раза, MAC
  из efuse, ноль power-seq ошибок, **ноль `-84` за всё время**
  (и это с power_mgnt=2/ips=1!). Вывод: правильная
  последовательность (DOWN-UP + позднее включение) = чистый
  линк; наши ранние включения без DOWN давали маргинальное
  состояние чипа (пачки `-84`, разрывы). Поэтому наш драйвер
  теперь тоже делает DOWN-UP (см. патч 2 в apply_x96s.py),
  а power-save всё равно выключен (страховка, стику не нужен).

Про power-save отдельно: дефолты драйвера — `rtw_power_mgnt=2`
(MAX) + `rtw_ips_mode=1`. На нашей сборке с ранним включением
сон/пробуждение чипа гнали пачки SDIO-ошибок (`_sd_read
FAIL(-84)`, `cpwm polling timeout`) вплоть до разрыва линка;
с `=0`/`=0` — ноль ошибок и 0% потерь (проверено живьём
двухминутным пингом). Поэтому собираем с `CONFIG_POWER_SAVING=n`
(дефолты становятся `ACTIVE`/`IPS_NONE`, проверяется чтением
`/sys/module/8723bs/parameters/rtw_power_mgnt`).

Проверка: `vermagic` обязан быть
`4.9.337 SMP preempt mod_unload modversions aarch64`
(смотреть строками в .ko). `insmod` вручную + `ip link show wlan0`
(MAC из efuse). Внешние прошивки НЕ нужны (firmware в hal-массивах).
Собранный .ko НЕ стрипать (ломает ELF для загрузчика 4.9).

### Сборка загрузчика с нуля (repro)

Всё ниже — на Linux-хосте (та же VM, что для патчера). Раскладка
каталогов важна: `build.sh` ждёт исходники в `../u-boot` рядом
с собой.

```bash
sudo apt install build-essential git bc bison flex libssl-dev \
  gcc-aarch64-linux-gnu gcc-arm-linux-gnueabihf
mkdir -p ~/uboot && cd ~/uboot
git clone https://github.com/LineageOS/android_hardware_amlogic_u-boot_build u-boot_build
git clone https://github.com/LineageOS/android_hardware_amlogic_u-boot u-boot
cd u-boot && git checkout fd4a7d4 && cd ..
```

Правка — 4 строки в `u-boot/board/amlogic/g12a_radxa0_v1/g12a_radxa0_v1.c`,
в `board_late_init()`, сразу после двух существующих `run_command`
(`factory_reset`/`upgrade_step`-веток). Окно делается из C-кода,
а НЕ вставкой `run try_auto_burn;` в дефолты `g12a_radxa0_v1.h`:
текст `switch_bootmode` берётся из SAVED env, который всегда бьёт
дефолты (доказано живьём и дампами env, см. §13), поэтому правка
дефолтов старые установки не лечит никогда. Хук вызывает
скомпилированную команду `update` напрямую — от env не зависит:

```diff
 		run_command("if itest ${upgrade_step} == 1; then "\
 						"defenv_reserv; setenv upgrade_step 2; saveenv; fi;", 0);
+		/* X96S: stock cold-boot WorldCup flash, env-independent. */
+		run_command("if test ${reboot_mode} = cold_boot; then update 700 750; fi;", 0);
 		/*add board late init function here*/
```

(`reboot_mode` выставляет `get_rebootmode` строкой выше — рантайм,
не saved; `update 700 750` — те же 700/750 что в стоке.)
Строку `run try_auto_burn;` в дефолты `g12a_radxa0_v1.h` НЕ возвращать:
когда-нибудь `defenv` её размножит в saved env и окно станет двойным.

Тулчейн: system-gcc закрывается симлинками под имена, которых
ждёт `build.sh` (плюс врапперы, т.к. дерево прибито `-Werror`
после всех флагов):

```bash
for t in gcc ld objcopy objdump ar nm strip readelf; do
  sudo ln -sf /usr/bin/aarch64-linux-gnu-$t /usr/local/bin/aarch64-none-elf-$t
done
for t in gcc cpp objcopy objdump ar nm strip readelf ld; do
  sudo ln -sf /usr/bin/arm-linux-gnueabihf-$t /usr/local/bin/arm-none-eabi-$t
done
printf '%s\n' '#!/bin/sh' \
  'exec /usr/bin/aarch64-linux-gnu-gcc "$@" -Wno-error -Wno-int-conversion' \
  | sudo tee /usr/local/bin/aarch64-none-elf-gcc >/dev/null
sudo chmod +x /usr/local/bin/aarch64-none-elf-gcc
printf '%s\n' '#!/bin/sh' \
  'exec /usr/bin/aarch64-linux-gnu-ld.bfd "$@" --no-warn-rwx-segments' \
  | sudo tee /usr/local/bin/aarch64-none-elf-ld >/dev/null
sudo chmod +x /usr/local/bin/aarch64-none-elf-ld
# шим под новый gcc (untracked, в diff только правка):
cp u-boot/include/linux/compiler-gcc4.h u-boot/include/linux/compiler-gcc15.h
```

Сборка чистой целью `u-boot.bin` (полный `make` упрётся в `bl301.bin` —
это SCP-прошивка, новым gcc не линкуется; в FIP ему нулевой слот,
для нас не нужен — цель обходит это стороной):

```bash
cd u-boot && make g12a_radxa0_v1_defconfig
PATH="/usr/local/bin:$PATH" CROSS_COMPILE=aarch64-none-elf- \
  make u-boot.bin -j$(nproc)
```

Проверка: в `build/u-boot.bin` строка дословно
(`strings ... | grep cold_boot`: `...cold_boot; then update 700 750;...`
ровно 1 раз, `run try_auto_burn` — 0), размер
1100160 байт. FIP довершает штатный скрипт (блобы уже в репо,
`aml_encrypt_g12a` статический):

```bash
cd ../u-boot_build
./generate-bins-new.sh fip-radxa-zero ../u-boot/build/u-boot.bin g12a_radxa0_v1-base
# -> uboot-bins-g12a_radxa0_v1-base-*/u-boot.bin (1248112 байт):
#    ToC 1:1 как в LOS (те же UUID/оффсеты, другое только тело BL33)
```

Готовый FIP (`u-boot.bin`, 1248112 байт) — payload
`bootloader-x96s.bin` в корне рабочей папки: `bootloader.img`
в ПОР, `bootloader.PARTITION` в ПОА (меньше слота 1261424 —
влезает; тул шьёт по таблице, stale-хвост не мешает).

## 9. Ловушки (набитые шишки)

1. Вставка многострочного текста в UART выполняет его как команды
   (`store erase boot/dtb` → WorldCup + потеря ключей usid/mac).
2. ИК-глазок наживую = `adb offline` (не ребут!). `adb reconnect`.
3. `/data` шифрован (FBE): правки настроек оттуда только из системы.
4. `/vendor` забит 100%, запись невозможна даже после resize2fs
   (битая аллокация; e2fsck/resize не лечат). Прямая запись блоков
   работает, ФС — нет. Обход: `/data` + persist-проп.
5. Бутлуп от битого dtbo чинится только UART+USB (`store write dtbo`).
   Рекавери при этом тоже может лупиться.
6. Урезанные `reg`/`interrupts` в оверлее = немой ребут до консоли.
   Всегда полные ячейки (reg 2+2, interrupts 3).
7. Явные `phandle` в оверлее: загрузчик сдвигает на +0x100, ссылки
   правь заранее (раздел 5.2).
8. Ядро `console=null` в cmdline: для паник добавлять
   `console=ttyS0,115200` через `saveenv initargs` (не через boot.img).
9. TV-сборка без BT-пульта = тупик на экране поиска аксессуаров
   (`Searching for accessories...`, спаривание BT-пульта): USB-клава и
   CEC его не скипают; ставить через TAB-сборку.
10. `adb root` слетает после каждой перезагрузки; в свежем рекавери
    adb выключен штатно — включать пунктом меню вручную
    (иначе `adb devices` пуст / `unauthorized`; агент, сначала проверь
    этот пункт, потом чини драйвера).
11. Кирпич на бутлого от битой прошивки: сначала loop-mount образов
    самим ядром 4.9 (`mount -o loop` на живом стике!) + `insmod`
    с loop, и только потом шить. Проверка на VM (другое ядро) ничего
    не доказывает. e2fsck дочиста перед прошивкой.
12. Никогда не стрипать собранные .ko (`--strip-unneeded` ломает ELF
    для загрузчика 4.9: `Module len truncated`, чинится только
    пересборкой/оригиналом).
13. Файлы внутри образов меняются только настоящим ext4-драйвером
    (debugfs на Linux, не побайтовой хирургией — та убита: хрупко,
    sparse-дырки, GDT-checksum); transfer.list
    перегенерируется заново. Подводные debugfs: `write` даёт 0770
    (чинить `sif` + биты типа), `chmod`/`chown` отсутствуют, xattrs
    снимать до `rm` и возвращать после, выход debugfs проверять
    по тексту (код 0 врёт).
14. Toybox `grep -a "a\|b"` молча врёт — только `grep -aE` или
    раздельные grep'ы.
15. `logcat -d` без `-t N` виснет (буфер огромный); `logcat -b events`
    тоже. Проверки делать рано (uptime <2 мин) и без обрезки head —
    иначе пропускаются старты сервисов и строки dmesg (ротация!).
16. SelfRecovery-счётчики отравляют все тесты после 2 провалов
    («Already restarted» = мгновенный реджект, а не genuine попытка).
    Чистый тест = свежий ребут + первые 2 попытки. Ручной
    `ctl.start/stop` сервисов врёт картину — выводы только с чистых
    ребутов.
17. bind-mount проверять `md5sum` + `mount|grep` (umount может молча
    не сработать); `chcon` подбирать по оригиналу (`ls -Z`).
18. `setprop` не переживает ребут; тумблер wifi — переживает
    (`wifi_on` persists). Часы на девайсе врут — верить только
    dmesg-меткам ядра. Серийник из цифр (`offline`) лечится
    `adb reconnect offline`; диалог fingerprint'а принимается
    только пультом на экране ТВ.
19. Живой драйвер не дёргать: `rmmod` усыновлённого вешает `insmod`
    навсегда (чип клинит). Только чтение, либо чистый ребут.
20. Tombstones смотреть всегда при странностях. `iw phy ... interface
    add` → `-19`: драйвер не умеет nl80211-создание. `dumpsys`-имя
    wificond — `wifinl80211`.
21. Перед ЛЮБОЙ прошивкой писать md5 зипа в журнал (сравнить потом
    будет не с чем). Две сборки подряд дают разный md5 зипа
    (mtime файлов в образах) — это норма, не порча.

## 10. Текущее состояние и TODO (обновлять!)

Состояние на 2026-10-05:

- Загрузчик переделан: окно `update 700 750` вшито C-хуком
  в `board_late_init` (мимо env вообще), header-патч `run try_auto_burn;`
  откачен, фикс `aip-env` (env-слот) УДАЛЁН из патчера вместе
  с `env_template.bin`. Живое доказательство ещё впереди: прошить
  fixed-ПОА поверх env без вызова → холодный бут с USB в ноут →
  вспышка ~750мс → загрузка дальше.

- Прошито и работает: TV `lineage-22.2-20260925-nightly-radxa0-signed-x96s-fix.zip`
  (dtbo + tab2 + wifi: `dhd.ko` с 8723bs внутри, ранний `on boot` insmod
  + `chmod 0666 firmware_path`). Пульт проходит сетап, WiFi поднимается
  сам из коробки   с efuse-MAC экземпляра: probe ~t=7.3, ноль `-84`,
  коннект по DHCP ~10 с после лаунчера. Проверено холодными бутами
  (DOWN/UP ~t=7.2, reinit ~t=7.25, ndev ~t=7.3, детерминизм до десятых)
  и 100/100 пингов до AP без потерь.
- TAB-сборка 0923: wifi заведён тем же фиксом (ядро одно, `libwifi-hal.so`
  побайтово тот же — подход универсален). Проверено живьём 2026-10-04:
  probe ~t=38 (первый бут после прошивки медленный сам по себе),
  efuse-MAC, ноль `-84`, коннект из коробки, 50/50 пингов без потерь.
- Burn-пакеты тоже патчатся: `out/aml_install_package-radxa0-x96s-fix.img`
  и `out/aml_install_package-radxa0_tab-x96s-fix.img` (`dtbo` +
  пересобранный u-boot в слоте `bootloader.PARTITION`, 15 слотов,
  env-слота больше нет; остальное побайтово как
  в исходных LOS-ПОА; CRC пересчитан, parse валиден, слот
  bootloader побайтово равен новому payload). Флоу: burn через
  USB Burning Tool → рекавери с пультом → sideload fixed-ПОР.
- Payload `8723bs-4.9.337.ko` в корне: single, `CONFIG_POWER_SAVING=n`,
  DOWN-UP + синхронный reinit без слипов, modname `dhd`,
  dummy `firmware_path`, НЕ стрипан (md5 текущего: `753e7edd…`).
- Серия самопроизвольных ребутов 10-03 оказалась питанием от USB-порта
  ноутбука, не нашим багом: с блоком питания стабильно. pstore при
  падениях был пуст (не паники ядра).
- По дороге было: кирпич-цикл от грязного шатдауна (вылечен вайпом
  `/data`, счётчики RescueParty). Мёртвые заходы (in-driver retry,
  init-сервис, exec_background, скрипты с поллингом, su-сервис,
  boot_completed-триггер) вычищены из кода и доков.
- Оверрайдов нет: `/data/remote` удален, persist-проп пуст.
  Никаких зашитых MAC/SSID/паролей: всё per-unit берётся из efuse.
- U-boot env: дописан `console=ttyS0,115200` в `initargs` (`saveenv`,
  перешивают только вместе с bootloader). verity отключен.
- Стенд: Linux-хост для сборки (кросс-тулчейн aarch64) и запуска
  скрипта (e2fsprogs + python3-brotli). Конкретика моего стенда —
  в AGENTS.md, здесь ей не место.

Следующие шаги:

1. BT RTL8723BS (разведка со стока снята, второй заход не нужен):
   UART `/dev/ttyS1`, H5, rtkbt, прошивки в `bt_fw/` (см. §12).
2. Публикация на GitHub (репо вычищено, `.gitignore` есть).

## 11. Журнал доводки WiFi (2026-10-02/04, сырая история)

Что пробовали (bring-up):

| Дизайн | Вердикт |
|---|---|
| `on boot` insmod (как донор) | рано (t≈7), чип не всегда готов — но см. финал |
| in-driver retry ×4 | мимо (глухая стена 4/4), откачено |
| init-сервис + скрипт (rmmod рабочего) | работает, но вешает insmod навсегда — убит |
| init-сервис v2 / exec_background / su-сервис / boot_completed-триггер | работают, но скрипты/сервисы запрещены как финал — вычищены |
| ранний plain insmod + SelfRecovery | ФИНАЛ (см. §8) |

Стена TV (пала 2026-10-03): драйвер чистый, но
`configureChip` code 9 → `Unknown iface name: wlan0` → `Vendor HAL died`
→ SelfRecovery сжигает 2 рестарта → тумблер гаснет. Корень: HAL пишет
`/sys/module/dhd/parameters/firmware_path`. Два слоя: (1) `ENOENT`
(модуль звался `8723bs`) → modname `dhd` + dummy charp; (2) `EACCES`
(0644, HAL — юзер wifi) → `chmod 0666` в rc (`0666` в `module_param`
не компилируется; стоковая станза `vendor.bcm_wifi=bcm` фаерится до
создания ноды). `Unknown iface` — шум ниже по течению, не причина.
Миф «случайный MAC при раннем probe» убит исходниками:
`rtw_check_invalid_mac_address` реджектит нули/FF/мультикаст/локальный
бит — драйвер отдаёт efuse либо пишет `invalid mac addr`; «левые» MAC
в `ip link` — рандомизация самого Android. `mac_wifi=` в cmdline нет
(ключи стёрты) — efuse единственный источник, и он работает.
Эксперименты А/Б (2026-10-04): снесены probe-блок (1.5с) и все слипы
(200+300+500мс) — 3/3 и 3/3 холодных бута чисто, детерминизм до десятых.
Вис на лого 2026-10-04: вечный логотип при проверенно чистом архиве
(причина не установлена — заливка? `/data`?); лечение — полный перепрошив
через burn mode. TAB живьём 2026-10-04: новый дизайн доказан и там
(см. §10). Кирпич-цикл от грязного шатдауна: счётчики RescueParty,
лечится вайпом `/data`; не дёргать кабель при висящих ядерных операциях.

## 12. Задел на BT (делать ПОСЛЕ wifi)

Разведка со стока (второй заход не нужен): BT — UART `/dev/ttyS1`,
протокол H5 (`BtDeviceNode=?/dev/ttyS1:H5` в `rtkbt.conf`), стек rtkbt.
Прошивки в `bt_fw/`: `rtl8723bs_config`/`rtl8723bs_fw`,
`rtl8723b_config`/`rtl8723b_fw`, `rtkbt.conf`. Combo-чип: BT-адрес идёт
следующим за WLAN (одна антенна). На Lineage BT краш-лупится в фоне
(`com.android.bluetooth`, HciHal tombstones) — ожидаемо, пока не сделан.

## 13. Журнал burn-пакетов (2026-10-04/05, сырая история)

Идея: один аргумент — ПОР или ПОА, детект по содержимому, каждому
типу свои фиксы; флоу burn ПОА → рекавери пультом → sideload ПОР.
По дороге было: двухаргументный merge (патчить разделы ПОР и вшивать
в ПОА) — отменён в пользу одноаргументного режима (проще, нечему
рассинхронизироваться); спор «vendor обязан ехать и в ПОА» — убит
фактами (§8, «Почему vendor-фиксы не едут в ПОА»).
Формат снят с исходников ampack (клонировался в `/tmp`, зависимость
не тянем): CRC без финального xor (`zlib.crc32(d[4:]) ^ 0xFFFFFFFF`,
сошлось с заголовками), VERIFY вплотную без паддинга (невыровненный
оффсет в стоке), бэкапы — доверять флагам (сток шарит оффсет при
разных данных). LOS-ПОА: V1, align 4, 15 записей, VERIFY нет вообще.
ПОА и ПОР — sibling-билды (`49d2b6e697:userdebug/test-keys` vs
`06e1d7a7a8:user/release-keys` в fingerprint dtbo), побайтового
равенства разделов нет и не должно быть. Доказано живьём в рекавери:
без `remotecfg` и без `/vendor/etc/remote*` сканкоды из `meson-remote`
сыплются — одного dtbo хватает для пульта в рекавери.
Позже: транслит `por`/`poa` в коде заменён на `ota`/`aip`;
`dtbo` стал единым фиксом на оба типа (канонические имена файлов +
`needs`, слоты маппит пайплайн; скипы всегда с N/A-причиной).
Позже: `aip-env` (env-слот в пакете) сначала УДАЛЁН как мусор,
потом ВОЗВРАЩЁН — живьём доказано, что saved env всегда бьёт
compiled дефолты (новый загрузчик + env без вызова = тишина),
поэтому нужна пара: `bootloader` покрывает стёртый env,
`env.PARTITION` — живой (шаблон без серийника, keyman самолечит).
Писатель env пойман меткой (`markertest` убит за один ребут):
`board_late_init` (`g12a_radxa0_v1.c`) при КАЖДОЙ загрузке:
`reboot_mode == factory_reset` → `defenv_reserv;save`,
`upgrade_step == 1` → `defenv_reserv; set upgrade_step 2; saveenv`.
То есть env пересоздаётся из дефолтов текущего загрузчика при
сбросах/апгрейд-флоу — текущий env уже с вызовом (наш загрузчик).
Окно длиннее стокового запрещено: выход даёт третий аргумент
(`update 700 750`), двуаргументный `update N` висит вечно штатно
(сессия ждёт кнопок) — доказано кодом (`need_check_timeout = 0`
после энумерации, `_auto_burn_time_out_base` только с argv[2])
и живьём. Нода `bootloader` начинается с 512 нулей (FIP с +512),
`bootloader0/1` — с нуля: md5-сверки читать со сдвигом.

WorldCup-расследование (2026-10-05): N burn mode задаётся НЕ разделом
прошивки, а u-boot env: `usb_burning=update 1000` (1000 мс ожидания
SOF хоста → `Try connect time out` → PHY off → загрузка дальше;
команда `update` = `do_v2_usbtool`). Триггеры в живом env стика
(считан с `/dev/block/by-name/env`, CRC сошёлся): хвост `storeboot`
(незагрузка ядра), `switch_bootmode` при `reboot_mode=update`;
`upgrade_key`/`forceupdate`/`irremote_update` в env есть, но в preboot
не вызываются. `env`-айтема нет ни в одном из 4 burn-пакетов
(сток/sbx/2×LOS), BL33 везде сжат (lz4) — статикой env не достать.
Итоги живьём: `reboot bootloader` из рекавери → straight to system
(путь update мёртв); `misc` пуст post-hoc; `bootdelay=1`;
в `initargs` стоит `console=null` — правка `ttyS0` через saveenv
в текущем env ОТСУТСТВУЕТ. Финал: `adb reboot update` с живой
системы — стик уходит в WorldCup (проверено 2026-10-05): команда
`update` в LOS u-boot есть, BCB-тракт `reboot_mode=update` работает.
Вход в burn mode без пинцета — только так (`reboot bootloader`
ведёт в fastbootd, не в WorldCup).
НАЙДЕНО (сток прошит, env снят и сравнен побайтово): вспышку
`~750ms` даёт `run try_auto_burn` (= `update 700 750`) в ветке
`cold_boot` переменной `switch_bootmode` — есть в стоковом env,
НЕТ в LOS env (ни в дефолтах radxa0, ни в сохранённом). Каждый
холодный бут: WorldCup ~750ms → таймаут → `storeargs` → система.
Деревья: сток — vendor 2015.01 от 03.09.2020, плата u221 (хеша
в баннере нет, дерево неизвестно); LOS — `LineageOS/
android_hardware_amlogic_u-boot`, коммит `fd4a7d4` (полный
`fd4a7d45096f5f66f9afba13dacfa29c271aaf47`, `devkits: radxa02pro:
Match Radxa's LPDDR4 configuration`), плата `g12a_radxa0_v1`
(сборка через `hardware/amlogic/u-boot_build/build_radxa0.sh`,
FIP `fip-radxa-zero`): в `g12a_radxa0_v1.h` строки 165-167 cold_boot
БЕЗ вызова, `CONFIG_AML_V2_FACTORY_BURN=1` (команда есть).
СОБРАН (2026-10-05, дерево в домашке VM — `/var/tmp` ребуты не
переживает, теперь `~/u-boot`, коммит `fd4a7d4` + C-хук 4 строки,
патч — в `patches/uboot-coldboot-window.patch`); `u-boot.bin` 1100160
байт собран system-тулчейном
через симлинки/wrapper'ы (`aarch64-none-elf-*` → `aarch64-linux-gnu-*`,
`arm-none-eabi-*` → `arm-linux-gnueabihf-*`, шим `compiler-gcc15.h`,
`-Wno-error`/`-Wno-int-conversion` довеском, `--no-warn-rwx-segments`
для ld) — в бинарнике строка окна ×1 (`cold_boot; then update 700 750`),
старого вызова ×0, баннер `2015.01-gfd4a7d4-dirty`. FIP упакован
`generate-bins-new.sh` (`uboot-bins-g12a_radxa0_v1-base-*`:
`u-boot.bin`/`.sd.bin`/`.usb.bl2`/`.usb.tpl`, шифрован, строк нет —
как в стоке). `bl301.bin` (SCP) не собирается новым gcc
(`-mfloat-abi=hard` без FPU) — в FIP ему слот нулевой, не нужен.
Доказательство, что бинарник из этого дерева: баннер
`2015.01-gfd4a7d4509` = `g` + первые 10 hex коммита, а дата баннера
(09:42:59) = дата коммита (14:42:59 +0100 = 09:42 EDT —
`build_radxa0.sh` штампует дату коммита через `SOURCE_DATE_EPOCH`).
TV и TAB везут побайтово один и тот же bootloader (sha256 сошёлся). Выход даёт
третий аргумент (auto-burn таймер 750), не первый: двуаргументный
`update N` висит вечно штатно (так работает `reboot update`).
Точная семантика из `usb_pcd.c`/`optimus_core.c`: argv[1] — бюджет
до энумерации в мс (нет SOF за половину → `noSof`, всего дольше →
`Try connect time out`; после `SET_CONFIGURATION` снимается
(`need_check_timeout = 0`)); argv[2] — окно после энумерации
в мс на IDENTIFY от тула (`_auto_burn_time_out_base` ставится
в `SET_CONFIGURATION`, превышение → выход из burn-цикла в загрузку).
Нет argv[2] — нет выхода после энумерации (сессия ждёт кнопок);
нет хоста вообще — срабатывает argv[1]. Наблюдаемые ~750мс =
истечение argv[2].
 LOS-фикс = вставить `run try_auto_burn;` в ту же ветку (файл
`env_tryautoburn.bin` собран и сверен: ровно +17 байт, CRC ок;
применяется одной `dd` из рутового adb, вторая копия env не
трогается). Заодно объяснилось зависание с `update 3000` в preboot:
гонка с виндовым драйвером (аттач ~1-2с): 700мс обычно успевают
выйти до аттача, 1000+ — уже нет, девайс уходит в сессию навсегда.
Окно длиннее стокового делать НЕЛЬЗЯ. Стоковый preboot также зовёт
`upgrade_key`+`upgrade_adc_key` (в LOS заменены на `recovery_key`) —
для вспышки не нужны, не трогаем.
 Разгадка «env меняется без env в пакетах» (2026-10-05, дампы сняты
живём через `adb exec-out dd`, CRC сошлись): пакеты env не везут
(все 4 проверены парсером: сток/sbx по 28 записей, оба LOS по 15),
но сам новый загрузчик при первой загрузке после вайпа пересоздаёт
saved env из СВОИХ дефолтов (`board_late_init`: `factory_reset` →
`defenv_reserv;save`, `upgrade_step==1` → `defenv_reserv…;saveenv`).
Стоковый burn → env С вызовом (первая копия валидна, вторая — нули);
оригинальный LOS burn → env БЕЗ вызова (`upgrade_step=2`, обе копии
валидны, дифф только рантайм-мусор: `bootargs`/`reboot_mode`/hdmi).
Отсюда же ответ, почему header-патч `run try_auto_burn;` в дефолтах
не сработал живьём: зашивается он только в момент `defenv`, а тест
был «новый загрузчик + старый env» при обычной загрузке
(`upgrade_step` уже `2` — `defenv` не fired, saved env победил).
OTA-путь и обычные ребуты `defenv` не триггерят вообще — поэтому
дефолтная правка откачена, а окно вшито C-хуком в `board_late_init`
(`if cold_boot → update 700 750`, мимо env; семантика сверена
с `optimus_core.c:60-74` + `usb_pcd.c:275-303,431-434,573-587`).
Новый `u-boot.bin` 1100160 байт (строка окна ×1, старого вызова ×0),
FIP 1248112, payload обновлён, фикс `aip-env` + `env_template.bin`
удалены, все 4 артефакта пересобраны (в ПОА 15 слотов, env-слота нет,
слот bootloader побайтово равен payload). Живой тест впереди:
fixed-ПОА поверх env без вызова → вспышка → загрузка.
