# Загрузчик u-boot и burn-пакеты

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
дефолты (доказано живьём и дампами env, см. журнал burn-пакетов ниже в этом файле), поэтому правка
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
[bootloader-x96s.bin](../bootloader-x96s.bin) в корне рабочей папки: `bootloader.img`
в ПОР, `bootloader.PARTITION` в ПОА (меньше слота 1261424 —
влезает; тул шьёт по таблице, stale-хвост не мешает).

## Журнал burn-пакетов (2026-10-04/05, сырая история)

Идея: один аргумент — ПОР или ПОА, детект по содержимому, каждому
типу свои фиксы; флоу burn ПОА → рекавери пультом → sideload ПОР.
По дороге было: двухаргументный merge (патчить разделы ПОР и вшивать
в ПОА) — отменён в пользу одноаргументного режима (проще, нечему
рассинхронизироваться); спор «vendor обязан ехать и в ПОА» — убит
фактами (см. [docs/3-patcher.md](3-patcher.md), «Почему vendor-фиксы не едут в ПОА»).
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
`bootloader0/1` — с нуля: сверки читать со сдвигом.

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
патч — в [patches-uboot/uboot-coldboot-window.patch](../patches-uboot/uboot-coldboot-window.patch)); `u-boot.bin` 1100160
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
