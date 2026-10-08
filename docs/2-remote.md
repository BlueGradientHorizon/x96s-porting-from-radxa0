# Пульт ИК: ядро и userspace

## Пульт (ИК), часть 1: DTBO-оверлей (уровень ядра)

### Что нужно ядру

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

### Phandle-quirk загрузчика (важно!)

U-boot 2015.01 сдвигает phandle оверлея на **+0x100**, а значения-ссылки
не трогает. Доказано вживую (`/proc/device-tree`: rc 0x101→0x201,
pinctrl-0 остался литералом). Поэтому в оверлее:

- `remote_pin: phandle 0x100`, ссылка `pinctrl-0 = 0x200`;
- `custom_maps: 0x110`, ссылка `map = 0x210`;
- `map_0/1/2: 0x111/0x112/0x113`, ссылки `map0..2 = 0x211/0x212/0x213`.

Явные `phandle` в оверлее, ломающие мерж (бутлуп!), не использовать
кроме этих. `reg`/`interrupts` — полными ячейками под `#cells=2`
корня и 3-cell GIC (урезанные копии валят дерево в немой ребут!).

### Куда класть и как шить

- В прошивке: `dtbo.img` (mkdtbo v0, 1 entry) → `package_extract_file`
  raw в `by-name/dtbo`, контрольных сумм нет. `dtb.img` (store,
  crc32!) и блочные `*.new.dat.br` НЕ ТРОГАТЬ (кроме vendor-фикса ниже).
- Вручную: `dd if=dtbo.img of=/dev/block/by-name/dtbo` (рут,
  `dtbo.img` достать из любой прошивки Lineage) + reboot.
  Текущий dtbo_partition перед этим сдампить в файл!
- Бутлуп чинится из UART+USB-флешки (раздел 3.3), рекавери при этом
  тоже может лупиться — только UART.

## Пульт (ИК), часть 2: userspace-таблицы (уровень Android)

Ядро ищет по DT-таблицам, но на boot `remotecfg{1,2,3}`
(`/vendor/bin/remotecfg`, `init.amlogic.system.rc`) перезаливают таблицы
через ioctl из **файлов** `/vendor/etc/remote.tab{1,2,3}`. Стоковый DT
полон, но файл tab2 в Lineage — от чужого пульта (нет 0x51/0x50, кривые
коды). Поэтому пофикшенный скриптом [remote.tab2](../remote.tab2) запекается прямо в
`vendor.new.dat.br` (см. [docs/3-patcher.md](3-patcher.md)) — после прошивки пульт работает сразу,
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

### Кеймап нашего пульта (custom 0xFE01, Linux-коды, Generic.kl)

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
| мышь (fn) | 0x00 | 100 | ALT_RIGHT + toggle NORMAL/MOUSE (шапка `fn_key/cursor_*_scancode`, значения из стокового DT) |
| KD | 0x44 | 66 | F8 (как в стоковом DT `0x00440042`; стоковый KD Player слушал F8, юзерский бинд — через маппер кнопок) |

### Ограничения (честно)

- Кнопка мыши работает (2026-10-08, проверено живьём): `fn_key_scancode
  0x00` + `cursor_*` в шапке tab2 (значения из стокового DT:
  left/right/up/down/ok = `0x51/0x50/0x16/0x1a/0x13`) + строка `0x00 100`
  в keymap (без неё `scancode 0 undefined`, тоггл не фаерится: `getkeycode`
  ищет сканкод в мапе ДО проверки fn). В MOUSE_MODE стрелки дают
  `REL_X/REL_Y` с ускорением при удержании, OK — `BTN_LEFT`; само
  нажатие fn шлёт ещё и `ALT_RIGHT` (код 100 как в стоковом DT —
  `0x00 0` парсер `remotecfg` отбрасывает, проверено). Ядро DT-`cursor_*`
  по-прежнему не читает (`memset 0xFF` в `get_custom_tables`) — режим
  живёт только через `remotecfg`-путь, DT-экстры в оверлее на него
   не влияют.
- KD (`0x44 → F8`, 2026-10-08, проверено живьём `getevent`): штатный
  маппер кнопок без гуглосервисов не работает, поэтому бинд на
  приложение — на усмотрение юзера; сам код из ядра идёт чисто.
- `repeat_enable=0` (как в стоке): удержание не повторяет.

