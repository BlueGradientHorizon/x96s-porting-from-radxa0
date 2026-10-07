# X96S — бортовой журнал

ТВ-стик X96S 2/16 (Amlogic S905Y2) под LineageOS 22.2 (radxa0, Android 15).
Цель: портировщик или ИИ-агент повторяет любой результат пошагово.
Подробности — в [docs/](docs), здесь только карта.

Железо коротко: SoC S905Y2, 2/16, WiFi/BT RTL8723BS только 2.4 ГГц
(SDIO `024c:b723`), ИК `meson-remote ff808040.rc`, USB-A только USB 2.0.
Сток [X96S_P_20200903-1822.img](flash/X96S_P_20200903-1822.img), кастом slimBOXtv `sbx_*atv*.img` — не путать.

## Быстрый старт

Патчер запускается на Linux-хосте (`e2fsprogs`, `python3-brotli`):

```bash
cd /media/sf_x96s && python3 fix_x96s.py flash/los-*/lineage-*.zip
python3 fix_x96s.py flash/los-*/aml_install_package.img
```

Выход: `out/<name>-x96s-fix.zip` (ПОР) и
`out/aml_install_package-radxa0[_tab]-x96s-fix.img` (ПОА).
Флоу: burn fixed-ПОА → рекавери с пультом → sideload fixed-ПОР.
Детали — [docs/3-patcher.md](docs/3-patcher.md), [docs/5-bootloader.md](docs/5-bootloader.md).

## Статус

Работает из коробки (проверено холодными бутами, см. [docs/6-pitfalls-status.md](docs/6-pitfalls-status.md)):
пульт ИК (DTBO + tab2), WiFi (ранний `on boot` insmod, efuse-MAC, ноль `-84`)
и BT RTL8723BS (RTK H5-стек со стока, адрес чипа, спаривание, A2DP;
детали — в [docs/8-bluetooth.md](docs/8-bluetooth.md)).

## Доки

| Файл | Что внутри (старые § README) |
|---|---|
| [docs/0-hardware.md](docs/0-hardware.md) | §1–2: стик, донор Radxa Zero, сырые замеры стока, симптомы LOS |
| [docs/1-access.md](docs/1-access.md) | §3–4: adb/UART/u-boot/burn mode, эталонные команды |
| [docs/2-remote.md](docs/2-remote.md) | §5–6: пульт целиком (DTBO-оверлей + userspace-табы + кеймап) |
| [docs/3-patcher.md](docs/3-patcher.md) | §7–8: инвентарь, архитектура [fix_x96s.py](fix_x96s.py), реестр, почему vendor не едет в ПОА |
| [docs/4-wifi.md](docs/4-wifi.md) | §8-WiFi + §11: сборка драйвера, включение, мультизагрузка |
| [docs/5-bootloader.md](docs/5-bootloader.md) | §8-u-boot + §13: сборка загрузчика, burn-пакеты, WorldCup/env |
| [docs/6-pitfalls-status.md](docs/6-pitfalls-status.md) | §9 + §10 + §12: 21 ловушка, текущее состояние/TODO |
| [docs/7-armbian.md](docs/7-armbian.md) | SD-конверт, extboot, USB-носители |
| [docs/8-bluetooth.md](docs/8-bluetooth.md) | BT RTL8723BS целиком: стек, фикс `vendor-bt`, задел на диспетчер |

Per-unit данные (серийники, MAC, CID eMMC, IP) в доках маскируются
(`XX:XX:XX`, `<из DHCP>`). Правила работы агента — в [AGENTS.md](AGENTS.md).
