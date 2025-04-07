#!/usr/bin/env python

from farm_tools import SmartFarmSystem, SmartFarmUI
import RPi.GPIO as GPIO
import logging


def configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('smart_farm.log'),
            logging.StreamHandler()
        ]
    )


def main():
    configure_logging()
    logging.info("Starting Smart Farm System")

    try:
        farm = SmartFarmSystem()
        ui = SmartFarmUI(farm)
        ui.run()
    except Exception as e:
        logging.error(f"Fatal error: {str(e)}", exc_info=True)
    finally:
        GPIO.cleanup()
        logging.info("System shutdown complete")


if __name__ == "__main__":
    main()