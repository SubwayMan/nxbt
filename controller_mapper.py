import asyncio
import logging
from typing import Dict, Any, Optional
from .nxbt import Nxbt, Buttons, Sticks, PRO_CONTROLLER, JOYCON_L, JOYCON_R
import json
import inputs
import threading
import time
import argparse

class ControllerMapper:
    """Maps physical controller inputs to nxbt commands."""
    
    def __init__(self, debug: bool = False, test_mode: bool = False):
        """Initialize the controller mapper.
        
        Args:
            debug: Enable debug logging
            test_mode: Enable test mode to print raw inputs
        """
        self.debug = debug
        self.test_mode = test_mode
        self.logger = logging.getLogger('controller_mapper')
        if debug:
            self.logger.setLevel(logging.DEBUG)
            
        # Initialize nxbt
        self.nx = Nxbt(debug=debug)
        self.controller_idx: Optional[int] = None
        
        # Default button mappings
        self.button_mappings = {
            'BTN_SOUTH': Buttons.B,  # B button (bottom)
            'BTN_EAST': Buttons.A,   # A button (right)
            'BTN_NORTH': Buttons.X,  # X button (top)
            'BTN_WEST': Buttons.Y,   # Y button (left)
            'BTN_TL': Buttons.L,
            'BTN_TR': Buttons.R,
            'BTN_TL2': Buttons.ZL,
            'BTN_TR2': Buttons.ZR,
            'BTN_START': Buttons.PLUS,
            'BTN_SELECT': Buttons.MINUS,
            'BTN_MODE': Buttons.HOME,
        }
        
        # Default stick mappings
        self.stick_mappings = {
            'ABS_X': ('L_STICK', 'x'),  # Left stick X
            'ABS_Y': ('L_STICK', 'y'),  # Left stick Y
            'ABS_RX': ('R_STICK', 'x'),  # Right stick X
            'ABS_RY': ('R_STICK', 'y'),  # Right stick Y
        }
        
        # Trigger mappings
        self.trigger_mappings = {
            'ABS_Z': Buttons.ZL,  # Left trigger
            'ABS_RZ': Buttons.ZR,  # Right trigger
        }
        
        # Current input state
        self.current_input = self.nx.create_input_packet()
        
        # Input processing state
        self.running = False
        self.input_thread = None
        
    async def connect_controller(self, controller_type: int = PRO_CONTROLLER) -> int:
        """Connect a controller.
        
        Args:
            controller_type: Type of controller to create (PRO_CONTROLLER, JOYCON_L, or JOYCON_R)
            
        Returns:
            int: Controller index
        """
        if not self.test_mode:
            self.controller_idx = self.nx.create_controller(controller_type)
            
            # Wait for connection
            while True:
                state = self.nx.state[self.controller_idx]['state']
                if state == 'connected':
                    break
                elif state == 'crashed':
                    raise ConnectionError(f"Controller failed to connect: {self.nx.state[self.controller_idx]['errors']}")
                await asyncio.sleep(0.1)
                
            return self.controller_idx
        return 0
    
    def _process_gamepad_event(self, event):
        """Process a gamepad event and convert it to nxbt input."""
        if self.test_mode:
            # In test mode, just print the event
            print(f"Event: {event.ev_type} {event.code} = {event.state}")
            return
            
        if event.ev_type == 'Key':  # Button press/release
            if event.code in self.button_mappings:
                nxbt_button = self.button_mappings[event.code]
                self.current_input[nxbt_button] = event.state == 1
                if self.debug:
                    self.logger.debug(f"Button {event.code} -> {nxbt_button}: {event.state == 1}")
                self.nx.set_controller_input(self.controller_idx, self.current_input)
                
        elif event.ev_type == 'Absolute':  # Stick/trigger movement
            # Handle triggers
            if event.code in self.trigger_mappings:
                button = self.trigger_mappings[event.code]
                # Normalize trigger value from 0-255 to 0-100
                value = int((event.state / 255) * 100)
                # Set the button state based on trigger value
                self.current_input[button] = value > 50  # Consider pressed if more than halfway
                if self.debug:
                    self.logger.debug(f"Trigger {event.code} -> {button}: {value > 50}")
                self.nx.set_controller_input(self.controller_idx, self.current_input)
                return
                
            # Handle D-pad
            if event.code == 'ABS_HAT0X':
                self.current_input[Buttons.DPAD_LEFT] = event.state == -1
                self.current_input[Buttons.DPAD_RIGHT] = event.state == 1
                if self.debug:
                    self.logger.debug(f"D-pad X: left={event.state == -1}, right={event.state == 1}")
            elif event.code == 'ABS_HAT0Y':
                self.current_input[Buttons.DPAD_UP] = event.state == -1
                self.current_input[Buttons.DPAD_DOWN] = event.state == 1
                if self.debug:
                    self.logger.debug(f"D-pad Y: up={event.state == -1}, down={event.state == 1}")
            # Handle sticks
            elif event.code in self.stick_mappings:
                stick_name, axis = self.stick_mappings[event.code]
                # Normalize stick values from -32768/32767 to -100/100
                value = int((event.state / 32767) * 100)
                # Invert Y axis values
                if axis == 'y':
                    value = -value
                if axis == 'x':
                    self.current_input[stick_name]['X_VALUE'] = value
                else:
                    self.current_input[stick_name]['Y_VALUE'] = value
                
                if self.debug:
                    self.logger.debug(f"Stick {event.code} -> {stick_name} {axis}: {value}")
                self.nx.set_controller_input(self.controller_idx, self.current_input)
    
    def _input_loop(self):
        """Main input processing loop."""
        while self.running:
            try:
                events = inputs.get_gamepad()
                for event in events:
                    self._process_gamepad_event(event)
            except Exception as e:
                self.logger.error(f"Error processing input: {e}")
                time.sleep(0.1)  # Prevent tight loop on error
    
    def start_input_processing(self):
        """Start processing physical controller inputs."""
        if self.input_thread is not None:
            return
            
        self.running = True
        self.input_thread = threading.Thread(target=self._input_loop)
        self.input_thread.daemon = True
        self.input_thread.start()
        
    def stop_input_processing(self):
        """Stop processing physical controller inputs."""
        self.running = False
        if self.input_thread is not None:
            self.input_thread.join()
            self.input_thread = None
            
    async def cleanup(self) -> None:
        """Clean up the controller."""
        self.stop_input_processing()
        if self.controller_idx is not None:
            self.nx.remove_controller(self.controller_idx)

def parse_args():
    parser = argparse.ArgumentParser(description='Controller Mapper for NXBT')
    parser.add_argument('--test', action='store_true', help='Run in test mode to see raw controller inputs')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    return parser.parse_args()

# Example usage:
async def main():
    args = parse_args()
    
    # Create mapper
    mapper = ControllerMapper(debug=args.debug, test_mode=args.test)
    
    try:
        if not args.test:
            # Connect controller
            await mapper.connect_controller()
            print("Controller connected!")
        else:
            print("Running in test mode - showing raw controller inputs")
            print("Press Ctrl+C to exit")
        
        # Start processing physical controller inputs
        mapper.start_input_processing()
        print("Input processing started. Press Ctrl+C to exit.")
        
        # Keep the program running
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        await mapper.cleanup()

if __name__ == "__main__":
    asyncio.run(main()) 