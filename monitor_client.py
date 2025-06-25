#!/usr/bin/env python3
"""
Hardware Health Monitor Client
Connects to the Health Monitor D-Bus service to read sensor data and listen for
critical temperature alerts. This represents an application that needs to monitor
the hardware state (e.g., a system management UI, a thermal daemon).
"""
from pydbus import SessionBus
from gi.repository import GLib
import logging
import sys
import threading
import time

# --- Configuration ---
LOGGING_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
BUS_NAME = 'com.example.HardwareHealthMonitor'
SERVICE_INTERFACE = 'com.example.HealthMonitor'
OBJECT_PATH = '/com/example/HealthMonitor'

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format=LOGGING_FORMAT)
logger = logging.getLogger('HealthMonitorClient')


class HealthMonitorClient:
    """Client to interact with the HealthMonitorService."""
    
    def __init__(self):
        self.bus = SessionBus()
        self.monitor_proxy = None
        self._running = False
        
    def connect(self) -> bool:
        """Connect to the monitor service."""
        try:
            self.monitor_proxy = self.bus.get(BUS_NAME, OBJECT_PATH)
            logger.info("Successfully connected to Health Monitor Service.")
            return True
        except Exception as e:
            logger.error(f"Connection to service failed: {e}")
            return False
    
    def subscribe_to_signals(self):
        """Subscribe to the TemperatureThresholdExceeded signal."""
        try:
            self.bus.subscribe(
                iface=SERVICE_INTERFACE,
                signal="TemperatureThresholdExceeded",
                signal_fired=self._on_temp_threshold_exceeded
            )
            logger.info("Subscribed to 'TemperatureThresholdExceeded' signal.")
        except Exception as e:
            logger.error(f"Failed to subscribe to signals: {e}")
    
    def _on_temp_threshold_exceeded(self, *args):
        """Handles the critical temperature signal."""
        # pydbus signal arguments can be complex, let's unpack safely
        try:
            # Expected args: (sender, object, interface, signal, (params,))
            if len(args) >= 5 and isinstance(args[4], tuple) and args[4]:
                current_temp = args[4][0]
                logger.critical(f"ALERT! Temperature threshold exceeded! Current Temp: {current_temp:.2f}°C")
            else:
                logger.warning(f"Received temperature alert with unexpected format: {args}")
        except Exception as e:
            logger.error(f"Error handling temperature signal: {e}")

    def _monitor_loop(self):
        """Periodically polls properties from the service."""
        while self._running:
            try:
                temp = self.monitor_proxy.Temperature
                volt = self.monitor_proxy.Voltage
                version = self.monitor_proxy.Version
                
                logger.info(f"Monitor Status | Temp: {temp:.2f}°C | Voltage: {volt:.3f}V | Service Version: {version}")
                
            except Exception as e:
                logger.error(f"Failed to read properties: {e}")
                # If we fail, the service might have gone away. Stop the demo.
                self._running = False
                
            time.sleep(5) # Poll every 5 seconds

    def run_demo(self):
        """Runs the main client monitoring logic."""
        logger.info("Starting Health Monitor Client demo.")
        
        self._running = True
        # Start the polling loop in a background thread
        monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        monitor_thread.start()
        
        logger.info("Client is now monitoring hardware health. Press Ctrl+C to stop.")
    
    def run(self):
        """Main client entry point."""
        loop = None
        try:
            if not self.connect():
                sys.exit(1)
            
            self.subscribe_to_signals()
            self.run_demo()
            
            # The GLib main loop is required to receive D-Bus signals
            loop = GLib.MainLoop()
            loop.run()
            
        except KeyboardInterrupt:
            logger.info("Client stopped by user.")
        except Exception as e:
            logger.error(f"Client failed: {e}")
        finally:
            self._running = False
            if loop:
                loop.quit()
            logger.info("Client has been shut down.")

def main():
    """Main function."""
    client = HealthMonitorClient()
    client.run()

if __name__ == "__main__":
    main() 