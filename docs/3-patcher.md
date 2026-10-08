# Патчер fix_x96s.py

## Файлы в рабочей папке (инвентарь)

- [fix_x96s.py](../fix_x96s.py) — тонкая точка входа (аргументы + вызов).
  Вся логика — в пакете [x96s_patcher/](../x96s_patcher) (см. ниже в этом файле):
  `errors`/`workdir` (база), `fdt` (парсер DTB), `ir_data`
  (кеймапы+таб пульта), `ext4` (механика debugfs), `vendor_img`
  (общий хелпер vendor-фиксов), `amlogic` (парсер/сборщик
   burn-пакетов), [fixes/](../x96s_patcher/fixes) (по файлу на фикс
   с саморегистрацией + targets `ota`/`aip`), `pipeline`
   (детект типа пакета + обе ветки), `cli`.
- [bootloader-x96s.bin](../bootloader-x96s.bin) — пересобранный u-boot (FIP, плата
  `g12a_radxa0_v1` + C-хук окна в `board_late_init`; payload
  для скрипта: `bootloader.img` в ПОР, `bootloader.PARTITION`
  в ПОА; ищется рядом с launch dir).
- [x96s_8723bs-4.9.337.ko](../x96s_8723bs-4.9.337.ko) — собранный драйвер WiFi (payload для скрипта,
  ищется рядом с launch dir; НЕ стрипать!). Имя в образе —
  `lib/modules/x96s_8723bs.ko` (внутреннее имя модуля `dhd`, см. [docs/4-wifi.md](4-wifi.md)).
- [x96s_wifi](../x96s_wifi) — dispatcher ранней загрузки WiFi (static, без libc;
  исходник в [dispatcher/](../dispatcher), бинарь собирается кросс-тулчейном).
- [x96s_patcher/wifi_drivers.py](../x96s_patcher/wifi_drivers.py) — таблица драйверов (VID:PID → файл
  в образе → payload) + генератор map; [docs/4-wifi.md](4-wifi.md) — разведка
  стоковой мультизагрузки (механизм + весь зоопарк драйверов).
- [apply_patches.py](../apply_patches.py) — один скрипт на все патчи исходников
  (`apply_patches.py <target>` из корня чистых исходников;
  патчи — файлами в [patches-rtl8723bs/](../patches-rtl8723bs) и [patches-uboot/](../patches-uboot)
  (сборка: [docs/4-wifi.md](4-wifi.md) и [docs/5-bootloader.md](5-bootloader.md)).
- [dotconfig](../dotconfig) — точный конфиг ядра с живого девайса (`/proc/config.gz`).
- [remote.tab2](../remote.tab2) — исправленный таб нашего пульта (эталонная копия;
  в скрипт текст встроен).
- [stock-dtb-raw.bin](../stock-dtb-raw.bin) — стоковый DTB-референс.
- [bt_fw/](../bt_fw) — payload'ы BT-фикса `vendor-bt` со стока
  (прошивки, `rtkbt.conf`, RTK `libbt-vendor.so`; детали —
  в [docs/8-bluetooth.md](8-bluetooth.md)).
- [flash/](../flash) — всё для прошивки:
  [X96S_P_20200903-1822.img](../flash/X96S_P_20200903-1822.img) (сток), [sbx_x96s_2gb_2.4Ghz_atv_9_16.img](../flash/sbx_x96s_2gb_2.4Ghz_atv_9_16.img)
  (slimBOXtv-кастом), [super_empty.img](../flash/super_empty.img), подпапки [los-22.2-radxa0/](../flash/los-22.2-radxa0)
  и [los-22.2-radxa0_tab/](../flash/los-22.2-radxa0_tab) (в каждой `aml_install_package.img` +
  оригинал `lineage-*-signed.zip`; `-x96s-fix.zip` собирается
  скриптом в [out/](../out)).
- [out/](../out) — собранные `-x96s-fix.zip` (ПОР) и
  `-radxa0[_tab]-x96s-fix.img` (ПОА) (артефакты сборки, в GitHub
  не едут — см. [.gitignore](../.gitignore)).

## fix_x96s.py

```
fix_x96s.py FIRMWARE.(zip|img)   # тип определяется по содержимому
fix_x96s.py --list               # список фиксов (с targets ota/aip)
```

Архитектура (пакет `x96s_patcher`, только stdlib + `pip install
brotli` для vendor-фикса; [fix_x96s.py](../fix_x96s.py) в корне — лишь импорт
`main` из [x96s_patcher.cli](../x96s_patcher/cli.py)):

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
- [fixes/](../x96s_patcher/fixes) — по модулю на фикс (`dtbo`, `vendor_tabs`,
  `vendor_wifi_rc`, `vendor_wifi_ko`, `vendor_wifi_dispatch`, `vendor_bt`,
  `bootloader`), контракт
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
  - `dtbo`: мерж оверлеев в `dtbo.img` (raw-прошивка через
    `package_extract_file`, контрольных сумм нет). Фрагменты `2..4` —
    ИК-приёмник (см. [docs/2-remote.md](2-remote.md)), фрагмент `5` —
    синий LED (вся история — в [docs/9-led.md](9-led.md)).
    Идемпотентность — по каждой ноде отдельно (старый IR-only образ
    допатчится только LED). Размер файла не меняется (добивка нулями).
  - `vendor-tabs`: `vendor.new.dat.br` → brotli-decode → raw ext4 →
    замена `etc/remote.tab2` на исправленный (настоящий ext4-драйвер
    через debugfs, transfer.list перегенерируется; там только
    `new`-диапазоны без хэшей) → brotli-encode (quality 6).
    Подпись zip ломается штатно (recovery: `Signature verification
    failed` → Yes, как для любых кастомных зипов).
  - `vendor-bt`: BT RTL8723BS (замена `libbt-vendor.so` на стоковую
    RTK + `rtkbt.conf`/`rtl8723bs_fw/_config` + снос 17 мёртвых BCM `.hcd`).
    Полная история — в [docs/8-bluetooth.md](8-bluetooth.md).
  Закрытый эксперимент `vendor-adb` (2026-10-08, удалён): попытка
  авто-adb+root. Стоковый механизм найден (в стоковом `default.prop`,
  секция BOOTIMAGE, вшито `persist.sys.usb.config=adb` — весь авто-adb
  стока держится на нём), но порт упёрся в три стены: `setprop` этих
  пропсов из vendor-rc запрещён sepolicy (`vendor_init` denied на
  `persist.sys.usb.config`/`service.adb.root`, avc-доказательство
  в dmesg), `setprop` из `on boot` детерминированно вешает загрузку
  на статичном лого (V1/V3), а `ro.adb.secure=1` лежит в system/EROFS
  (vendor не перебивает).   Итог: авто-adb возможен, но без авторута
  и без снятия RSA-тапа — смысла ноль, фикс удалён. Vendor-путями
  не возвращаться. Теоретически полное решение (авторут + no-auth +
  pre-launcher одной строкой) возможно только пересборкой system
  (EROFS через `mkfs.erofs` с сохранением меток + подгонка под размер
  логического раздела): `ro.adb.secure=0`, `ro.secure=0`. Отложено,
  не сегодня.
- НЕ ТРОГАЮТСЯ: остальные `*.new.dat.br`, `boot.img`, `dtb.img`
  (store с crc32!), `vbmeta`, `bootloader`, updater-script,
  transfer-листы. Исходник только читается.
- Проверено: оба nightly патчатся (dtbo + vendor), zip валидны
  (`testzip`), побайтовые сверки (префикс/суффикс образа, табы,
  оверлей == боевому), исходники нетронуты, tmp чистятся даже на
  ошибках, повторный прогон идемпотентен.

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

