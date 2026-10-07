# Ловушки и текущее состояние

## Ловушки (набитые шишки)

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

## Текущее состояние и TODO (обновлять!)

Состояние на 2026-10-06 (полная пересборка с нуля на ubuntu-vm,
старые репо удалены):

- Загрузчик переделан: окно `update 700 750` вшито C-хуком
  в `board_late_init` (мимо env вообще), header-патч `run try_auto_burn;`
  откачен, фикс `aip-env` (env-слот) УДАЛЁН из патчера вместе
  с `env_template.bin`. Живое доказательство ещё впереди: прошить
  fixed-ПОА поверх env без вызова → холодный бут с USB в ноут →
  вспышка ~750мс → загрузка дальше.
- CI ([.github/workflows/](../.github/workflows), раннер `ubuntu-26.04`): [build.yml](../.github/workflows/build.yml) —
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
  dummy `firmware_path`, НЕ стрипан (md5 текущего: `27c95153…`;
  собран 2026-10-06 из ядра `f90a0048` — точный коммит из
  build-manifest обоих nightlies — + `rockchip_wlan f38306`;
  размер тот же 3264040). Payload [bootloader-x96s.bin](../bootloader-x96s.bin) пересобран
  там же (`u-boot fd4a7d4` + оба патча, `u-boot.bin` 1101224,
  FIP 1248624, md5 `f2f40bef…`). Все 4 образа пропатчены заново
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
  md5 сошёлся). Идемпотентность содержательная (реран = no-op).
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

1. Публикация на GitHub (репо вычищено, [.gitignore](../.gitignore) есть).

## Bluetooth (закрыт 2026-10-07, вся история — в [docs/8-bluetooth.md](8-bluetooth.md))

BT RTL8723BS работает из коробки: фикс `vendor-bt` (RTK H5-либа
со стока + `bt_fw/` + снос BCM `.hcd`), TV и TAB прошиты и проверены
живём (ON с `SYSTEM_BOOT`, адрес чипа, ноль крашей, спаривание,
A2DP-звук в наушниках). Не работает передача файлов — выключена
во фреймворке (`opp=false`, вне скоупа патчера).

