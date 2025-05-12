# Car Park License Plate Recognition System

**Author:** Lan Huong (LaHu)

## Core Functionality

This system automates car park entry by:
1.  Detecting vehicles using an STM32 microcontroller.
2.  Capturing license plate images via a Raspberry Pi.
3.  Recognizing plate numbers using OCR.
4.  Verifying authorization against a database.
5.  Controlling a barrier gate via the STM32.

## System Architecture

The system comprises two main components:

### 1. STM32 Microcontroller (STM32F103C8Tx) - Real-time Control Unit

*   **Role:** Manages car detection, servo motor for the gate, OLED status display, and UART communication with the Raspberry Pi.
*   **Key Peripherals:**
    *   `PA1` (Input): Car detection sensor.
    *   `PA0` (TIM2 PWM): Servo motor control for barrier gate.
    *   `PB6/PB7` (I2C1): SSD1306 OLED display.
    *   `PA9/PA10` (USART1): Serial communication with Raspberry Pi (115200 baud).
*   **Firmware:** `Core/Src/main.c` (STM32CubeIDE project: `servotesting.ioc`)

### 2. Raspberry Pi 5 - Image Processing & Logic Unit

*   **Role:** Handles image capture, license plate detection (using `detector.py` with `best.pt` model), OCR (using `ocr_reader.py`), database lookups, and UART communication with the STM32.
*   **Key Software:**
    *   Python 3
    *   OpenCV (`cv2`): Camera interface & image manipulation.
    *   `pyserial`: UART communication.
    *   SQLite3: `car_park.db` for authorized license plates.
*   **Main Script:** `Core/Src/main.py`

## Operational Flow

1.  **Detection:** STM32 detects a car via sensor (PA1).
2.  **STM32 -> RPi:** STM32 sends "CAR\_DETECTED" via UART.
3.  **RPi Processing:**
    *   Receives message.
    *   Captures image.
    *   Detects & OCRs license plate.
    *   Checks plate against `car_park.db`.
4.  **RPi -> STM32:** RPi sends "OK\\n" (authorized) or "NO\\n" (unauthorized/not found) via UART.
5.  **Gate & Display (STM32):**
    *   **"OK":** Opens gate (servo on PA0), displays "Access Granted" on OLED.
    *   **"NO":** Keeps gate closed, displays "Access Denied" on OLED.
    *   STM32 closes gate after car passes (sensor PA1 clear).

## Setup Essentials

*   **STM32:** Program with STM32CubeIDE using `servotesting.ioc`.
*   **Raspberry Pi:**
    *   Run `Core/Src/main.py`.
    *   Ensure `detector.py`, `ocr_reader.py`, and `best.pt` model are accessible.
    *   SQLite database `car_park.db` with a `plates` table (schema: `id INTEGER PRIMARY KEY, plate_number TEXT, owner_name TEXT, access_level INTEGER`) must exist.
*   **UART Connection:** Connect STM32 USART1 (PA9-TX, PA10-RX) to Raspberry Pi UART (`/dev/ttyAMA0`) at 115200 baud.
