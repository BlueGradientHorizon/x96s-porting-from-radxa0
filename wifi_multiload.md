# Стоковая мультизагрузка WiFi (разведка по образам, 2026-10-06)

Как стоковый Android 9 (X96S_P_20200903-1822, slimBOXtv sbx) выбирает и грузит
один из ~20 WiFi-драйверов в рантайме. Источники: `vendor`/`system`/`boot`
из обоих burn-пакетов (`simg2img` + loop-mount + `strings`, см. методику внизу).
Живой стоковый dmesg/lsmod — в README §1.3.

## 1. Механизм (по шагам)

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
   слот запитывает `aml_wifi`, `power_on_pin=482`, см. README §8).
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

## 2. Драйверы на диске (`/vendor/lib/modules/`)

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

## 3. Пути в таблице ext-библиотеки (всего 30, включая отсутствующие на диске)

На диске есть все из раздела 2. Дополнительно библиотека знает, но в оба
пакета **не положены**: 8188fu, 8192es, 8192eu, 8723cs, 8812au, 8821au,
8821cu, atbm602x_usb, wlan_9379. То есть таблица ext-lib — надмножество
(один код на все платы Amlogic, в пакеты кладут подмножество под ревизии).

## 4. Что это значит для LOS (реализовано и работает живьём, 2026-10-06)

В LOS-HAL этого расширения нет: generic HAL умеет только один предзагруженный
модуль с именем `dhd`. Рантайм-система на LOS = собственный загрузчик
`/vendor/bin/x96s_wifi` (исходник в `dispatcher/`, static без libc),
повторяющий шаги 4–5 как oneshot-сервис на `on boot` (HAL усыновляет только
раннюю загрузку, доказано): `wait` SDIO → `start` → finit одного по try-order
map `etc/wifi/x96s_wifi.map` → `wait` ноды `firmware_path` → `chmod`.
Таблица драйверов — `x96s_patcher/wifi_drivers.py` (VID:PID брать из
стокового `modules.alias`).

Три ограничения переноса, все доказанные живьём (детали и пруфы — в README
§10; `0666` вместо событийного `0660` — LOS не ставит
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

## 5. Добавление нового драйвера (инструкция на будущее)

Конвейер уже мультидрайверный: dispatcher грузит по try-order из map,
перекомпилировать его НЕ надо. Новая ревизия = payload + одна строка.
По шагам:

0. **Разведка.** VID:PID новой ревизии — живьём
   (`cat /sys/bus/sdio/devices/*/vendor+device`) или из стокового
   `modules.alias` (раздел 2). VID:PID вписывается в таблицу честно:
   колонки нужны будущему матчеру, хоть try-order их пока не читает.
1. **Сборка** — тем же конвейером, что 8723bs (README §8):
   ядро `f90a0048` + `dotconfig` + полный `make modules` (нужен свежий
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
   с `fix_x96s.py` + одна строка в `WIFI_DRIVERS`
   (`x96s_patcher/wifi_drivers.py`): `(VID, PID, "lib/modules/x96s_<чип>.ko",
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
6. **Доки.** Обновить README §10 и кинуть строку в журнал (§11/§13).

## 6. Методика (repro)

На ubuntu-vm: свой парсер burn-пакетов (`x96s_patcher.amlogic`: CRC без
финального xor, VERIFY вплотную) → извлечь слоты `vendor`/`system`/`boot` →
sparse (`3aff26ed`) через `simg2img`, `boot` — `ANDROID!`-образ (page 2048,
ramdisk пуст — system-as-root) → `mount -o loop,ro` → `grep` по `etc/init/hw`,
`strings` HAL-сервиса и `libwifi-hal-common-ext.so`, `modules.alias/dep`.
Артефакты после разбора удалены (raw ~4ГБ), в репо уехал только этот файл.
