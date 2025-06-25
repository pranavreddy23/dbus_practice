#!/usr/bin/env python3
"""
Hardware Health Monitor Service
A D-Bus service that simulates monitoring hardware sensor data (temperature, voltage)
and exposes it for other applications. This is a common pattern in SLM.
"""
from pydbus import SessionBus
from pydbus.generic import signal
from gi.repository import GLib
import threading
import time
import logging
import sys
import random

# --- Configuration ---
LOGGING_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
BUS_NAME = 'com.example.HardwareHealthMonitor'
SERVICE_INTERFACE = 'com.example.HealthMonitor'
OBJECT_PATH = '/com/example/HealthMonitor'
TEMPERATURE_THRESHOLD = 85.0

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format=LOGGING_FORMAT)
logger = logging.getLogger('HealthMonitorService')


class HardwareSimulator:
    """
    Simulates a hardware sensor, providing realistic-looking data.
    In a real system, this logic would be replaced by reading from a kernel driver
    (e.g., from /sys/class/thermal).
    """
    def __init__(self):
        self._temperature = 65.0
        self._voltage = 1.1
        self._lock = threading.Lock()
        self._running = False
        logger.info("Hardware simulator initialized.")

    def get_sensor_data(self) -> (float, float):
        """Returns the current simulated (temperature, voltage)."""
        with self._lock:
            return self._temperature, self._voltage

    def _simulation_loop(self):
        """Internal loop to generate fluctuating sensor data."""
        while self._running:
            with self._lock:
                # Simulate temperature drift and occasional spikes
                temp_drift = random.uniform(-0.5, 0.5)
                # Every ~20 cycles, simulate a load spike
                if random.randint(0, 20) == 5:
                    temp_drift += random.uniform(5, 15)
                
                self._temperature += temp_drift
                # Clamp temperature within a realistic range
                self._temperature = max(50.0, min(95.0, self._temperature))

                # Simulate minor voltage fluctuations
                self._voltage = random.uniform(1.05, 1.15)
            
            time.sleep(2)

    def start(self):
        """Starts the simulation background thread."""
        if not self._running:
            self._running = True
            thread = threading.Thread(target=self._simulation_loop, daemon=True)
            thread.start()
            logger.info("Hardware simulation thread started.")

    def stop(self):
        """Stops the simulation loop."""
        self._running = False
        logger.info("Hardware simulation thread stopped.")


class HealthMonitorService(object):
    """
    D-Bus service that exposes hardware health data.
    It reads from a data source (the simulator) and publishes on D-Bus.
    """
    dbus = f"""
    <node>
        <interface name='{SERVICE_INTERFACE}'>
            <property name='Temperature' type='d' access='read'/>
            <property name='Voltage' type='d' access='read'/>
            <property name='Version' type='s' access='read'/>
            
            <signal name='TemperatureThresholdExceeded'>
                <arg name='current_temp' type='d'/>
            </signal>
        </interface>
    </node>
    """

    # Define the signal using pydbus.generic
    TemperatureThresholdExceeded = signal()

    def __init__(self, simulator: HardwareSimulator):
        self._simulator = simulator
        self._version = "1.0.0-prototype"
        self._last_temp_reading = 0.0
        self._shutdown_requested = False

        # Start a thread to periodically check the sensor data
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("Health Monitor D-Bus service initialized.")

    def _monitor_loop(self):
        """Periodically checks the simulator and emits signals if necessary."""
        while not self._shutdown_requested:
            temp, _ = self._simulator.get_sensor_data()
            
            # Check if the temperature has crossed the threshold
            if temp > TEMPERATURE_THRESHOLD and self._last_temp_reading <= TEMPERATURE_THRESHOLD:
                logger.warning(f"Temperature threshold exceeded: {temp:.2f}°C")
                self.TemperatureThresholdExceeded(temp)

            self._last_temp_reading = temp
            time.sleep(1) # Check every second

    # --- D-Bus Properties ---
    @property
    def Temperature(self) -> float:
        """Returns the current temperature from the simulator."""
        temp, _ = self._simulator.get_sensor_data()
        return temp

    @property
    def Voltage(self) -> float:
        """Returns the current voltage from the simulator."""
        _, volt = self._simulator.get_sensor_data()
        return volt

    @property
    def Version(self) -> str:
        """Returns the service version."""
        return self._version
        
    def shutdown(self):
        """Performs a graceful shutdown."""
        self._shutdown_requested = True
        logger.info("Shutdown requested for D-Bus service.")


def main():
    """Main service entry point."""
    loop = None
    service = None
    simulator = None
    try:
        # 1. Create the data source
        simulator = HardwareSimulator()
        simulator.start()

        # 2. Create the D-Bus service and give it the data source
        service = HealthMonitorService(simulator)
        
        # 3. Publish the service on the D-Bus at a specific object path
        bus = SessionBus()
        # The path must come FIRST in the tuple
        bus.publish(BUS_NAME, (OBJECT_PATH, service))
        
        logger.info(f"'{BUS_NAME}' service running at '{OBJECT_PATH}'. Press Ctrl+C to stop.")
        
        # 4. Run the main loop
        loop = GLib.MainLoop()
        loop.run()
        
    except KeyboardInterrupt:
        logger.info("Service stopped by user.")
    except Exception as e:
        logger.error(f"Service failed: {e}")
        sys.exit(1)
    finally:
        if simulator:
            simulator.stop()
        if service:
            service.shutdown()
        if loop:
            loop.quit()
        logger.info("Service has been shut down.")


if __name__ == "__main__":
    main() 