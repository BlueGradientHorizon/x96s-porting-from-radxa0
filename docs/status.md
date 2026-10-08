# Текущее состояние и TODO (обновлять!)

Состояние на 2026-10-06 (полная пересборка с нуля на ubuntu-vm,
старые репо удалены):

- Загрузчик переделан: окно `update 700 750` вшито C-хуком
  в `board_late_init` (мимо env вообще), header-патч `run try_auto_burn;`
  откачен, фикс `aip-env` (env-слот) УДАЛЁН из патчера вместе
  с `env_template.bin`. Живое доказательство ещё впереди: прошить
  fixed-ПОА поверх env без вызова → холодный бут с USB в ноут →
  вспышка ~750мс → загрузка дальше.
- CI ([.github/workflows](../.github/workflows), раннер `ubuntu-26.04`): [build.yml](../.github/workflows/build.yml) —
  весь пайплайн (оригиналы по API Lineage + ядро с коммита из
  манифеста + драйвер + u-boot с [patches-uboot/](../patches-uboot) + [fix_x96s.py](../fix_x96s.py),
  джобы `resolve`/`kernel-driver`/`uboot`/`build-device`),
  [ci.yml](../.github/workflows/ci.yml) — ручной запуск, [release.yml](../.github/workflows/release.yml) — ручной релиз.
  Тулчейн — версионный `gcc-15` (безверсионный кросс в 26.04 —
  битые 80-байтные стабы, виснут навсегда), шим `compiler-gccN.h`
  строго по версии кросса, tmate-дебарг на падениях. Зелёный
   прогон есть: 7 артефактов пофайлово (2 зипа + 2 img + ko + bin + dispatcher).

- Прошито и работает: TV [lineage-22.2-20260925-nightly-radxa0-signed-x96s-fix.zip](../out/lineage-22.2-20260925-nightly-radxa0-signed-x96s-fix.zip)
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
- Burn-пакеты тоже патчатся: [out/aml_install_package-radxa0-x96s-fix.img](../out/aml_install_package-radxa0-x96s-fix.img)
  и [out/aml_install_package-radxa0_tab-x96s-fix.img](../out/aml_install_package-radxa0_tab-x96s-fix.img) (`dtbo` +
  пересобранный u-boot в слоте `bootloader.PARTITION`, 15 слотов,
  env-слота больше нет; остальное побайтово как
  в исходных LOS-ПОА; CRC пересчитан, parse валиден, слот
  bootloader побайтово равен новому payload). Флоу: burn через
  USB Burning Tool → рекавери с пультом → sideload fixed-ПОР.
- Payload [x96s_8723bs-4.9.337.ko](../x96s_8723bs-4.9.337.ko) в корне: single, `CONFIG_POWER_SAVING=n`,
  DOWN-UP + синхронный reinit без слипов, modname `dhd`,
  dummy `firmware_path`, НЕ стрипан (собран 2026-10-06 из ядра
  `f90a0048` — точный коммит из build-manifest обоих nightlies —
  + `rockchip_wlan f38306`; размер тот же 3264040).
  Payload [bootloader-x96s.bin](../bootloader-x96s.bin) пересобран
  там же (`u-boot fd4a7d4` + оба патча, `u-boot.bin` 1101224,
  FIP 1248624). Все 4 образа пропатчены заново
  из оригиналов `flash/los-22.2-radxa0(-tab)/` (2 ПОР testzip OK,
  в обоих ПОА слот bootloader побайтово равен новому payload).
- Рантайм-диспетчер WiFi (2026-10-06, РАБОТАЕТ живьём):
  [dispatcher/wifi_select.c](../dispatcher/wifi_select.c) (static, raw syscalls) + map из
  [wifi_drivers.py](../x96s_patcher/wifi_drivers.py): oneshot-сервис [x96s_wifi](../x96s_wifi)
  (`seclabel u:r:vendor_modprobe:s0`) + `wait` SDIO + `start` +
  `wait` ноды `firmware_path` + `chmod` в rc; один insmod по try-order
  map, `dhd.ko` из образа удалён. Живой drill: start/trying/up в kmsg
  на t≈7.0–7.4, probe + reinit + ndev efuse-MAC, ноль `-84`, ноль
  HAL-ошибок, коннект по DHCP сам (после `svc wifi enable`, см. ниже),
  20/20 пингов без потерь. По дороге поймано и убито (все живьём):
  запись до удаления не влезает в 10 свободных блоков (теперь удаление
  первое); ошибки debugfs в stderr при коде 0 (сканер теперь мержит
  stderr); `exec` в `on boot` init молча пропускает в ОБЕИХ формах
  (`wait` рядом работает, ни строки в логах — рабочие exec'ы все
  в on-property контекстах); голый сервис без seclabel умирает с
  `incorrect label or no domain transition from u:r:init:s0` (видно
  только через ручной `ctl.start`, в on-boot init это не логирует);
  лечение — штатный домен `vendor_modprobe` из `vendor_sepolicy.cil`
  (transition из init, entrypoint `vendor_toolbox_exec`, sys_module,
  kmsg, чтение vendor; sysfs у него НЕТ — поэтому dispatcher try-order
  без sysfs, а chmod остался в init); баг парсера map (0 означал и
  коммент, и конец — цикл вставал на ведущих `#`; проверен нативом).
  После двух мертвых прошивок тумблер wifi был ВЫКЛЮЧЕН (`wifi_on=0`,
  SelfRecovery гасит после циклов без драйвера — проверять первым!);
  нода `firmware_path` в итоге `0660 system:wifi` (LOS-триггер сам
  chown'ит — HAL пишет, наш `0666` безвредно шире); `dhd: disagrees
  about version of symbol printk` — безвредно (модуль тот же,
  сверка содержимого сошлась). Идемпотентность содержательная (реран = no-op).
- Серия самопроизвольных ребутов 10-03 оказалась питанием от USB-порта
  ноутбука, не нашим багом: с блоком питания стабильно. pstore при
  падениях был пуст (не паники ядра).
- По дороге было: кирпич-цикл от грязного шатдауна (вылечен вайпом
  `/data`, счётчики RescueParty). Мёртвые заходы (in-driver retry,
  init-сервис, exec_background, скрипты с поллингом, su-сервис,
  boot_completed-триггер) вычищены из кода и доков.
- Оверрайдов нет: `/data/remote` удален, persist-проп пуст.
  Никаких зашитых MAC/SSID/паролей: всё per-unit берётся из efuse.
- Кнопка мыши пульта (закрыта 2026-10-08):
  `fn_key/cursor_*` + `0x00 100` в tab2 (детали — в [docs/2-remote.md](2-remote.md)).
  Ход: live-тест через `/data/remote`-оверрайд (тоггл NORMAL/MOUSE,
  REL-курсор с ускорением, OK = BTN_LEFT) → запечено в патчер
  (`remote.tab2` + `FIXED_TAB2`) → оба `-x96s-fix.zip` пересобраны
  на VM (tab2 в образе сверен через debugfs) → оверрайд убран →
  TAB прошит (sideload `0.97x`) → работает из коробки.
  Вывод задним числом: пересборка ядра была
  не нужна (ранний диагноз по `memset 0xFF` в `get_custom_tables`
  был неверен — `remotecfg` парсит `fn_key/cursor_*` из tab-файла
  и везёт их ioctl'ом сам).
- KD (`0x44 → F8`, закрыта 2026-10-08): маппинг как в стоковом DT
  (`0x00440042`), живьём идёт чистый `KEY_F8` в `getevent`.
  Штатный Button Mapper требует гуглосервисов (их нет) — бинд F8
  на приложение остаётся на усмотрение юзера. Запечено в тот же
  tab2, TAB прошит, работает из коробки
  (стик просыпается по KD).
- U-boot env: дописан `console=ttyS0,115200` в `initargs` (`saveenv`,
  перешивают только вместе с bootloader). verity отключен.
- Стенд: Linux-хост для сборки (кросс-тулчейн aarch64) и запуска
  скрипта (e2fsprogs + python3-brotli). Конкретика моего стенда —
  в AGENTS.md, здесь ей не место.

Следующие шаги:

1. Публикация на GitHub (репо вычищено, [.gitignore](../.gitignore) есть).

## Bluetooth (закрыт 2026-10-07, вся история — в [docs/8-bluetooth.md](8-bluetooth.md))

BT RTL8723BS работает из коробки: фикс `vendor-bt` (RTK H5-либа
со стока + `bt_fw/` + снос BCM `.hcd`), TV и TAB прошиты и проверены
живём (ON с `SYSTEM_BOOT`, адрес чипа, ноль крашей, спаривание,
A2DP-звук в наушниках). Не работает передача файлов — выключена
во фреймворке (`opp=false`, вне скоупа патчера).
