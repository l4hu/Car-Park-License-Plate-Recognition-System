#!/usr/bin/env python3
import time
import logging
import sqlite3
import serial
import cv2
import numpy as np
from io import BytesIO
import threading
import os
import sys
from datetime import datetime

from detector import LicensePlateDetector
from ocr_reader import OCRReader

log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f"carpark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

logger = logging.getLogger("CarParkSystem")
logger.setLevel(logging.DEBUG)

file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.INFO)
file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_format)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)
console_format = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
console_handler.setFormatter(console_format)

logger.addHandler(file_handler)
logger.addHandler(console_handler)
logger.propagate = False

class CarParkSystem:
    def __init__(self):
        logger.debug("Initializing Car Park System")
        self.PORT = "/dev/ttyAMA0"
        self.BAUDRATE = 115200
        self.serial_conn = None
        logger.debug("Loading license plate detection model")
        self.detector = LicensePlateDetector(model_path="best.pt")
        logger.debug("Loading OCR model")
        self.ocr = OCRReader()
        self.db_conn = None
        self.camera_id = 0
        self.frame_width = 1280
        self.frame_height = 720
        logger.debug(f"Camera settings: ID={self.camera_id}, Resolution={self.frame_width}x{self.frame_height}")
        self.is_running = False
        self.current_frame = None
        self.camera_thread = None
        logger.debug("Car Park System initialization complete")

    def connect_to_serial(self):
        logger.debug(f"Attempting to connect to STM32 on port {self.PORT} at {self.BAUDRATE} baud")
        try:
            self.serial_conn = serial.Serial(
                port=self.PORT,
                baudrate=self.BAUDRATE,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1
            )
            logger.info(f"Connected to STM32 on {self.PORT}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to serial port: {e}")
            logger.debug(f"Serial connection error details: {str(e)}", exc_info=True)
            return False

    def connect_to_database(self):
        db_path = 'car_park.db'
        logger.debug(f"Attempting to connect to database at {os.path.abspath(db_path)}")
        try:
            self.db_conn = sqlite3.connect(db_path, check_same_thread=False)
            cursor = self.db_conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='plates'")
            if not cursor.fetchone():
                logger.warning("Plates table not found in database. Creating it.")
                cursor.execute(
                    "CREATE TABLE plates (id INTEGER PRIMARY KEY, plate_number TEXT, owner_name TEXT, access_level INTEGER)"
                )
                self.db_conn.commit()
                logger.debug("Created plates table in database")
            else:
                cursor.execute("PRAGMA table_info(plates)")
                columns = [col[1] for col in cursor.fetchall()]
                logger.debug(f"Database columns: {columns}")
            logger.info("Connected to database successfully")
            return True
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            logger.debug(f"Database connection error details: {str(e)}", exc_info=True)
            return False

    def initialize_camera(self):
        logger.debug(f"Initializing camera (ID: {self.camera_id})")
        def camera_loop():
            logger.debug("Camera thread started")
            cap = cv2.VideoCapture(self.camera_id)
            if not cap.isOpened():
                logger.error(f"Failed to open camera with ID {self.camera_id}")
                return
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_height)
            actual_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            actual_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            actual_fps = cap.get(cv2.CAP_PROP_FPS)
            logger.debug(f"Camera parameters: {actual_width}x{actual_height} at {actual_fps} FPS")
            logger.info("Camera initialized successfully")
            frame_count = 0
            start_time = time.time()
            while self.is_running:
                ret, frame = cap.read()
                if ret:
                    self.current_frame = frame
                    frame_count += 1
                    if frame_count % 900 == 0:
                        elapsed = time.time() - start_time
                        fps = frame_count / elapsed if elapsed > 0 else 0
                        logger.debug(f"Camera capturing at {fps:.2f} FPS")
                        frame_count = 0
                        start_time = time.time()
                else:
                    logger.warning("Failed to capture frame from camera")
                time.sleep(0.03)
            logger.debug("Camera thread stopping")
            cap.release()
            logger.debug("Camera released")

        self.is_running = True
        self.camera_thread = threading.Thread(target=camera_loop, name="CameraThread")
        self.camera_thread.daemon = True
        self.camera_thread.start()
        logger.debug("Waiting for camera initialization")
        time.sleep(2)
        is_alive = self.camera_thread.is_alive()
        logger.debug(f"Camera thread status: {'Running' if is_alive else 'Failed'}")
        return is_alive

    def check_plate_in_database(self, plate_number):
        logger.debug(f"Checking plate '{plate_number}' in database")
        if not self.db_conn:
            logger.error("Database not connected")
            return False
        try:
            cursor = self.db_conn.cursor()
            query = "SELECT COUNT(*) FROM plates WHERE plate_number = ?"
            logger.debug(f"Executing query: {query} with param: {plate_number}")
            cursor.execute(query, (plate_number,))
            count = cursor.fetchone()[0]
            logger.info(f"Plate {plate_number}: {'Authorized' if count > 0 else 'Unauthorized'}")
            return count > 0
        except Exception as e:
            logger.error(f"Database query error: {e}")
            logger.debug(f"Database query error details: {str(e)}", exc_info=True)
            return False

    def process_captured_image(self):
        logger.debug("Processing captured image for license plate detection")
        if self.current_frame is None:
            logger.error("No camera frame available")
            return None
        try:
            frame_shape = self.current_frame.shape
            logger.debug(f"Processing frame with shape: {frame_shape}")
            start_time = time.time()
            ret, buffer = cv2.imencode('.jpg', self.current_frame)
            if not ret:
                logger.error("Failed to encode image")
                return None
            jpg_bytes = BytesIO(buffer).getvalue()
            logger.debug(f"Image encoded to JPEG: {len(jpg_bytes)} bytes")
            detection_start = time.time()
            cropped_plate = self.detector.detect_and_crop(jpg_bytes)
            detection_time = time.time() - detection_start
            logger.debug(f"License plate detection took {detection_time:.3f} seconds")
            if cropped_plate is None:
                logger.warning("No license plate detected in the image")
                return None
            ocr_start = time.time()
            plate_text = self.ocr.read_text(cropped_plate)
            ocr_time = time.time() - ocr_start
            logger.debug(f"OCR processing took {ocr_time:.3f} seconds")
            if not plate_text:
                logger.warning("Could not read license plate text")
                return None
            original_text = plate_text
            plate_text = ''.join(ch for ch in plate_text if ch.isalnum()).upper()
            logger.debug(f"OCR result: '{original_text}' cleaned to '{plate_text}'")
            total_time = time.time() - start_time
            logger.info(f"Detected license plate: {plate_text} (processing took {total_time:.3f} seconds)")
            return plate_text
        except Exception as e:
            logger.error(f"Error processing image: {e}")
            logger.debug(f"Image processing error details: {str(e)}", exc_info=True)
            return None

    def run(self):
        logger.info("Starting Car Park System")
        if not self.connect_to_serial():
            logger.error("Failed to initialize serial connection")
            return
        if not self.connect_to_database():
            logger.error("Failed to initialize database")
            return
        if not self.initialize_camera():
            logger.error("Failed to initialize camera")
            return
        logger.info("System initialized and ready")
        idle_count = 0
        while True:
            if self.serial_conn.in_waiting > 0:
                idle_count = 0
                serial_data = self.serial_conn.readline().decode('utf-8').strip()
                logger.info(f"Received from STM32: {serial_data}")
                if "CAR_DETECTED" in serial_data:
                    event_start = time.time()
                    time.sleep(0.5)
                    plate_number = self.process_captured_image()
                    if plate_number:
                        is_authorized = self.check_plate_in_database(plate_number)
                        if is_authorized:
                            self.serial_conn.write(b"OK\n")
                            logger.info(f"Access granted for plate: {plate_number}")
                        else:
                            self.serial_conn.write(b"NO\n")
                            logger.info(f"Access denied for plate: {plate_number}")
                    else:
                        self.serial_conn.write(b"NO\n")
                        logger.info("Access denied: License plate not recognized")
                    event_time = time.time() - event_start
                    logger.debug(f"Event processing time: {event_time:.3f}s")
            else:
                idle_count += 1
                if idle_count >= 100:
                    idle_count = 0
            time.sleep(0.1)

if __name__ == "__main__":
    logger.debug("Script started")
    try:
        car_park_system = CarParkSystem()
        car_park_system.run()
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
