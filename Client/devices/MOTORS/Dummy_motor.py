"""
A module for simulating KDC101 motor device.

@author: Junho Jeong
@email: jhjeong32@snu.ac.kr
"""
import time
from threading import Thread
import numpy as np

class DummyKDC101:
    """
    A class representing a KDC101 instance

    Methods
    -------
    get_serial_number       : () => str
    get_position            : [bool] => float
    get_acc_and_vel         : () => (int, int)

    set_acc_and_vel         : [int, int] => ()
    
    needs_home              : () => bool
    
    print_msg               : Any => ()
    open                    : [bool] => KDC101
    close                   : () => ()
    start_polling           : [int] => int
    stop_polling            : () => ()
    open_and_start_polling  : [int] => KDC101
    home                    : [bool, bool] => bool
    move_to_position        : number [, bool, bool] => (int, int, int)
    move_relative           : number [, bool, bool] => (int, int, int)
    stop_profiled           : () => ()
    """
    acc = 5
    vel = 5
    is_opened = False
    
    def __init__(self, serno="dummy"):
        """
        Parameters
        ----------
        serno : str
            The serial number of the device
        """
        self.serno = serno
        self.position = np.random.random(1)[0]*12


    def get_position(self):
        """
        Returns
        -------
        float if in_devunit==False
            current position in millimeters
        int if in_devunit==True
            current position in device unit
        """
        return self.position

    def get_acc_and_vel(self):
        """Gets acceleration and max-velocity of the motor.

        Returns
        -------
        tuple (int, int)
            (acceleration, max-velocity) in device unit.
        """

        return self.acc, self.vel

    def set_acc_and_vel(self, acc=None, vel=None):
        """Sets acceleration and max-velocity of the motor.

        Parameters
        ----------
        """
        if not acc == None:
            self.acc = int(acc)
            print("Dummy set acc %d" % self.acc)
        if not vel == None:
            self.acc = int(acc)
            print("Dummy set vel %d" % self.vel)

    def needs_home(self):
        """Dummy retunrs False only.
        """
        return False

    def print_msg(self, msg):
        """Prints message with its serial number to identify itself.

        """
        print("A dummy device that simulates KDC101")

    def open(self, auto_build=True):
        """Opens the device to communicate.
        
        Raises
        ------
        ErrorCodeException - error when opening

        Returns
        -------
        KDC101
            returns self
        """
        sleep_time = np.random.choice(np.arange(1.8, 5.2, 0.2), 1)[0]
        time.sleep(sleep_time)
        success = np.random.random()
        if success < 0.1:
            raise RuntimeError("An error while opening the motor.")
            return
            
        self.is_opened = True
        return self

    def close(self):
        """Closes the device communication.

        """
        self.is_opened = False

    def start_polling(self, interval=200):
        """Starts the internal polling loop to keep track on the device status.
        
        Parameters
        ----------
        interval : int (default 200)
            The polling rate in milliseconds
        
        Raises
        ------
        ValueError - zero or negative interval

        Returns
        -------
        int
            if success, current polling interval in milliseconds.
            zero if polling is not started.
            if the interval is different, returns negated current value.
        """
        if interval <= 0:
            raise ValueError("polling interval must be positive integer.")

        time.sleep(2)  # for stability
        return interval

    def stop_polling(self):
        """Stops the internal polling loop.

        """
        pass
    
    def open_and_start_polling(self, interval=200):
        """Opens and starts polling.

        This method can be useful in with statement.

        Raises
        ------
        FailedException - failed to start polling

        Returns
        -------
        KDC101
            returns self
        """
        self.open()
        set_interval = self.start_polling(interval)
        if set_interval == 0:
            raise FailedException("start polling")
        elif set_interval < 0:
            self.print_msg("Warning: the polling interval is not set.")
            self.print_msg("  - current value: {}ms.".format(set_interval))

        return self

    def home(self, force=False, verbose=False):
        """Homes the device - device will find 'home' and calibrates its
        zero position.

        Waits until the homing process is finished.
        
        Parameters
        ----------
        force : bool (default False)
            forces to home regardless the motor needs it or not

        Returns
        -------
        bool
            whether the device is homed properly or not
        """
        if not self.needs_home():
            self.print_msg("Warning: the device does not need homing.")
            if not force:
                self.print_msg("  - skip homing...")
                return

        if verbose:
            self.print_msg("start homing...")

        pos_thread = Thread(target=self._moving_simulation, args=(self.position, 0))
        pos_thread.daemon = False
        pos_thread.start()
        pos_thread.join()
        
        return True

    def move_to_position(self, pos, in_devunit=False, verbose=False):
        """Moves the motor to the certain position.
        
        Waits until the moving process is finished.

        Parameters
        ----------
        pos : number
            desired destination position of the motor in millimeters
            if in_devunit is True, this is in device unit(check DEVUNIT_RATIO)
        in_devunit : bool (default False)
            if this flag is set, pos is interpretted in device unit
            o.w., pos is interpretted in millimeter
        verbose : bool (default False)
            if this flag is set, status message is displayed
        """
        if pos < 0:
            raise ValueError ("The position must be positive.")
            return
        
        pos_thread = Thread(target=self._moving_simulation, args=(self.position, pos))
        pos_thread.daemon = False
        pos_thread.start()
        pos_thread.join()
        
        return True
    

    def move_relative(self, disp, in_devunit=False, verbose=False):
        """Moves the motor relatively by the given displacement.

        Waits until the moving process is finished.

        Parameters
        ----------
        disp : number
            desired displacement from the current position in millimeters
            if in_devunit is True, this is in device unit(check DEVUNIT_RATIO)
        in_devunit : bool (default False)
            if this flag is set, disp is interpretted in device unit
            o.w., disp is interpretted in millimeter
        verbose : bool (default False)
            if this flag is set, status message is displayed
        """
        return True

    def stop_profiled(self):
        """Stop the device with its motion profile.
        """
        pass
    
    def _moving_simulation(self, cur_pos, tar_pos, velocity=0.05):
        position_list = np.arange(cur_pos, tar_pos, (-1)**(cur_pos > tar_pos)*velocity)
        
        for pos in position_list:
            self.position = pos
            time.sleep(0.05)
        self.position = tar_pos
        return



class FailedException(Exception):
    def __init__(self, failed_action: str):
        super().__init__("failed to {}.".format(failed_action))
