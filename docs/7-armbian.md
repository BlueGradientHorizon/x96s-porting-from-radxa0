# Armbian на X96S (бортовой журнал, отдельно от Android-трека)

Попытка запустить Armbian под Radxa Zero на стике + завести встроенный
WiFi RTL8723BS под мейнлайном. Сюда же — всё про порядок загрузки
SD → USB → eMMC. В [README.md](../README.md) этой теме не место.

## Образ

[flash/Armbian_26.8.3_Radxa-zero_trixie_current_6.18.45_minimal.img](../flash/Armbian_26.8.3_Radxa-zero_trixie_current_6.18.45_minimal.img)
(1.7 ГБ) — это НЕ прошивка, а raw-образ SD-карты: MBR, один раздел ext4
(`armbi_root`, старт с 4 МБ), в первых 4 МБ — свой FIP-загрузчик
(`@AML`, `g12a`, radxa). Внутри: Trixie, ядро 6.18.45 `meson64`,
DTB `meson-g12a-radxa-zero.dtb`, root по UUID. USB Burning Tool его
закономерно отвергает (ждёт burn-пакет с магией `27B51956`, а тут её нет).
Писать как обычную SD: Balena Etcher / Rufus (DD) / Win32DiskImager.
Первые 4 МБ везут Amlogic-FIP (BL2) + мейнлайн U-Boot 2023.07 (строка
версии в бинарнике) с distro-boot — именно он выставляет `devtype/
devnum/prefix` и исполняет `boot.scr`. Наш u-boot 2015.01 distro-boot
не умеет — потому в разделе про порядок загрузки ниже в этом файле своя минимальная последовательность вместо
`boot.scr`.

## Конверт в 32-битный ext4

Наш u-boot 2015.01 (дерево LineageOS, см. [docs/5-bootloader.md](5-bootloader.md)) не понимает
64-битный ext4 (его драйвер считает групповые дескрипторы по 32 байта —
`sizeof(struct ext2_block_group)`), а раздел Armbian — 64bit +
metadata_csum. Прямая карта через `ext4load` не читается никак.
Лечение — пересборка ФС (layout, UUID и label те же):
`mkfs.ext4 -O ^64bit,^metadata_csum,^orphan_file -L armbi_root -U <тот же
UUID>` + `cp -a`, первые 4 МБ (FIP+MBR) копируются как есть, в конце
`e2fsck -f` дочиста. Готовый файл —
`out/Armbian_26.8.3_Radxa-zero_trixie_current_6.18.45_minimal-x96s.img`
(тот же размер, e2fsck=0). Оригинал в [flash/](../flash) не тронут.

## 64-битный ext4 в вендорный u-boot (оценка 2026-10-09, не делать пока)

Инверсия трека «тащить вендор в мейнлайн»: вместо этого научить вендорный
2015.01 читать 64-битный ext4 — тогда наш `x96s_try_ext_boot` грузит
НЕмодифицированный Armbian, а WC-окно/`update`/store остаются. Замерено:
ФС Armbian — `64bit flex_bg metadata_csum(_seed) extent filetype`
(`incompat=0x22C2`, `desc_size=64`, блок 4К, inode 256, журнал чистый);
вендорный `ext4fs_mount` гейта фич НЕ имеет вообще (маунт не реджектит,
просто врёт чтения); modern `fs/ext4` (4778 строк) против вендорного
(4633) — полный бэкпорт невыгоден. Минимальный патч (~100–200 строк,
только read-путь `ext4_common.c` + `struct ext2_block_group` в
`ext_common.h`): шаг дескрипторов из `s_desc_size` (фолбэк 32),
lo+hi номера (hi в нашем масштабе всегда 0 — диски гигабайты, 32 бит
хватает до 16ТБ; hi!=0 → вернуть ошибку → хук безопасно откатится
в Android), `ee_start_hi` в экстентах; чексуммы meta_csum старый код
не проверяет — и не надо. Тест без UART: успех = ядро 6.18 доходит
до userspace (Image/uInitrd/dtb все идут через патченный код —
битый бит роняет загрузку рано, а не грузит криво); провал = откат
в Android по тому же хуку. Цена: вечер на патч + 2–4 итерации
burn+boot (~20 мин каждая, CI-джоб uboot уже есть). Выигрыш: вендорный
набор (WC/update) + немодифицированный Armbian + конверт не нужен.

Конкретно (на VM, Linux; из PowerShell инлайн не гнать — `$` съедается,
скрипт файлом через `scp`):
```bash
SRC=/media/sf_x96s/flash/Armbian_26.8.3_Radxa-zero_trixie_current_6.18.45_minimal.img
DST=/media/sf_x96s/out/Armbian_26.8.3_Radxa-zero_trixie_current_6.18.45_minimal-x96s.img
W=~/x96s-armbi && rm -rf $W && mkdir -p $W
cp $SRC $W/src.img
dd if=$W/src.img of=$W/dst.img bs=1M count=4 status=none
truncate -s $(stat -c %s $W/src.img) $W/dst.img
S=$(sudo losetup -f --show -o 4194304 -r $W/src.img)
U=$(sudo blkid -s UUID -o value $S)
D=$(sudo losetup -f --show -o 4194304 $W/dst.img)
sudo mkfs.ext4 -O ^64bit,^metadata_csum,^orphan_file -L armbi_root -U $U $D
M1=$(mktemp -d); M2=$(mktemp -d)
sudo mount -o ro $S $M1 && sudo mount $D $M2
sudo cp -a $M1/. $M2/ && sync
sudo umount $M2 $M1
sudo e2fsck -f -n $D   # обязан быть чистым, exit 0
sudo dumpe2fs -h $D 2>/dev/null | grep -E "features"  # без 64bit
sudo losetup -d $D $S && rmdir $M1 $M2
cp $W/dst.img $DST && rm -rf $W
```

## Порядок загрузки SD → USB → eMMC

Штатный `storeboot` грузит ядро только с eMMC, а `recovery_from_sdcard`
ищет лишь `aml_autoscript`/`recovery.img` в FAT — воткнутая SD с осью
молча игнорилась. Решение — второй C-хук в `board_late_init`
([patches-uboot/uboot-x96s-extboot.patch](../patches-uboot/uboot-x96s-extboot.patch), функция `x96s_try_ext_boot`,
мимо env, как окно WorldCup): дефолты root-UUID/console/fdtfile →
`ext4load` armbianEnv + `env import` → `ext4load` Image/uInitrd/dtb →
`booti`; сначала `mmc 0:1` (SD), потом `usb start 0` + `usb 0:1`, в конце
`mmc dev 1` (иначе storeboot потеряет eMMC). Все команды (`mmc/usb/env/
test/ext4load/booti`) проверены по `u-boot.map`; `source` в этом u-boot
нет — потому своя минимальная последовательность, а не `boot.scr`.
Симлинки `/boot/Image|uInitrd` драйвер понимает (`ext4fs_symlinknest`),
версии не хардкодятся; `storeargs` bootargs перезаписывает полностью —
откат на Android чистый. Адреса: kernel `0x34000000`, initrd `0x3A000000`,
fdt `0x04080000` (Image 37МБ + uInitrd 26МБ влезают с запасом).

Сборка там же, где окно (`~/u-boot`, `make u-boot.bin`, FIP через
`generate-bins-new.sh`); оба патча валятся `apply_patches.py uboot`
по алфавиту на чистое дерево (проверено worktree-прогоном).
`u-boot.bin` вырос 1100160 → 1101224, FIP 1248112 → 1248624
(выравнивание после роста BL33; ToC 1:1, в слот 1261424 влезает).
Payload [bootloader-x96s.bin](../bootloader-x96s.bin) обновлён. Фиксер прогнан ТОЛЬКО по
[flash/los-22.2-radxa0/aml_install_package.img](../flash/los-22.2-radxa0/aml_install_package.img) →
[out/aml_install_package-radxa0-x96s-fix.img](../out/aml_install_package-radxa0-x96s-fix.img) (dtbo + новый bootloader,
остальное N/A; остальные пакеты не тронуты). Живой тест 2026-10-06:
USB-путь работает (конверт грузится; со старым 64бит-образом — полный
игнор, как и положено), без носителей — Android как раньше.

## Mainline-загрузчик на eMMC через burn-пакет (без компромиссов, 2026-10-09)

Готовый артефакт — `out/aml_install_package-armbian-x96s.img`: скелет
оригинального LOS-ПОА (v1, 15 слотов), в котором заменён ТОЛЬКО слот
`bootloader.PARTITION` на FIP из самого Armbian-образа. Остальное
побайтово = LOS-оригинал.

Почему так можно (доказано разбором, не гаданием): FIP-структура у обоих
из одного семейства (TOC-магия `AA640001`, записи e0/e1/e2 — DDR-блобы —
побайтово одинаковые, включая оффсеты/размеры; отличается только e3 —
тело BL33: Android u-boot vs мейнлайн 2023.07, строка `2023.07` внутри).
TOC в LOS-слоте на `0x10010`, в голове Armbian — на `0x10210`: дельта
ровно `0x200` = MBR-префикс. Занято FIP по `0x107000` головы, хвост до
конца слота — нули. Поэтому в слот лёг `head[0x200:0x200+1261424]`
(MBR срезан, размер слота тот же — влезает с запасом ~185КБ нулей).

`DDR.USB`/`UBOOT.USB`/`aml_sdc_burn.UBOOT` оставлены LOS-овскими
СОЗНАТЕЛЬНО: это RAM-стадия самого Burning Tool (инициализация DRAM +
вендорная команда `update`, которой у мейнлайна нет). Отвязка только
у `bootloader.PARTITION` (`is_backup=0`, свой `data`); остальные
бэкап-связи не тронуты. VERIFY в LOS v1 нет вообще — проверять нечего.

Сборка/проверка (на VM, чистый stdlib через `x96s_patcher.amlogic`):
заменить `data` у `("bootloader","PARTITION")`, `build`, затем репарс:
CRC ок, 15 слотов, все кроме bootloader побайтово = оригинал
(одноразовый скрипт, в репо не ехал — шаги эти).

Флоу: burn этим пакетом через USB Burning Tool → на eMMC мейнлайн
u-boot → distro-boot: eMMC без MBR пропускается, грузится SD/USB
Armbian (НЕМОДИФИЦИРОВАННЫЙ, конверт ext4 больше не нужен — читает
родной u-boot образа) → установка на eMMC полным dd образа
(перекроет загрузчик теми же байтами + допишет MBR и rootfs;
блочное устройство eMMC уточнить через `lsblk`).

Сборка воспроизводимо (2026-10-09): скрипт
[make_mainline_uboot_aip.py](../make_mainline_uboot_aip.py) в корне
(только stdlib + `x96s_patcher`, запускать на VM):
`python3 make_mainline_uboot_aip.py <los_aip.img> <armbian.img>` →
`out/aml_install_package-uboot-mainline-<device>.img` (девайс из
fingerprint dtbo: `radxa0`/`radxa0_tab`, как у патчера). Меняет ТОЛЬКО
слот bootloader (FIP `head[0x200:0x200+len]`), проверяет DDR-записи
TOC e0–e2 на равенство LOS (чужой DRAM-инит = отказ) и v1 без VERIFY.
Проверено: TV-выход побайтово равен боевому
`aml_install_package-armbian-x96s.img`, TAB собирается со своим суффиксом.
CI: [.github/workflows/armbian-aip.yml](../.github/workflows/armbian-aip.yml)
(ручной запуск из Actions: качает Armbian `Trixie_current_minimal` + оба
LOS-ПОА с проверкой sha256, патчит оба скриптом, выхлопы — в артефактах).

Источники mainline-FIP под radxa-zero (разведка 2026-10-09, чтобы не
таскать 341МБ ради 1.2МБ):

- `dl.radxa.com/zero/images/loader/u-boot.bin.sd.bin` (1.4МБ, mainline
  2022.04): TOC на `0x10210` (та же раскладка, FIP с `0x200`), DDR e0–e2
  = LOS 3/3. НО: файл 1444720 Б > слота 1261424 (хвост ненулевой —
  резать нельзя). Влез бы в 4МБ-раздел целиком (`file[0x200:]`), но это
  даунгрейд 2023.07→2022.04 + живой тест. Отложено.
- Deb `linux-u-boot-radxa-zero-current` (стоит в самом образе): везёт
  ТОЛЬКО BL33 (`/usr/lib/linux-u-boot-current-radxa-zero/u-boot.bin`,
  FIP собирается при установке через `platform_install.sh` + блобы) —
  готового FIP нет, тупик.
- Апстрим v2023.07: `radxa-zero_defconfig` есть — самосбор возможен
  (тулчейн + BL2/BL31 + пакер, дни).
- Range на `dl.armbian.com` работает (206), но отдаётся `.xz` —
  декод префикса хрупкий, для CI не годится.
Итог: в CI остаётся полный образ (на раннере это ~минута, sha256,
проверенный 2023.07 побайтово равен локальному).

Риски (приняты): WorldCup-окна больше нет и `update`-команды в мейнлайне
нет — повторный вход в burn только через тестпоинт eMMC (maskrom).
WC-окно в мейнлайн НЕ портируется: `update`/optimus — вендорный стек
(`v2_burning` + store), в мейнлайне его нет; да и ловить тулом было бы
нечего — с мейнлайном тул не разговаривает. Реанимация без тестпоинта:
SD-rescue (грузишься с SD → чинишь eMMC, доказано живьём) + консоль
u-boot по USB-клаве. Бинарь FIP шифрован (`aml_encrypt`), состав команд
оттуда не виден.
Откат — burn любого Android-ПОА. Живой тест burn → SD-загрузка: ПРОШЁЛ
(2026-10-09, Armbian с флешки грузится с eMMC-загрузчика).

## Armbian целиком внутри burn-пакета (eMMC-установка одним burn, 2026-10-09)

Артефакт — `out/aml_install_package-armbian-emmc-x96s-v2.img` (1.75 ГБ):
скелет оригинального LOS-ПОА (v1, 15 слотов), где заменены два слота,
остальное побайтово = LOS-оригинал (проверено репарсом: размеры/флаги
остальных + CRC шапки сошлись):

- `bootloader.PARTITION` (1261424): чистый FIP Armbian
  `head[0x200:0x200+1261424]` (TOC на `0x10010`, строка `2023.07`) —
  побайтово как проверенный рабочий bootloader-only пакет;
- `super.PARTITION`: rootfs Armbian как есть (`файл[4МиБ:]`, 1707081728 Б,
  ext4-магия и UUID `7c427b10-...` на месте — ядро находит корень по UUID
  из `armbianEnv.txt`, который не тронут). 1.7 ГБ < 2.08 ГБ раздела.

ВАЖНО (ошибка v1, кирпич-но-бутящийся в WC): в слот bootloader НЕЛЬЗЯ
класть MBR. Доказано A/B: bootloader-only (FIP с байта 0) грузится,
v1 отличался ТОЛЬКО первыми 512 Б (MBR) — и стик упал в WC. Вывод:
тул кладёт файл слота начиная с сектора 1 eMMC (сектор 0 зарезервирован
и тулом не пишется), BootROM ждёт BL2-заголовок в секторе 1. MBR
сдвинул BL2 — BootROM ничего не нашёл. Поэтому MBR сектора 0 пишется
только живьём (ниже), слот везёт чистый FIP.

Откуда super@1174МиБ (LBA 2404352, доказано исходниками, не гаданием):
`LineageOS/android_hardware_amlogic_u-boot`,
`drivers/mmc/aml_emmc_partition.c` (`_calculate_offset`, `compose_ept`)
+ `common/partitions.c`, `include/emmc_partitions.h`:
bootloader 4М @0 → gap 32М → reserved 64М @36М → дальше шаг 8М
(`PARTITION_RESERVED`): cache 800М @108М (DTB-`cache` замещает встроенный
по имени — `is_prio_partition`), env 8М @916М, затем подряд разделы DTB
(logo/recovery/misc/dtbo/cri_data/frp/rsv/metadata/vbmeta/param/boot/
tee) → super `0x7c400000` @1174МиБ → data до конца. `DDR.USB`/`UBOOT.USB`
оставлены LOS-овскими (RAM-стадия Burning Tool, как раньше).

Флоу:
1. Burn v2-пакетом через USB Burning Tool (старый v1-файл перед этим
   удалить — тул может держать на нём лок; если снова WC — дело уже
   не в bootloader, а в записи super: тогда rootfs зальём живьём
   по dd, пакет всё равно вернул загрузчик).
   Живое наблюдение 2026-10-09: v2-ButROM стартует, eMMC видна как
   `mmc 2` (`switch to partitions #0, OK`), `No partition table` —
   штатно до записи MBR; `-110 voltage select` — шум пустого SD-слота;
   без носителей дальше PXE-цикл. Нумерация u-boot (mmc2) НЕ равна
   ядерной — eMMC в Linux уточнять через `lsblk` (Samsung ~14.6G).
   Живьём подтверждено: eMMC=`mmcblk1`, ext4-магия `53 ef` ровно на
   1174МиБ, UUID корня `7c427b10-...` там же — формула super
   из u-boot-исходников сошлась побайтово. MBR записан в сектор 0,
   `mmcblk1p1` появился, но ядро увидело чужую запись (LBA 3335360
   вместо 2404352, тип 0x0) — сверяем `/tmp/mbr0.bin` с сектором 0
   (подозрение на патч через `printf`). upd: хвост `tail -n 4` запись
   не показал (entry на 0x1BE, а видно с 0x1D0) — смотрим `hexdump -s 446`.
   Причина найдена (ошибка рецепта, не шелла): патч из 8 байт с seek=450
   затирал ТИП (0x83→0x00) и клал размер в поле LBA, а значение размера
   ещё и само было неверным (`C0 E4` вместо `00 E0`: 3334144=0x32E000).
   Правильно — 12 байт с seek=450: тип+CHS+LBA+SIZE
   (`83 FF FF FF | 00 B0 24 00 | 00 E0 32 00`). Заодно выяснилось: SD
   при первой загрузке расширила раздел на всю карту (потому в её MBR
   размер 15425536, а не 3334144 — поле SIZE тоже переписываем нашим).
   Живьём подтверждено: hexdump записи и `blkid` (UUID+TYPE ext4) сошлись.
   Бут Armbian 6.18.45 с eMMC без SD — РАБОТАЕТ (2026-10-09). Drill:
   корень `mmcblk1p1`, Armbian при первом буте сам расширил ФС на всю
   eMMC (14G, свободно 12G), корень по UUID, rw. Шумы dmesg — те же что
   с SD (регрессий нет): `mmc2: error -84` (встроенный 8723BS запаркован),
   `Request_irq(10) EINVAL` (CD SD-слота), `panfrost: no regulator (mali)`
   (консоль через simplefb идёт), `Bluetooth hci0 BCM -110` (BT-чип чужой),
   `mdio-multiplexer deferred` (ethernet'а физически нет).
2. Загрузка с SD (проверенный путь) → живьём на Armbian:
   ```
   sudo blkid -s UUID -o value /dev/mmcblk0p1   # эталон 7c427b10-...
   # магия super на 1174МиБ eMMC (eMMC уточнить через lsblk!):
   sudo dd if=/dev/mmcblk1 bs=1 skip=$((1174*1024*1024+1080)) count=2 2>/dev/null | hexdump -C
   # ждём 53 ef; нет — ищем метку по всей eMMC (минуты):
   sudo grep -a -b -o -m1 'armbi_root' /dev/mmcblk1
   # MBR с SD + правка entry0 (12 байт с seek=450: тип+CHS+LBA+SIZE):
   sudo dd if=/dev/mmcblk0 of=/tmp/mbr0.bin bs=512 count=1
   printf '\x83\xff\xff\xff\x00\xb0\x24\x00\x00\xe0\x32\x00' | sudo dd of=/tmp/mbr0.bin bs=1 seek=450 conv=notrunc status=none
   hexdump -C -s 446 -n 16 /tmp/mbr0.bin   # ждём ...83 ff ff ff 00 b0 24 00 00 e0 32 00
   sudo dd if=/tmp/mbr0.bin of=/dev/mmcblk1 bs=512 count=1   # только сектор 0, FIP с 512 цел!
   sudo blockdev --rereadpt /dev/mmcblk1 && sudo blkid /dev/mmcblk1p1
   # ждём UUID 7c427b10-... — формула подтверждена
   ```
3. Выключить, вынуть SD, включить, ждать 80+ с → Armbian с eMMC.
   С воткнутой SD — по-прежнему грузится SD.
Откат — burn любого Android-ПОА.

## Почему MBR нельзя вшить в пакет (доказано исходниками, вопрос закрыт)

`common/cmd_aml_mmc.c`: `amlmmc_write_bootloader` пишет файл слота
начиная с `GXL_START_BLK=1` (GXL и новее, наш G12A тоже) — сектор 0
eMMC burn-потоком не пишется вообще (туда же дублируются boot0/boot1).
`find_mmc_partition_by_name` ищет только inherent+DTB (`bootloader,
reserved, cache, env, logo…data`) — виртуального `AML_MBR` там нет,
`find_virtual_partition_by_name` знает только `dtb`. PARTITION-айтемы
диспетчеризуются по имени (`store_write_ops(partName,…)`), сектор 0
не адресован ни одним именем. `MMC_UBOOT_CLEAR_MBR` в дереве закомменчен.
Итог: установка = burn v2 + один dd 512 Б в сектор 0 (выше); в один
burn не укладывается по конструкции тула, не по нашей лени. MBR живет
в секторе 0 вечно (обновления Armbian через apt раздел не двигают),
повторять dd нужно только при смене образа целиком.

## Почему WC-окна в мейнлайне нет (замер 2026-10-09, вопрос закрыт)

Сравнение деревьев (`~/u-boot-src` вендор 2015.01 vs `~/u-boot-mainline`
v2023.07, оба на VM):

- Вендорный burn-стек: протокол+гаджет `v2_burning/` + `aml_tiny_usbtool/`
  = **26643 строки** (~25 файлов: optimus-ядро, v2 usb/sdc, sysrecovery,
  собственный DWC PCD-драйвер с дефайнами регистров); store-стек =
  **8792 строки** (`store_interface.c`, `cmd_aml_mmc.c` 4174,
  `partitions.c`, `cmd_burnup.c`, `aml_emmc_partition.c`, `env_mmc.c`).
  Команда `update` — в `v2_usb_tool/optimus_core.c`. Внешние зависимости:
  secure-boot SMC (`aml_sec_boot_check`), securitykey/efuse, board-glue
  (`cpu_id` и др.).
- Мейнлайн 2023.07: нет `update`/optimus/store/amlmmc/burnup вообще.
  Есть ums/fastboot/dfu/thor/rockusb/sdp + DOS/GPT. DWC-драйвер вендора
  писан под gadget API 2015 года — в мейнлайн не встанет без переписи.
  Плюс отладка почти вслепую (UART убит). Итог: порт WC = недели.
- Реалистичная замена окну — `ums` с абсолютным таймаутом: `ums` в
  мейнлайне есть, но авто-выход (60 с, `UMS_CABLE_READY_TIMEOUT`) работает
  только пока кабель НЕ подключён; с подключённым висит до клавиши
  (`tstc`, `CONFIG_CMD_UMS_ABORT_KEYED`) — при питании от USB ноута это
  вечный вис. Нужен патч ~30 строк (абсолютный таймаут) + сборка u-boot
  + FIP + тесты = дни, не недели. Но это mass-storage для dd, а не
  WorldCup: Burning Tool его не поймёт. Статус-кво (SD-rescue) закрывает
  ту же потребность бесплатно.

Замечание по сборке: пакет собирается только на VM (1.75 ГБ через
vboxsf + сравнение гигабайтов в RAM на 7-ГБ машине упирается в своп —
полный байт-компаре не делать, проверять репарсом заголовков + CRC
потоково; скрипты одноразовые, в репо не едут).

## USB-носители: привередливость — это дохлое железо

OEM-флешка 16 ГБ (Alcor): контент побайтово верный, в u-boot не грузится
НЕ из-за кода — контроллер виснет на чтении (пойман `cmd_age=31s`,
I/O error, usb reset под живым Linux; повтор того же места — ок).
Вывод: ретраи в загрузчике дохлое железо не спасут. Кардридер с SD
грузится штатно. Задел на будущее: `sleep` в нашем u-boot есть
(`do_sleep` в map) — если понадобятся задержки для МЕДЛЕННЫХ,
но исправных носителей.

## Встроенный WiFi RTL8723BS (запаркован 2026-10-06, не брошен)

Чип тот же (`024c:b723`, только 2.4 ГГц). Драйвер в образе есть:
staging `r8723bs.ko` v4.3.5.5 с alias ровно под наш VID:PID, прошивок
не просит. Но карта не перечисляется: `mmc2: error -84` / `Failed to
initialize a non-removable card`, `/sys/bus/sdio/devices` пусто.

Что выяснено сравнением DTB Radxa Zero со стоковым DTB (из
[stock-dtb-raw.bin](../stock-dtb-raw.bin) вытащены 3 DTB через `AML_`-заголовок, наш — 2G):
wifi висит на `ffe05000` (как в стоке — `sd2`), а в Radxa-DTB на нём
висел чужой `emmc-pwrseq` и `cd-gpios`, без `non-removable/sdio-irq/
keep-power`; `sdio-pwrseq` (п.71) был прибит к SD-слоту. Стоковый
`power_on_pin` — periphs-пин 72 (тот же, что `power_on_pin=482`
в dmesg стока: база 410 + 72).

Перебрано по одной переменной, всё мимо: pwrseq-пин 71/72/73 и 71+72,
флаг ACTIVE_LOW/HIGH, задержка 0/10/1000 мс (10 мс — как у родственного
Realtek-бокса fbx8am), vqmmc 3V3/1V8, bus-width 4/1, перенос pwrseq
на wifi, hog'и X_4 LOW / 71 HIGH / 72 HIGH. Проверено чтением живого
дерева, что всё применяется: pinmux-карта чистая (сигналы на своих
пинах, `sdcard_c` как в стоке), регуляторы 3V3/1V8 включены, IRQ хоста
тикают, pwrseq-пин реально HIGH, pinctrl-мапы в порядке (parked без
карты — норма: clk-gate). Ребинд-трасс через dyndbg (корень на USB):
CMD52/CMD8/CMD5/CMD55/CMD1 — все `-110`, карта нема. Чип на ощупь
холодный во всех конфигурациях.

Остаток: либо пин/рейл питания не тот (`power_on_pin=72` не греет;
`GPIOV_0` из стокового `sdio_x_clr` ни во что не маппится — в мейнлайне
V-банка нет вовсе), либо дохлая SDIO-физика/обвязка. Нужен скоп или
вендорные исходники. Зацепка: BT того же combo-чипа (pin82 уже HIGH,
UART/H5, [bt_fw/](../bt_fw)) — его доводка может вскрыть общий тракт питания
и заодно решить wifi.

### Трёхстороннее сравнение DTB (2026-10-10, только анализ, девайс не тронут)

Живое состояние подтверждено по ssh: корень на eMMC, сеть через
донгл (`rtl8xxxu`), `r8723bs.ko` на месте, `/sys/bus/sdio/devices`
пусто, `mmc2` (`ffe03000`) — `error -84`. Живое дерево = немодифицированный
Radxa-DTB (`wifi@1` с `brcm,bcm4329-fmac` на `ffe03000`, pwrseq пин 71).
Мелочь: ядро `6.18.44`, а каталог dtb — `6.18.45` (перекос после
apt-апгрейда, безвреден — `fdtfile` резолвится через `/boot/dtb`-симлинк).
Файлы `radxa-zero.dtb` + `fbx8am-realtek.dtb` + `x96-max.dtb` сняты
с живого `/boot` копией (не менялись), сток разобран парсером
`x96s_patcher.fdt` (все 3 DTB в [stock-dtb-raw.bin](../stock-dtb-raw.bin)
в этой части одинаковы).

Сток: wifi = `sd2@ffe05000` (okay), `sdio@ffe03000` — disabled. У `sd2`
нет ни `vmmc/vqmmc`, ни `mmc-pwrseq` (рейлы всегда включены, питание —
драйвер `aml_wifi`: `power_on_pin=[gpio,72,0]` = GPIOX_7 HIGH,
`interrupt_pin` = 73). Шина 4 бита, 100 МГц.

Мейнлайн (все три бокса одинаково): wifi SDIO = `ffe03000` + `sdio-pwrseq`
пин 71 (GPIOX_6) + `wifi32k` 32 кГц. Стоковый путь `ffe05000` + пин 72
в мейнлайне не повторяет никто — гнаться за ним вслепую не надо,
эталон теперь `fbx8am-realtek` (Freebox Player Pop, рабочий Realtek SDIO).
Его отличия от radxa-zero ровно на пути `ffe03000`:

- `post-power-on-delay-ms=10` в `sdio-pwrseq` (у radxa этого свойства нет);
- `vqmmc` = отдельный always-on `VDDIO_AO1V8` (у radxa — `VDDAO_1V8`;
  такого регулятора в radxa-дереве вообще нет);
- нет `wifi@1`-чайлда (у radxa и x96-max — `brcm,bcm4329-fmac`);
- бонусом gpio-коммутируемый `VDDAO_3V3_T` (пин 24); SD-слот у него
  на 50 МГц против 100 (к wifi не относится).

Непокрытые дельты (по одной уже пробовались задержка 10 мс и vqmmc
1V8/3V3 — но не этот рейл и не в связке, так что пробами не закрыты):

1. `vqmmc` → `VDDIO_AO1V8` (новая нода always-on 1V8 + переключить
   `vqmmc` у `ffe03000`);
2. снести `wifi@1` brcm-ноду;
3. delay 10 мс в связке с пп. 1–2;
4. трек `ffe05000` по-стоковому (`sd2` + pwrseq 72, убрать `cd-gpios`,
   `non-removable`) — старым «переносом pwrseq» покрыт лишь частично;
5. BT H5-трек как вскрытие общего питания — без изменений
   (статус живьём: hci-устройств нет, в минималке нет `hciconfig/rfkill`,
   `ttyS1` жив, H4/H5-драйверы загружены, attach не делался).

### Живые пробы по дельтам fbx8am (2026-10-10, обе мимо)

Шаг 1: `post-power-on-delay-ms=10` (`fdtput`) + снос `wifi@1` brcm-ноды
и алиаса `brcmf` (decompile/sed/recompile, `dtc` чист). Проверено живым
деревом (чайлд пропал, задержка `0x0A` на месте) — `mmc2: error -84`
остался, SDIO пусто.

Шаг 2: + новый always-on `VDDIO_AO1V8` 1V8 и `vqmmc` `ffe03000` на него
(ссылка через `&vddio_ao1v8`, phandle выдан автоматом, `dtc` чист).
Проверено живым деревом (регулятор на месте) — `-84` остался
(ошибка стала раньше по времени, t≈0.35, сути не меняет).

Итог: дельта fbx8am исчерпана полностью (задержка + рейл + без brcm —
всё разом применено). Откат — `/root/radxa-zero.dtb.bak-20261010`
на девайсе (+ копия оригинала у меня).

### Шаг 4 и добивка 71+72 (2026-10-10, всё мимо)

Шаг 4 (wifi на `ffe05000` как в стоке): `cd-gpios` долой,
`non-removable` + `keep-power-in-suspend`, свой `wifi-pwrseq`
пин 72 + delay 10 (корень на eMMC — SD-слот на время теста не жалко).
Итог: `mmc0: Failed to initialize a non-removable card` (даже без
`-84`), SDIO пусто. Попутно поймано: два pwrseq на одном пине =
второй падает с `-EBUSY` (`reset GPIOs not ready`), хост без pwrseq
из dmesg вообще пропадает — разведено удалением чужой ноды
(`fdtput -d` чистит только пропсы, ноды — только decompile/sed/
recompile; висячих `&label`-ссылок `dtc` не прощает — ловится
компиляцией).

Добивка: `sdio-pwrseq` (`ffe03000`) переведён на пин 72 с бута
(`fdtput -t u ... reset-gpios 43 72 1`, проверено `fdtget`),
затем 71+72 вместе (`43 71 1 43 72 1`). Итог: тот же `-84`,
SDIO пусто. Живой замер `debug/gpio`: после упавшей инициализации
pwrseq гасит пин (`out lo` — штатный power_off, не причина).
Честный power-cycle вручную (72 LOW→HIGH + unbind/bind хоста
с реинициализацией при поднятом питании) — тоже `-84`.

Баланс по `ffe03000` (всё проверено живым деревом): пины
71/72/71+72, delay 0/10, vqmmc-шим 1V8/3V3, с/без brcm-чайлда —
тишина везде. По `ffe05000`: pwrseq-72 и без pwrseq — тишина.
Не исключено методом исключения: чип НЕ на падах контроллера B
(SD-слот на тех же падах работает) — остаётся контроллер A
с правильным питанием, но молчащий (нет подтяжек? нет 32k?
мёртвый чип?). Развязка найдена живьём ниже (прорыв 2026-10-10):
дело было в скорости шины + IPS драйвера, чип жив.

### Прорыв: карта перечислилась, трафик идёт (2026-10-10, вечер)

Рабочая точка (всё проверено живым деревом): `ffe03000`, bus-width 4,
`max-frequency` 25 МГц, `sdio-pwrseq` пин 71 + delay 1000 мс, пин 72
задран хогом (`output-high`, постоянно, без teardown). `r8723bs`
биндится сам, `wlan0` с efuse-MAC экземпляра, скан видит точки,
assoc + DHCP + пинг шлюза 20/20 + внешка 10/10 без потерь, FAIL=0.
`50 МГц` вешает загрузку (шторм ошибок топит USB — донгл не успевает,
`dependency failed`; лечится с консоли возвратом частоты).
`1 МГц` перечисляет, но data path кривой (см. ниже).

Дельта-разбор по дороге (каждая — живьём, по одному ребуту):
пломбир шины — не ширина (4 бита на 1 МГц работают), а скорость:
`71` в миксе ⟺ `-84` (на шине кто-то отвечает мусором), без `71` —
глухая тишина; `72` один + 1000 мс — тишина; `71` один + 1000 мс —
`-84`; `71+72` + 1000 — `-84`; хог-72 + `71` + 1000 + 1 МГц/1бит —
ПЕРВОЕ перечисление (`mmc2: new high speed SDIO card`).

IPS-шторм (главная ловушка вечера): дефолтный `rtw_ips_mode=1`
+ поднятый линк = тысячи `sd_recv_rxfifo: alloc recvbuf FAIL!` в минуту
(памяти свободно 1.5 ГБ — не OOM, а мусорная длина RX),
`systemd-journald` 100% ядра, кольцо dmesg ротируется за минуты.
Лечение: `rtw_ips_mode=0` (`rtw_power_mgnt=0` уже лежал
в `/etc/modprobe.d/r8723bs.conf`; тамошний же `rtw_enusbss` драйверу
неизвестен — безвредное предупреждение). С `ips=0` счётчик FAIL
замертво даже под assoc+DHCP.

Клин под sustained-активностью (ОТКРЫТО, не tonight): `up`/скан-луп/
пинг-серии через `wlan0` вешают коробку намертво (виснет даже локальный
login, sshd молчит при живом TCP; лечится только передёргиванием).
Уточнено 2026-10-10 вечером: клин бьёт по ВСЕЙ сети коробки, включая
USB-донгл (интерфейс flap'ает сам, IP на месте, пинги с LAN не доходят;
оба драйвера — `rtl8xxxu` и `r8723bs` — висят на общем `mac80211`,
он под подозрением). Триггер — sustained `wlan0`-UP в любом виде
(даже idle без wpa); короткие окна (один скан, assoc+DHCP+3 пинга
с немедленным teardown) переживаются. Мгновенное лечение доказано
живьём: `modprobe -r r8723bs` → `wlan0` исчезает → LAN/ssh
возвращаются сразу, без ребута. Подозревается дедлок staging-драйвера
2014 года под 6.18 PREEMPT в data path (нагрузка и память в норме,
FAIL=0 в момент клина). Стратегический выход (проект, не ночь):
портировать `rockchip_wlan rtl8723bs v5.2.17.1` (тот же код, что
запечён в LOS-payload и доказан на Android) под 6.18 вместо чинки
стейджинга; у `rtw88` поддержки BS-SDIO нет (только D/DU).
Стабильное состояние на ночь: `blacklist r8723bs` + снесённый
автоконнект (`30-wlan0.yaml` удалён, станза цела
в `/root/armbian.yaml.bak`); ручной `modprobe` чёрный список
не блокирует — точечные тесты возможны.

Хог-квирк (пойман export-пробой): `gpio-hog` внутри контроллера
парсится БЕЗ phandle — `gpios = <пин флаги>` (с phandle уехал
на пин `0x2b`=43 вместо 72!). `reset-gpios` и прочие conid-пропсы
с phandle парсятся нормально (сверено метками в debugfs).

Живой DTB на девайсе сейчас: hog72 + pwrseq71 + delay1000 + bus4 +
max25M (+ `ffe05000` non-removable без pwrseq/cd — остаток шага 4,
безвреден). НЕ проверены и не трогать пока: delay1000→10,
снятие hog72, BT H5 заново (там своя история с несозданием hdev).

### Драйвер v5.2.17.1 под 6.18 (собран, probe+assoc OK, трафик недоказан)

Мейнлайн-стейджинг 2014 года — тупик для стабильности, поэтому собран
настоящий v5: `openlumi/rtl8723bs`, ветка `openwrt-build` @ `832c0dc`
(там же есть ветка `v5.2.17.1` = `f38306` — тот же коммит, из которого
собран наш LOS-драйвер). HEAD умеет 6.17, до 6.18 доведён тремя
патчами (файлы — в [patches-rtl8723bs-6.18/](../patches-rtl8723bs-6.18),
проверены `patch --dry-run` в обе стороны на чистом дереве;
`include/linux/wireless.h` — снос Realtek-заглушки с `#if 0` +
`<sys/socket.h>`, делается руками):
`01` — cfg80211 6.18 (change_beacon берёт `ap_update`,
set_monitor_channel с `net_device`), `02` — таймеры
(`linux/timer.h`, `timer_delete_sync`, локальный `from_timer`),
`03` — `_cancel_timer_ex`. Все гвардами, ниже 6.18 безвредны.

Сборка — кросс на VM (нативный на стике не вариант: Debian отдаёт
десятки КБ/с), ядро Armbian трогать не надо:
ванилла `linux-6.18.44.tar.xz` (браузером, рядом с репо) + `.config`
и `Module.symvers` из headers-`.deb` + `make modules_prepare
ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- LOCALVERSION=
-current-meson64` (суффикс обязателен — иначе разъедется vermagic).
Сам модуль: `make -C <ванилла> M=<дерево> ARCH=arm64
CROSS_COMPILE=aarch64-linux-gnu- LOCALVERSION=-current-meson64
TopDIR=<дерево> "ccflags-y=<ниже>" modules` (`TopDIR` обязателен:
в дереве он от пустого `$(src)`; Ubuntu-кросс не знает
`-mrecord-mcount` — строка 959 топ-`Makefile` дерева комментируется
в копии). Флаги (точное содержимое — сверено `make -p` + добавки):
`-idirafter <дерево>/{include,platform,hal/btc,hal/phydm}`
`-DCONFIG_RTL8723B -DCONFIG_MP_INCLUDED -DCONFIG_BT_COEXIST
-DCONFIG_EFUSE_CONFIG_FILE -DCONFIG_LOAD_PHY_PARA_FROM_FILE
-DREALTEK_CONFIG_PATH=\"/lib/firmware/\"
-DEFUSE_MAP_PATH=\"/system/etc/wifi/wifi_efuse_8723bs.map\"
-DWIFIMAC_PATH=\"/data/wifimac.txt\"
-DCONFIG_TXPWR_BY_RATE_EN=0 -DCONFIG_TXPWR_LIMIT_EN=0
-DCONFIG_RTW_ADAPTIVITY_EN=0 -DCONFIG_RTW_ADAPTIVITY_MODE=0
-DCONFIG_RTW_SDIO_PM_KEEP_POWER -DCONFIG_RTW_NAPI -DCONFIG_RTW_GRO
-DCONFIG_RTW_WIFI_HAL -DCONFIG_RTW_CFGVEDNOR_LLSTATS -DCONFIG_RTW_DEBUG
-DRTW_LOG_LEVEL=2 -DDM_ODM_SUPPORT_TYPE=0x04 -DCONFIG_IOCTL_CFG80211
-DRTW_USE_CFG80211_STA_EVENT` + `-Wno-error=implicit-function-declaration
-Wno-error=implicit-int -Wno-error -Wno-error=int-conversion
-D__LITTLE_ENDIAN -DCONFIG_LITTLE_ENDIAN -Wno-date-time`
(кавычки в PATH-дефайнах — экранированные, шелл их съедает).

Выход: `8723bs.ko` 81 МБ (отладка; для перекачки `--strip-debug`
до 3 МБ — на 6.18 безопасно, проверено insmod; наш запрет strip'а
был про 4.9). `vermagic` 1:1 со стоковым, alias на `024c:b723` есть.
Живьём: `insmod` по пути (стейджинг в blacklist не мешает),
probe + efuse-MAC + скан + assoc — всё чисто. Трафик упирается
в тот же общекоробочный клин, что у стейджинга (тест недожат —
эксперимент свёрнут). Грабли сборки, чтобы не повторять:
kbuild в M-режиме роняет `EXTRA_CFLAGS` дерева (флаги везти
`ccflags-y`); после правок заголовков — только `git clean -fdx`
+ полная пересборка (инкремент врёт из-за битых dep-файлов эры
без `fixdep`); headers-`.deb` Armbian для внешних модулей
сломан в принципе (протухшие `.config`/`autoconf.h`, нет
`asm/sync_core.h`, `arch/arm64/tools`, `linux/mei.h`, хостовых
утилит — чинить дольше, чем взять ваниллу).
Следующий кандидат — шаг 5 (BT H5): прошивок ставить не надо,
`rtl8723bs_fw/_config.bin` уже лежат в `/lib/firmware/rtl_bt/`,
не хватает только userspace-аттача (`hciattach/btattach` в минималке
нет — тянется через `apt install bluez`).

### BT H5 живьём (2026-10-10, чип молчит и там)

`apt install bluez` (донгл тянет нормально). По дороге выяснено:
BT UART — это `ffd24000.serial` (`serial0`, НЕ `/dev/ttyS1` — то было
Android-имя; в Armbian там только `ttyAML0` с другого контроллера),
а в Radxa-DTB на нём сидит serdev-нода `bluetooth` с
`brcm,bcm43438-bt` — она и давала старый `hci0` + `BCM ... -110`
(чужой драйвер, как `wifi@1` у wifi). `btattach -P h5` не взлетел
(`Invalid protocol`), зато в `modules.alias` есть точный compatible
`realtek,rtl8723bs-bt → hci_uart` — пошли штатным serdev-путём:
подмена compatible в ноде (decompile/sed/recompile, `shutdown-gpios`
пин 82 и `lpo`-клок не тронуты) → ребут → `serial0-0` привязался
к `hci_uart_h5`, но `/sys/class/bluetooth` пуст, а с `dyndbg`
видно вечный H5-sync в TX (`type 15`) без единого RX-байта.
Тот же почерк, что SDIO: всё шлёт, ничего не отвечает.

Решающий живой тест тут же (без ребута, H5-sync как детектор):
пин 72 (стоковый `power_on_pin` combo-чипа) поднят вручную через
`/sys/class/gpio` (periphs-база 512 → `gpio584`, был свободен) —
6 секунд HIGH: ни SDIO-перечисления, ни H5-RX. Пин возвращён
(LOW + unexport). На тот момент были подняты ВСЕ известные рейлы:
pwrseq-71 отпущен, 72 HIGH, 82 HIGH, 32к-клок заведён, регуляторы on.

Вывод: combo-чип молчит на обеих шинах при всех поднятых питаниях —
либо неизвестный бортовой рейл (ни в одном DTB его нет), либо мёртвый
чип/обвязка. Дальше без скопа или вендорных исходников ловить нечего.
Всё откачено (пины, unbind `hci_uart_h5`, DTB — побайтово оригинал
из `/root/radxa-zero.dtb.bak-20261010`, ребут, baseline `-84` + разовый
BCM-шум на месте). `bluez` оставлен (пригодится), `dyndbg`-флаги умерли
ребутом. Скрипты проб (`armbi_rmwifi.sh`, `armbi_ao1v8.py`,
`armbi_rtkbt.py`) лежат у меня в temp — переприменить за минуты,
когда появятся новые данные. Временная сеть — донгл TL-WN725N (`rtl8xxxu`;
на минималке нет ни `nmtui`, ни `nmcli` — только `armbian-config`;
сломанный `/etc/netplan/20-eth-fixed-mac.yaml` с пустым `ethernets:`
лечится удалением строки — ethernet'а на стике физически нет).

## Live-workflow (без перезаливок образа)

Каждая перезаливка + настройка — 30+ минут, поэтому все правки —
`fdtput`/`dtc` прямо в `/boot/dtb` на живой системе (в образе есть)
+ ребут. Правила, выученные здесь:

- Правило 80 секунд между ребутами (USB грузится дольше; 55 мало).
- Один ext4 — один loop за раз (два параллельных маунта = split-brain,
  правка теряется); проверка свежим маунтом после полного detach;
  висячие loop чистить (`losetup -a`).
- `fdtput -d` удаляет только пропсы, НЕ узлы — удаление узлов через
  decompile/sed/recompile (`__symbols__:gpio size 47` при декомпиле —
  безвредное предупреждение исходника).
- `vmmc 3V3` общий у SD-слота и wifi: живой unbind wifi-хоста гасит шину
  и убивает корень на SD. Хосты с общей шиной живьём не дёргать.
- Корень на USB для опасных экспериментов — клоном живьём: голова 4МБ +
  правка таблицы (`sfdisk -N 1`), `mkfs.ext4` без 64bit с тем же UUID,
  `cp -a` системы (влезло 1.5 ГБ на 2 ГБ), `e2fsck`. Копирование на
  медленный ридер — 10+ минут, `sync` вешает надолго: гнать `rsync`
  фоном (`nohup ... &`) и следить через `/proc/<pid>/io` (диск не трогает).
