# Доступ и диагностика

## Доступ к железу

platform-tools, USB Burning Tool 2.x (драйвер WorldCup), Python 3.8+
(только stdlib), Rust+git (разово, для `ampack`), паяльник, лупа.

### ADB

- Сток: microUSB к ПК (`X96S_P`), рут есть (userdebug).
- Lineage: Developer options (USB + Network), `adb root` работает.
- Recovery: adb включается пунктом меню (в новых сборках вручную!).
  Sideload — `Apply from ADB`.
- Втыкание 3.5мм ИК-глазка наживую роняет USB-adb (`offline`): джек
  коротит питание, USB PHY ресетится, SoC жив. Лечение:
  `adb reconnect offline` / перетык microUSB. Глазок — только на
  обесточенном!

### UART (главный инструмент восстановления)

На обороте платы 4 пада `VCC GND RX TX` (рядом подпись 3.3V).
Мост из ESP32-C3 Super Mini:

```cpp
void setup() {
  Serial.begin(115200);
  Serial1.begin(115200, SERIAL_8N1, 20, 21); // 20=RX моста, 21=TX моста
}
void loop() {
  while (Serial.available()) Serial1.write(Serial.read());
  while (Serial1.available()) Serial.write(Serial1.read());
}
```

Arduino IDE: `ESP32C3 Dev Module`, `USB CDC On Boot: Enabled`.
Только 3 провода (GND-GND, TX_стика→GPIO20, RX_стика→GPIO21),
VCC не подключать. PuTTY 115200 8N1.

### U-Boot (вендорный 2015.01, `g12a_radxa0_v1#`)

- Вход: держать Enter/Space + подать питание (autoboot ~0-1с).
- `run recovery_from_flash` — в рекавери без кнопок.
- `usb start 0` + `fatload/fatwrite usb 0 <addr> <file> [size]` +
  `store read|write <name> <addr> <off> <size>` (dtbo = `0x800000`).
  Конкретный пример — откат битого dtbo заведомо целым с USB-флешки
  (флешка с `dtbo.img` из любой прошивки Lineage в полноразмерном
  USB-порту стика):
  ```
  usb start 0
  fatload usb 0 0x1000000 dtbo.img
  store write dtbo 0x1000000 0 0x800000
  reset
  ```
- Консоль ядра: `setenv initargs "${initargs} console=ttyS0,115200"`
  + `saveenv` (cmdline собирается из `initargs`, править boot.img
  бесполезно — u-boot его перезаписывает).
- Не вставлять многострочный текст в терминал: так был стерт
  загрузчик (`store erase ...` из help!). Лечится повторной прошивкой
  `aml_install_package.img` (WorldCup появляется сам).

### Burn mode и установка Lineage (всё в Windows)

1. `aml_install_package.img` → USB Burning Tool → `Resetting board [OK]`.
2. Цикл питания с USB-клавой → Lineage Recovery.
3. `fastboot -w wipe-super super_empty.img`, Format data,
   `adb -d sideload lineage-*.zip`, reboot (первая загрузка ~1–2 мин:
   ~1 мин обычно, ~2 мин после вайпа `/data` — замерено секундомером).
4. Тестпоинт eMMC — рядом с чипом Samsung (на другой стороне платы
   от UART; фото есть на 4pda для соседней ревизии, контакты совпали):
   замкнуть пинцетом в момент подачи питания, держать до детекта
   WorldCup в Burning Tool. Наживую — просто ребут.

## Диагностика (эталонные команды, в каталоге с `adb`)

```powershell
.\adb.exe shell "lsmod | grep 8723bs; dmesg | grep -iE 'rtl8723|meson-remote|fb04|xhci'"
.\adb.exe shell "cat /sys/bus/sdio/devices/*/vendor; cat /sys/bus/sdio/devices/*/device"
.\adb.exe shell "cat /proc/bus/input/devices; ls -l /dev/amremote"
.\adb.exe shell "getevent -lt /dev/input/event0"   # жать кнопки пульта
```

