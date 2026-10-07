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
и заодно решить wifi. Временная сеть — донгл TL-WN725N (`rtl8xxxu`;
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
