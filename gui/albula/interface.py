import subprocess
import os


class AlbulaInterface:
    _instance = None  # All these variables are used to create a singleton
    _init_args = None
    _process = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(AlbulaInterface, cls).__new__(cls)
        return cls._instance

    def __init__(self, *args, **kwargs):
        
        if self._init_args is None:
            self._init_args = (args, kwargs)
            print("Opening Albula")
            self.use_separate_process = False
            if "python_path" in kwargs:
                self.use_separate_process = True

            self.open(args, kwargs)

    def _call(self, code: str):
        # This method passes any code as string to the spawned python process
        # The code is executed in the python process's interactive shell
        if self._process:
            print(code, file=self._process.stdin, flush=True)

    def open_file(self, filename):
        if isinstance(filename, str):
            index = None
        else:
            # For rasters filename is passed in as a tuple of filename and image index
            index = filename[1]
            filename = filename[0]
        if self.use_separate_process:
            self._call(f'albulaController.disp_file("{filename}", {index})')
        else:
            from gui.albula.controller import albulaController
            albulaController.disp_file(filename, index)

    def close(self):
        if self._process is None:
            return
        if self._process.stdin:
            self._process.stdin.close()
        self._process.terminate()

    def open(self, args, kwargs):
        if self._process is not None and self.use_separate_process:
            return
        if self.use_separate_process:
            self._process = subprocess.Popen(
                [
                    kwargs["python_path"],
                    "-u",
                    "-i",
                    f"{os.path.dirname(os.path.realpath(__file__))}/controller.py",
                ],  # -u for unbuffered I/O, -i to keep stdin open
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                universal_newlines=True,
            )
        
        if "ip" in kwargs and "gov_message_pv_name" in kwargs:
            if self.use_separate_process:
                self._call(
                    f'albulaController.setup_monitor("{kwargs["ip"]}", "{kwargs["gov_message_pv_name"]}")'
                )
            else:
                from gui.albula.controller import albulaController

                albulaController.setup_monitor(
                    kwargs["ip"], kwargs["gov_message_pv_name"]
                )
