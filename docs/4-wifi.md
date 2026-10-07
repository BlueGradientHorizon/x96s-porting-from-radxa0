# WiFi RTL8723BS: драйвер, включение, мультизагрузка

### Как добавлен WiFi-фикс (готово, работает из коробки)

Драйвер 8723bs v5.2.17.1 собран из исходников rockchip_wlan под
4.9.337-aarch64 (vermagic совпал 1:1, стоковый .ko был 32-бит и не
подошел). Правки исходников ([patches-rtl8723bs/](../patches-rtl8723bs), применяются один раз
на чистое дерево скриптом `apply_patches.py rtl8723bs`):
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
- `vendor_dlkm.new.dat.br`: драйверы лежат как `lib/modules/x96s_*.ko`
  (каждый собран с внутренним именем `dhd`, грузится только выбранный —
  коллизий нет), мёртвый Broadcom `dhd.ko` удалён (его ~6.9МБ — бюджет
  под ~3 драйвера). Настоящий ext4-драйвер (`debugfs`: штатная аллокация,
  режим и `security.selinux` сохраняются), затем `e2fsck -f` дочиста.
  Никаких дыр/leak. Удаление идёт ДО записи (места в образе впритык —
  наоборот не влезло бы, словили `verify failed`).
- `vendor.new.dat.br`: `init.amlogic.wifi_buildin.rc` — oneshot-сервис
  [x96s_wifi](../x96s_wifi) (`seclabel u:r:vendor_modprobe:s0`, иначе init не стартует:
  у generic `vendor_file` нет transition) + `wait` SDIO + `start` +
  `wait` ноды `firmware_path` + `chmod 0666` (всё в init, детерминировано
  через inotify). Сам dispatcher ([dispatcher/wifi_select.c](../dispatcher/wifi_select.c): static,
  без libc — на девайсе bionic, glibc-бинарь не встал бы) грузит драйверы
  из map `etc/wifi/x96s_wifi.map` по try-order через `finit_module`
  (sysfs у домена `vendor_modprobe` нет — VID:PID-матчинг переедет
  в `module_init` каждого драйвера, когда появится второй; метка
  бинаря — `vendor_toolbox_exec`, entrypoint домена). Плюс [remote.tab2](../remote.tab2).
  Внешние прошивки НЕ нужны.
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
ретраит сам. Никаких скриптов, поллинга и слипов:
один oneshot-сервис в rc + штатные механизмы. Таблица драйверов —
[x96s_patcher/wifi_drivers.py](../x96s_patcher/wifi_drivers.py) (единый источник: VID:PID, имя в образе,
payload): новая ревизия = собранный драйвер + одна строка, dispatcher
перекомпилировать не надо. Коннект к настроенной точке поднимается
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
- Проверено: loop-mount образов самим ядром 4.9 + `insmod`
  с loop = wlan0 (md5 сходится с payload, сразу WPA-handshake); затем прошивка
  грузится, wifi поднимается сам, коннект к домашней точке.
- Рантайм-загрузка как у стока (см. приложение в конце этого файла): сток грузит
  драйвер userspace-библиотекой `libwifi-hal-common-ext.so`
  (`multi_wifi_load_driver`: sysfs-детект → insmod одного → power →
  проп-триггер на chmod); у LOS этого расширения нет, поэтому наш
  dispatcher повторяет ту же схему на `on boot` (HAL усыновляет только
  раннюю загрузку). Нюансы переноса (все доказаны живьём 2026-10-06):
  `exec` в `on boot` init молча скипает (обе формы); generic `vendor_file`
  без transition не стартует ни как `exec`, ни как сервис — нужен
   `vendor_modprobe` + метка `vendor_toolbox_exec` (нюансы — в [docs/6-pitfalls-status.md](6-pitfalls-status.md)); sysfs
  у этого домена нет — детект try-order'ом, chmod в init.
- wififix-метод через sideload УСТАРЕЛ и не работает (в рекавери
  /vendor read-only) — вместо него хирургия образов внутри скрипта.
- BT заведён отдельным фиксом `vendor-bt` — см. [docs/8-bluetooth.md](8-bluetooth.md).

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

Патчи драйвера — готовые файлы в [patches-rtl8723bs/](../patches-rtl8723bs) (применяются
одним вызовом `apply_patches.py rtl8723bs` из корня исходников
`rtl8723bs`; `CONFIG_PROC_DEBUG` в `include/autoconf.h` НЕ выключать —
тест-хуки зовутся из боевого кода, без них не линкуется):

- [01-procfs-file-operations.patch](../patches-rtl8723bs/01-procfs-file-operations.patch) — порт procfs (`struct proc_ops`
  есть только с ядра 5.6): 1 сигнатура + 7 структур `rtw_*_proc_ops`
  (имена вида `rtw_drv_proc_seq_proc_ops` остаются);
- [02-sdio-power-rescan.patch](../patches-rtl8723bs/02-sdio-power-rescan.patch) — питание и переенумерация:
  `extern_wifi_set_enable` + `sdio_reinit()` (DOWN-UP как в стоке,
  синхронный reinit без единого слипа — эксперименты А/Б 2026-10-04
  убрали 1.5-с settle и все паузы);
- [03-firmware-path-knob.patch](../patches-rtl8723bs/03-firmware-path-knob.patch) — шим под Broadcom-HAL:
  dummy-параметр `firmware_path` (charp 0644);
- [04-modname-dhd.patch](../patches-rtl8723bs/04-modname-dhd.patch) — переименование цели в `dhd.o`
  (`dhd-y := $(8723bs-y)`, иначе имя модуля не сменить).

Зачем каждая часть: `extern_wifi_set_enable` — включает питание чипа
через штатный aml_wifi-драйвер (иначе тишина); `sdio_reinit()` —
amlogic-ресет SDIO именно для Realtek 024C (оживляет карту после
power-cycle, который устраивает dhd при загрузке).

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
  теперь тоже делает DOWN-UP (см. [02-sdio-power-rescan.patch](../patches-rtl8723bs/02-sdio-power-rescan.patch)),
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

## Журнал доводки WiFi (2026-10-02/04, сырая история)

Что пробовали (bring-up):

| Дизайн | Вердикт |
|---|---|
| `on boot` insmod (как донор) | рано (t≈7), чип не всегда готов — но см. финал |
| in-driver retry ×4 | мимо (глухая стена 4/4), откачено |
| init-сервис + скрипт (rmmod рабочего) | работает, но вешает insmod навсегда — убит |
| init-сервис v2 / exec_background / su-сервис / boot_completed-триггер | работают, но скрипты/сервисы запрещены как финал — вычищены |
| ранний plain insmod + SelfRecovery | ФИНАЛ (см. выше в этом файле) |

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
(см. [docs/6-pitfalls-status.md](6-pitfalls-status.md)). Кирпич-цикл от грязного шатдауна: счётчики RescueParty,
лечится вайпом `/data`; не дёргать кабель при висящих ядерных операциях.



---

# Приложение: стоковая мультизагрузка

# Стоковая мультизагрузка WiFi (разведка по образам, 2026-10-06)

Как стоковый Android 9 (X96S_P_20200903-1822, slimBOXtv sbx) выбирает и грузит
один из ~20 WiFi-драйверов в рантайме. Источники: `vendor`/`system`/`boot`
из обоих burn-пакетов (`simg2img` + loop-mount + `strings`, см. методику внизу).
Живой стоковый dmesg/lsmod — в [docs/0-hardware.md](0-hardware.md).

## Механизм (по шагам)

1. **Зоопарк на диске.** Все драйверы лежат в `/vendor/lib/modules/*.ko`
   (раздел 2), у каждого в `modules.alias` свой SDIO/USB alias. Прошивки —
   в `/vendor/firmware/` (Realtek `rtl8723b/d*`, `rtl8761*`, MTK `WIFI_RAM_CODE*`),
   конфиги под каждый чип — в `/vendor/etc/wifi/<чип>/`
   (43458/4354/4356/43569/4358/4359/6212/6255/62x2/6335/AP6271/AP6330,
   MT7601USTA.dat, RT2870STA_7603.dat, qca6174, qca9377, ssv6051, ssv6x5x).
2. **init в этом не участвует.** Стоковый `init.amlogic.wifi_buildin.rc` —
   голый `on boot` без тела; insmod wifi-драйверов нет ни в одном rc
   (есть только `mali/cfg80211/galcore` в board.rc). `wpa_supplicant` объявлен
   `disabled`, его поднимает HAL.
3. **Грузит userspace-библиотека** `/vendor/lib/libwifi-hal-common-ext.so`
   (Amlogic-расширение, слинковано в HAL-сервис
   `/vendor/bin/hw/android.hardware.wifi@1.0-service`, у сервиса capability
   `SYS_MODULE` — право на insmod). Ключевые символы:
   `multi_wifi_load_driver()` → `sdio_wifi_load_driver()` /
   `usb_wifi_load_driver()`, `is_wifi_driver_loaded()`,
   `set_wifi_power()`, `wifi_load_driver_ext()` / `wifi_unload_driver_ext()`.
4. **Детект по sysfs.** SDIO ID читается из
   `/sys/bus/mmc/devices/<host>:0001/<host>:0001:1/device`, USB — из
   `/sys/bus/usb/devices` (+ `/proc/bus/usb`). По таблице VID:PID выбирается
   `.ko` (полный список путей внутри библиотеки — раздел 3), делается insmod,
   дальше ожидание готовности (`check loading wifi driver is ok... /
   driver loaded`, при неудаче выгрузка: `driver not ok, wait`).
5. **Питание чипа — тоже из библиотеки**: `set_wifi_power()` через
   `/dev/wifi_power` (те самые DOWN-UP на t≈74–75 из живого стока;
   слот запитывает `aml_wifi`, `power_on_pin=482`, см. выше в этом файле).
6. **Тайминг поздний.** Грузится не на boot, а при первом включении WiFi
   фреймворком (~t=76) — система уже устаканилась, probe чистый, ноль `-84`.
7. **Финал событийный.** После успеха фреймворк ставит `wlan.driver.status=ok`
   → init-триггер `on property` делает `chown system:wifi + chmod 0660` на
   `firmware_path` сразу для обоих имён (`dhd` и `bcmdhd`).
8. **Broadcom-особенности.** Отдельный сервис `bcmdl` (прошивка в чип 43569,
   `disabled`) и per-chip аргументы `firmware_path=.../fw_....bin
   nvram_path=.../nvram.txt` для AP6271/62xx/63xx/32x. `bcmdhd_init_wlan_mem
   1.579.77.41.9` в dmesg — статически вкомпиленный пред-аллокатор памяти
   Broadcom (в lsmod его нет, грузится только выбранный `8723bs`).

## Драйверы на диске (`/vendor/lib/modules/`)

| Семейство | Модули (сток / sbx) | Шина |
|---|---|---|
| Realtek SDIO | 8189es, 8189fs, 8723bs, 8723ds, 8821cs, 8822bs, 8822cs (все в обоих) | SDIO |
| Realtek USB | 8188eu (только сток), 8723bu, 8723du, 8822bu (кроме 8188eu — в обоих) | USB |
| Broadcom | bcmdhd, dhd, wlan_6174, wlan_9377 (в обоих) | SDIO |
| MediaTek | mt7601usta, mt7603usta, wlan_mt76x8_sdio, wlan_mt76x8_usb (в обоих) + хелпер mtprealloc | USB/SDIO |
| SSV (iComm) | ssv6051, ssv6x5x (в обоих) + хелпер ssv_hwif_ctrl | SDIO/USB |

`modules.dep` у всех wifi-драйверов пуст (зависимостей нет, `cfg80211` —
отдельный insmod в board.rc). Разница сток vs sbx: в sbx нет
`8188eu/8822bs/8822bu/8822cs` (2.4GHz-сборка урезана).

Примеры alias (полная таблица — `modules.alias` на стоковом vendor):
`sdio v024C dB723`→8723bs, `v024C dD723/D724`→8723ds,
`v024C dB821/B821`→8821cs, `v024C d179`→8189fs,
`usb 0BDA:B812/82C`→8822bu, `0BDA:B720`→8723bu,
`07B8:8179/0BDA:0179/8179`→8188eu, `0E8D:7603`→mt7603usta,
`0E8D:7668/7666/6632`→wlan_mt76x8_usb.

## Пути в таблице ext-библиотеки (всего 30, включая отсутствующие на диске)

На диске есть все из раздела 2. Дополнительно библиотека знает, но в оба
пакета **не положены**: 8188fu, 8192es, 8192eu, 8723cs, 8812au, 8821au,
8821cu, atbm602x_usb, wlan_9379. То есть таблица ext-lib — надмножество
(один код на все платы Amlogic, в пакеты кладут подмножество под ревизии).

## Что это значит для LOS (реализовано и работает живьём, 2026-10-06)

В LOS-HAL этого расширения нет: generic HAL умеет только один предзагруженный
модуль с именем `dhd`. Рантайм-система на LOS = собственный загрузчик
`/vendor/bin/x96s_wifi` (исходник в [dispatcher/](../dispatcher), static без libc),
повторяющий шаги 4–5 как oneshot-сервис на `on boot` (HAL усыновляет только
раннюю загрузку, доказано): `wait` SDIO → `start` → finit одного по try-order
map `etc/wifi/x96s_wifi.map` → `wait` ноды `firmware_path` → `chmod`.
Таблица драйверов — [x96s_patcher/wifi_drivers.py](../x96s_patcher/wifi_drivers.py) (VID:PID брать из
стокового `modules.alias`).

Три ограничения переноса, все доказанные живьём (детали и пруфы — в [docs/6-pitfalls-status.md](6-pitfalls-status.md); `0666` вместо событийного `0660` — LOS не ставит
`wlan.driver.status=ok` нашему драйверу, проверено отказом с 0644):

1. `exec` в `on boot` init этой ветки молча скипает (обе формы синтаксиса) —
   только oneshot-сервис + `start`.
2. Generic `vendor_file` не стартует ни как `exec`, ни как сервис (`no domain
   transition from u:r:init:s0`, в on-boot init ошибку не логирует — видно
   только через ручной `ctl.start`). В `vendor_sepolicy.cil` есть ровно один
   штатный домен-загрузчик: `vendor_modprobe` (transition из init, entrypoint
   `vendor_toolbox_exec`, sys_module, kmsg, чтение vendor) — сервис идёт
   с `seclabel u:r:vendor_modprobe:s0`, бинарь помечен `vendor_toolbox_exec`.
3. У `vendor_modprobe` НЕТ sysfs — поэтому никакого sysfs-детекта в userspace:
   выбор try-order'ом (сейчас один драйвер), VID:PID-матчинг переедет в
   `module_init` каждого драйвера (`-ENODEV` при чужом железе), когда
   появится второй; chmod остался в init, у которого sysfs есть.

## Добавление нового драйвера (инструкция на будущее)

Конвейер уже мультидрайверный: dispatcher грузит по try-order из map,
перекомпилировать его НЕ надо. Новая ревизия = payload + одна строка.
По шагам:

0. **Разведка.** VID:PID новой ревизии — живьём
   (`cat /sys/bus/sdio/devices/*/vendor+device`) или из стокового
   `modules.alias` (раздел 2). VID:PID вписывается в таблицу честно:
   колонки нужны будущему матчеру, хоть try-order их пока не читает.
1. **Сборка** — тем же конвейером, что 8723bs (см. раздел сборки драйвера выше в этом файле):
   ядро `f90a0048` + [dotconfig](../dotconfig) + полный `make modules` (нужен свежий
   `Module.symvers` с CRC); патчи `01` (procfs, общий), `02` (питание/
   reinit — проверить, нужен ли именно этому VID; писать безопасным
   на пустой шине), `03` (dummy `firmware_path` — обязателен, HAL),
   `04` (modname `dhd` — обязателен, HAL); `CONFIG_POWER_SAVING=n`;
   НЕ стрипать; проверить `vermagic`
   (`4.9.337 SMP preempt mod_unload modversions aarch64`).
2. **Обязательное для try-order: честный отказ.** Драйвер НЕ должен
   «успешно» грузиться на чужом железе, иначе dispatcher рапортует `up`
   впустую. `module_init` возвращает `-ENODEV`, если его VID:PID
   отсутствует: статический флаг `probed_ok` (ставит probe), после
   register — проверка флага, если пуст → unregister + fail. Квирки
   питания при этом идут ДО энумерации (иначе карту не увидеть), но
   обязаны быть безопасными на пустой шине.
3. **Подключение.** Payload как `x96s_<чип>-4.9.337.ko` рядом
   с [fix_x96s.py](../fix_x96s.py) + одна строка в `WIFI_DRIVERS`
   ([x96s_patcher/wifi_drivers.py](../x96s_patcher/wifi_drivers.py)): `(VID, PID, "lib/modules/x96s_<чип>.ko",
   "x96s_<чип>-4.9.337.ko")`. Map генерируется сам.
4. **Бюджет.** В vendor_dlkm свободно 912 блоков (~3.7 МБ, замерено) —
   влезет ~1 драйвер. Дальше — только хранение сжатым + свой inflate
   в dispatcher (задел, не сделано). Мысль на будущее (анализ 2026-10-06,
   не делать пока не надо): ресайзить ничего не придётся — в super
   свободно ~455 МБ (физический раздел 2084569088 байт, сумма логических
   из `dynamic_partitions_op_list` ~1.63 ГБ; юзердата тут ни при чём —
   `data` отдельная физическая партиция). Расширение vendor_dlkm =
   одна строка `resize` в `dynamic_partitions_op_list` (текст в зипе,
   updater применяет его раньше всех `block_image_update`) + образ
   побольше; verity vendor_dlkm нет (доказано: наши изменённые образы
   грузятся), риск — максимум незалившаяся прошивка, не кирпич.
5. **Проверка** (стандарт, без скидок): патчер по ОРИГИНАЛАМ →
   `testzip`, md5 файла в образе = payload, e2fsck чист, реран = no-op →
   loop-mount + insmod живым ядром 4.9 (до прошивки!) → прошивка →
   `dmesg | grep x96s_wifi` (`trying` → `finit err` на чужом →
   `trying` → `up` на своём), `wlan0` с efuse-MAC, `-84` = 0, ноль
   HAL-ошибок, пинг без потерь. Первым делом проверить `wifi_on`:
   SelfRecovery гасит тумблер после мёртвых бутов (`svc wifi enable`).
6. **Доки.** Обновить [docs/6-pitfalls-status.md](6-pitfalls-status.md) (состояние и журналы — там).

## Методика (repro)

На ubuntu-vm: свой парсер burn-пакетов ([x96s_patcher.amlogic](../x96s_patcher/amlogic.py): CRC без
финального xor, VERIFY вплотную) → извлечь слоты `vendor`/`system`/`boot` →
sparse (`3aff26ed`) через `simg2img`, `boot` — `ANDROID!`-образ (page 2048,
ramdisk пуст — system-as-root) → `mount -o loop,ro` → `grep` по `etc/init/hw`,
`strings` HAL-сервиса и `libwifi-hal-common-ext.so`, `modules.alias/dep`.
Артефакты после разбора удалены (raw ~4ГБ), в репо уехал только этот файл.
