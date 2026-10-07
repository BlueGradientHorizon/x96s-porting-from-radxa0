# Bluetooth RTL8723BS: стек, прошивка, мультизагрузка (задел)

BT заведён и работает из коробки (2026-10-07): H5 over `ttyS1`,
стоковая RTK-либа, адрес чипа, спаривание, A2DP-звук в наушники
(проверено живьём). Этот файл — вся BT-история в одном месте
(перенесена из рабочих разделов после закрытия темы).

## Спека

- Combo-чип RTL8723BS (та же микруха что WiFi, одна антенна):
  BT-адрес идёт следующим за WLAN (`...:8D` при WLAN `...:8C`,
  оба из efuse конкретного экземпляра; в `bt_config.conf`:
  `Address = 44:ef:bf:a8:60:8D` — префикс совпал со стоковым
  `rtw_ndev_init`, см. [docs/0-hardware.md](0-hardware.md)).
- Транспорт: UART `/dev/ttyS1` (`ffd24000.serial`), протокол H5,
  старт 115200 → переключение на 1500000 после заливки прошивки.
- LOS-vendor userspace 32-битный (как стоковый Android 9) — стоковые
  32-битные BT-библиотеки грузятся без пересборки (ср. с WiFi, где
  64-битному ядру потребовался пересобранный `.ko`).

## Разведка со стока (второй заход не нужен)

Burn-пакет `X96S_P_20200903-1822.img`: парсер `x96s_patcher.amlogic` →
слот `vendor` (sparse) → `simg2img` → loop-mount на VM (методика —
в приложении [docs/4-wifi.md](4-wifi.md)). Найдено:

- `lib/libbt-vendor.so` (161488 байт, md5 `8d070231…`) — Realtek
  (`RTKBT_RELEASE_NAME: 20190311_BT_ANDROID_9.0`, H5-машина
  `h5_*_timer`, `rtk_get_bt_firmware`, `hci_get_h5_int_interface`);
  рядом generic `lib/hw/android.hardware.bluetooth@1.0-impl.so`
  (тот же HIDL-скелет что у LOS, без droidlogic-расширений).
- `etc/bluetooth/rtkbt.conf` (`BtDeviceNode=?/dev/ttyS1:H5`,
  побайтово = [bt_fw/rtkbt.conf](../bt_fw/rtkbt.conf)),
  `firmware/rtl8723bs_fw` + `rtl8723bs_config` (побайтово =
  [bt_fw/](../bt_fw), md5 `37210afd…` / `ab690442…`).
- `bin/rtkcmd`, сервис `vendor.bluetooth-1-0`
  (`etc/init/android.hardware.bluetooth@1.0-service.rc`), VINTF-запись
  `android.hardware.bluetooth@1.0 hwbinder IBluetoothHci/default`
  (в LOS-манифесте её нет — только `bluetooth_audio.xml`).
- Питание/доступ: `chown bluetooth` на `rfkill0/{state,type}`
  и `/proc/bluetooth/sleep/{btwrite,lpm}` (rtkbt-драйвера сна в
  LOS-ядре нет — либе не мешает, см. шум ниже).

## Диагноз LOS (чистый ребут, 5 крашей за ~25 с)

- `ttyS1` жив, HIDL-сервис `vendor.bluetooth-1-0` (droidlogic,
  `android.hardware.bluetooth@1.0`) стартует, `initialize()` доходит,
  `userial open /dev/ttyS1` ок, `Firmware configured in ~3.4–3.7s` —
  но GD-стек падает раньше по таймауту (~3 с):
  `system/gd/stack_manager.cc:56 StartUp: Can't start stack,
  last instance: starting HciHal` (+ `serviceDied` → `close` в HAL).
- Вендорный HAL (`android.hardware.bluetooth@1.0-impl-droidlogic.so`)
  мультичиповый: H4+H5, таблица USB (`rtl8723du/bu`, `rtl8821au/cu`…
  → `libbt-vendor_rtlMulti.so`), выбор через `ro.vendor.btmodule`
  (на LOS пуст — лог `btmodule: no_set`). В образе только Broadcom
  `libbt-vendor.so` (17 КБ, чипсеты BCM43xxx, `.hcd` из
  `/vendor/etc/bluetooth/`), RTK-либы нет. Итог: HAL гонит
  BCM-протокол в Realtek-чип, ответа нет → таймаут → краш-луп
  (фреймворк после ~6 крашей ретраить перестаёт).
- VINTF-нюанс (шум, не корень): GD ищет `@1.1::IBluetoothHci`
  и AIDL `IBluetoothHci/default`, в манифесте их нет — но 1.0-fallback
  работает (`initialize()` до HAL доходит).

## Живой тест (bind-mount, без перепрошивки, 2026-10-07)

Стоковые `libbt-vendor.so` + `rtkbt.conf` + `rtl8723bs_fw/_config`
поверх LOS-вендора, `stop/start vendor.bluetooth-1-0`,
`svc bluetooth enable`:

- `RTKBT_RELEASE_NAME: 20190311`, H5 open `/dev/ttyS1`
  (flowctrl OFF), `check_match_state` (lmp_subversion `0x8723`),
  `get_patch_entry → rtl8723bs_fw + rtl8723bs_config`,
  `Load FW OK`, baud 115200 → 1500000 (dmesg), `state: ON`,
  адрес `...:60:8D`, EIR сгенерирован, ноль крашей.
- Безвредный шум (не чинить): `udpsocket Permission denied`,
  `rtk_btcoex` и `/proc/bluetooth/sleep/lpm` отсутствуют,
  `rtk_btconfig.txt` нет.
- Пойманные ловушки (все живьём):
  - без `rtkbt.conf` либа уходит в USB-путь (`/dev/rtkbt_dev`, fail);
  - стейджинг в `/data/local/tmp` HAL не читает (avc `search denied`,
    `shell_data_file`) — только `/data/vendor` (`vendor_data_file`)
    + `chcon` под метки соседей (`same_process_hal_file` либе,
    `vendor_configs_file` конфу, `vendor_file` прошивкам);
  - bind поверх несуществующего файла невозможен — только dir-bind
    стейджинга (для `etc/bluetooth` и `firmware` целиком,
    со всем исходным содержимым);
  - `mount|grep` после `stop/start` врал — проверять `md5sum` цели
    + `/proc/PID/root/...` + `maps` (либа грузится лениво,
    по `initialize()`);
  - `RtkBtsnoopDump=true` НЕ ВКЛЮЧАТЬ: `.cfa_rtk` HAL писать не может
    (`Permission denied`, sepolicy) — и дальше либа падает внутрь
    `rtk_update_altsettings` (tombstone, краш-луп; лечится ребутом,
    бинды слетают). HCI-снуп входящего пейджинга так и не снят.

## Фикс `vendor-bt` (запечено в патчер)

Модуль [x96s_patcher/fixes/vendor_bt.py](../x96s_patcher/fixes/vendor_bt.py)
(targets `ota`, регистрация + порядок — в `fixes/__init__.py`):

- замена `lib/libbt-vendor.so` на стоковую RTK (режим и
  `security.selinux` наследуются от BCM-оригинала через replace-op);
- создание `etc/bluetooth/rtkbt.conf`, `firmware/rtl8723bs_fw`,
  `firmware/rtl8723bs_config` (0644, метки соседей через
  `selinux_xattr`; payload'ы — [bt_fw/](../bt_fw), [`rtkbt.conf` +
  fw/config] уже лежали в репо, либа доложена из стокового vendor);
- удаление 17 мёртвых BCM `.hcd` (RTK-либа их не читает; удаление идёт
  первым и funds место — прецедент `dhd.ko`, в LOS-vendor всего
  78 свободных блоков, надо ~50).
- Проверено: оба nightly патчатся, `testzip` OK, 4 файла побайтово =
  payload, `.hcd` = 0, реран = no-op. VINTF-запись и `ro.vendor.btmodule`
  сознательно НЕ тронуты (стек работает без них — доказано живьём).

## Прошивка и верификация

- TV `lineage-22.2-20260925-nightly-radxa0-signed-x96s-fix.zip`
  (md5 `da505d8b…`, sideload `Total xfer: 0.96x` — штатно; первая
  попытка висела на ~0% — рекавери ждало ручного `Apply from ADB`).
  Холодный бут: BT ON сам (`SYSTEM_BOOT`, t≈30 с), адрес `...:60:8D`,
  `Bluetooth crashed 0 times`, discovery-движок жив, WiFi цел
  (`wlan0` UP, ноль `-84`). 4 vendor-файла на девайсе = payload.
  Счёт: bind-mount бут + прошитый бут = 2/2 ON.
- TAB `...-radxa0_tab-signed-x96s-fix.zip` (md5 `3fb00ff6…`, тот же фикс)
  прошит юзером сам: спаривание с телефоном работает в обе стороны,
  стик видит Xiaomi TV за стеной с полным EIR/UUID, телефон видит
  `Radxa Zero` (`SCAN_MODE_CONNECTABLE_DISCOVERABLE`). Финал: звук
  в BT-наушниках работает — тема закрыта.

## Ограничения (честно)

- Передача файлов НЕ работает ни в какую сторону: в сборке выключены
  `bluetooth.profile.opp.enabled=false` и `pbap.server.enabled=false`
  (включены только a2dp-source/hid-host/pan). Флаги зашиты во фреймворк
  (btservices APEX), не в vendor — вне скоупа патчера.
- Входящий пейджинг с телефона до конца не разобран: две HCI-выборки
  (5300+ пакетов) не содержат ни одного Connection Request, при этом
  исходящий inquiry и видимость в порядке. Подозрение — телефонная
  сторона или accept-диалог ТВ; стек и радио доказано живые.
- TV-настройки BT ищут аксессуары (фильтр UI фреймворка) — телефон там
  может не показаться; спаривание телефона идёт со стороны телефона
  или из TAB-сборки.
- Single-chip: фикс рассчитан на RTL8723BS (других ревизий стика
  с иным BT не встречалось; BCM `.hcd` снесены — см. задел ниже).

## Задел: runtime-диспетчер BT (теория, не делать пока не надо)

Если встретится ревизия стика с другим BT-чипом — повторять WiFi-путь
([docs/4-wifi.md](4-wifi.md)): не плодить фиксы на чип, а один рантайм-выбор.
Ориентир дизайна (на 2026-10-07 проверена только одночиповая замена выше;
ниже — гипотезы с указанием что именно осталось доказать):

1. Детект — по sysfs, как стоковый `multi_wifi_load_driver`
   (`/sys/bus/mmc/devices/<host>:0001/.../device` для SDIO,
   `/sys/bus/usb/devices` для USB; VID:PID брать из стокового
   `modules.alias`). У домена BT-HAL sysfs, в отличие от
   `vendor_modprobe`, есть (HAL читает `rfkill` живьём) — детект
   возможен прямо из HAL-процесса, userspace-демон может не понадобиться.
2. Выбор — штатным механизмом droidlogic-HAL: `ro.vendor.btmodule` +
   семейство `libbt-vendor_*Multi.so` (bcm/rtl/mtk/qca/nxp/uwe/aml/639 —
   все имена уже внутри `impl-droidlogic.so`; таблица USB-чипов там же).
   Осталось доказать реверсом: какие значения `btmodule` каким `.so`
   соответствуют и что выбирается для UART (таблица покрывает только USB;
   H5-путь RTK, судя по `hci_get_h5_int_interface` в стоковой либе,
   инициируется самой vendor-либой, а не `btmodule`).
3. Доставка — все `libbt-vendor_*Multi.so` + все `rtl*_fw/_config` +
   все `.hcd` запекаются в образ (бюджет: ~200 КБ на набор; BCM-набор
   сейчас снесён — вернуть), выбор только указывает нужный.
   Альтернатива без реверса HAL: свой oneshot-сервис на `on boot`
   (домен с sysfs + правом `stop/start vendor.bluetooth-1-0`?) —
   тяжелее: HAL стартует раньше и перечитывать выбор не умеет,
   понадобится его рестарт до старта фреймворка.
4. Проверка та же что у WiFi, плюс спаривание: чистый ребут →
   `initialize()` нужной либы в логе → `Load FW OK` → адрес чипа →
   ноль крашей → scan/pair с реальным устройством.
