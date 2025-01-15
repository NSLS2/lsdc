import os
import socket

from ophyd import Component as Cpt
from ophyd import Device, EpicsSignal, EpicsSignalRO, PVPositioner
from ophyd.status import SubscriptionStatus


class MD2Positioner(PVPositioner):
    setpoint = Cpt(EpicsSignal, "Position", name="setpoint")
    readback = Cpt(EpicsSignal, "Position", name="readback")
    state = Cpt(EpicsSignalRO, "State", name="state")
    done = Cpt(EpicsSignalRO, "State", name="done")
    precision = Cpt(EpicsSignalRO, "Precision", name="precision")
    done_value = 4  # MD2 Enum, 4 = Ready
    # TODO: Add limits, settle_time, timeout or defaults for each

    def val(self):
        return self.get().readback


class ExporterComponent(Cpt):
    def __init__(self, address, port, name, **kwargs):
        super().__init__(self, **kwargs)
        self.name = name
        self.address = address
        self.port = port
        self.sock = None  # socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # self.sock.settimeout(5)

    def get(self):
        return ()

    def connect(self):
        # for establishing connection, using context manager is preferred
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.address, self.port))

    def disconnect(self):
        self.sock.close()
        self.sock = None

    def send_data(self, data):
        STX = chr(2)
        ETX = chr(3)
        data = STX + data + ETX
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((self.address, self.port))
            s.sendto(data.encode(), (self.address, self.port))
            state = s.recv(4096)
            print(f"state: {self.decipher_reply(state)}")
            ret = None
            while ret is None:
                output = s.recv(4096)
                output = self.decipher_reply(output)
                ret = self.process_ret(output)
            return ret

    def read_stream(self):
        output = None
        while output is None:
            output, addr = self.sock.recvfrom(4096)
            print(f"output:{self.decipher_reply(output)}")
            output = None

    def write(self, attribute, value):
        return self.send_data("WRTE " + attribute + " " + str(value))

    def read(self, attribute):
        return (self.send_data("READ " + attribute + " ")).split(" ")[0][4:]

    def cmd(self, method, parameters):
        parameters = map(str, parameters)
        params = "\t".join(parameters)
        return self.send_data("EXEC " + method + " " + str(params))

    def decipher_reply(self, reply):
        # Specifically for decoding MD2 Exporter replies
        reply = str(reply)
        reply = reply.replace("\\x03", "")
        reply = reply.replace("\\x1f", ", ")
        reply = reply.replace("\\x02", "\n")
        reply = reply.replace("\\t", " ")
        return reply[2:-1]

    def process_ret(self, ret):
        # Returns only when an error or return value is found,
        # ignores events to ensure flyer kickoff functions as expected
        for line in ret.split("\n"):
            if "ERR:" in line:
                print(f"error: {line}")
                return line
            elif "RET:" in line:
                print(f"returned: {line}")
                return line
            elif "NULL" in line:
                print(f"null error: {line}")
                return line
            elif "EVT:" in line:  # print here if you want to see the events
                pass  # return self.process_evt(line)


class LightDevice(Device):
    control = Cpt(EpicsSignal, "LightIsOn", name="control")
    factor = Cpt(EpicsSignal, "LightFactor", name="factor")
    level = Cpt(EpicsSignal, "LightLevel", name="level")

    def is_on(self):
        return self.control.get() == 1

    def turn_on(self):
        self.control.set(1)

    def turn_off(self):
        self.control.set(0)

    def set_factor(self, factor):
        self.factor.set(factor)

    def set_level(self, level):
        self.level.set(level)


class BeamstopDevice(Device):
    distance = Cpt(MD2Positioner, "BeamstopDistance", name="distance")
    distance_preset = Cpt(EpicsSignal, "BeamstopDistance", name="distance_preset")
    x = Cpt(MD2Positioner, "BeamstopX", name="x")
    y = Cpt(MD2Positioner, "BeamstopY", name="y")
    z = Cpt(MD2Positioner, "BeamstopZ", name="z")
    pos = Cpt(EpicsSignal, "BeamstopPosition", name="pos")


class MD2SimpleHVDevice(Device):
    horizontal = Cpt(MD2Positioner, "HVHorizontal", name="horizontal")
    vertical = Cpt(MD2Positioner, "HVVertical", name="vertical")
    pos = Cpt(EpicsSignal, "HVPosition", name="pos")
    # Current aperture/scintillator/capillary predifined position.
    # Enum: the aperture position:
    # 0: PARK, under cover.
    # 1: BEAM, selected aperture aligned with beam.
    # 2: OFF, just below the OAV.
    # 3: UNKNOWN, not in a predefined position (this cannot be set).


class GonioDevice(Device):
    omega = Cpt(MD2Positioner, "Omega", name="omega")
    x = Cpt(MD2Positioner, "AlignmentX", name="x")
    y = Cpt(MD2Positioner, "AlignmentY", name="y")
    z = Cpt(MD2Positioner, "AlignmentZ", name="z")
    cx = Cpt(MD2Positioner, "CentringX", name="cx")
    cy = Cpt(MD2Positioner, "CentringY", name="cy")


class MD2Device(GonioDevice):
    # TODO: Enum for MD2 phases and states
    cx = Cpt(MD2Positioner, "CentringX", name="cx")
    cy = Cpt(MD2Positioner, "CentringY", name="cy")
    center_pixel_x = Cpt(EpicsSignalRO, "BeamPositionHorizontal", name="center_pixel_x")
    center_pixel_y = Cpt(EpicsSignalRO, "BeamPositionVertical", name="center_pixel_y")
    centring_click = Cpt(EpicsSignal, "setCentringClick", name="centring_click")
    centring_save = Cpt(EpicsSignal, "saveCentringPositions", name="centring_save")
    state = Cpt(EpicsSignalRO, "State", name="state")
    phase = Cpt(EpicsSignal, "CurrentPhase", name="phase")
    phase_index = Cpt(EpicsSignalRO, "CurrentPhaseIndex", name="phase_index")
    detector_state = Cpt(EpicsSignal, "DetectorState", name="det_state")
    detector_gate_pulse_enabled = Cpt(
        EpicsSignal, "DetectorGatePulseEnabled", name="det_gate_pulse_enabled"
    )
    exporter = Cpt(
        ExporterComponent,
        address=os.environ["EXPORTER_HOST"],
        port=int(os.environ["EXPORTER_PORT"]),
        name="exporter",
    )

    task_info = Cpt(EpicsSignalRO, "LastTaskInfo", name="task_info")
    task_output = Cpt(EpicsSignalRO, "LastTaskOutput", name="task_output")

    def save_center(self):
        self.centring_save.put("__EMPTY__")

    def task_complete(self):
        return self.task_output == "true"

    def task_status(self):
        def check_task(*, old_value, value, **kwargs):
            "Return True when last task completes"
            return value[6] == "1"

        return SubscriptionStatus(self.task_info, check_task)

    def is_ready(self):
        return self.state.get() == 4

    def ready_status(self):
        # returns an ophyd status object that monitors the state pv for operations to complete
        def check_ready(*, old_value, value, **kwargs):
            "Return True when the MD2 is ready"
            return value == 4

        return SubscriptionStatus(self.state, check_ready)

    def phase_transition(self, phase):
        # returns an ophyd status object that monitors the phase pv for operations to complete
        self.phase.put(phase)

        def check_transition_state(*, old_value, value, **kwargs):
            "Return True when the MD2 is ready"
            return value == 4 and self.phase.get() == phase

        return SubscriptionStatus(self.state, check_transition_state)

    def standard_scan(
        self,
        frame_number=0,  # int: frame ID just for logging purposes.
        num_images=1,  # int: number of frames. Needed solely when the detector use gate enabled trigger.
        start_angle=0,  # double: angle (deg) at which the shutter opens and omega speed is stable.
        scan_range=0.1,  # double: omega relative move angle (deg) before closing the shutter.
        exposure_time=0.1,  # double: exposure time (sec) to control shutter command.
        num_passes=1,  # int: number of moves forward and reverse between start angle and stop angle
    ):
        command = "startScanEx2"
        if start_angle is None:
            start_angle = self.omega.get()
        return self.exporter.cmd(
            command,
            [
                frame_number,
                num_images,
                start_angle,
                scan_range,
                exposure_time,
                num_passes,
            ],
        )

    def vector_scan(
        self,
        start_angle=None,  # double: angle (deg) at which the shutter opens and omega speed is stable.
        scan_range=10,  # double: omega relative move angle (deg) before closing the shutter.
        exposure_time=1,  # double: exposure time (sec) to control shutter command.
        start_y=None,  # double: PhiY axis position at the beginning of the exposure.
        start_z=None,  # double: PhiZ axis position at the beginning of the exposure.
        start_cx=None,  # double: CentringX axis position at the beginning of the exposure.
        start_cy=None,  # double: CentringY axis position at the beginning of the exposure.
        stop_y=None,  # double: PhiY axis position at the end of the exposure.
        stop_z=None,  # double: PhiZ axis position at the end of the exposure.
        stop_cx=None,  # double: CentringX axis position at the end of the exposure.
        stop_cy=None,  # double: CentringY axis position at the end of the exposure.
    ):
        command = "startScan4DEx"
        if start_angle is None:
            start_angle = self.omega.val()
        if start_y is None:
            start_y = self.y.val()
        if start_z is None:
            start_z = self.z.val()
        if start_cx is None:
            start_cx = self.cx.val()
        if start_cy is None:
            start_cy = self.cy.val()
        if stop_y is None:
            stop_y = self.y.val()
        if stop_z is None:
            stop_z = self.z.val()
        if stop_cx is None:
            stop_cx = self.cx.val()
        if stop_cy is None:
            stop_cy = self.cy.val()

        # List of scan parameters values, comma separated. The axes start values define the beginning
        # of the exposure, that is when all the axes have a steady speed and when the shutter/detector
        # are triggered.
        # The axes stop values are for the end of detector exposure and define the position at the
        # beginning of the deceleration.
        # Inputs names: "start_angle", "scan_range", "exposure_time", "start_y", "start_z", "start_cx",
        # "start_cy", "stop_y", "stop_z", "stop_cx", "stop_cy"
        param_list = [
            start_angle,
            scan_range,
            exposure_time,
            start_y,
            start_z,
            start_cx,
            start_cy,
            stop_y,
            stop_z,
            stop_cx,
            stop_cy,
        ]
        return self.exporter.cmd(command, param_list)

    def raster_scan(
        self,
        omega_range=0,  # double: omega relative move angle (deg) before closing the shutter.
        line_range=0.1,  # double: horizontal range of the grid (mm).
        total_uturn_range=0.1,  # double: vertical range of the grid (mm).
        start_omega=None,  # double: angle (deg) at which the shutter opens and omega speed is stable.
        start_y=None,  # double: PhiY axis position at the beginning of the exposure.
        start_z=None,  # double: PhiZ axis position at the beginning of the exposure.
        start_cx=None,  # double: CentringX axis position at the beginning of the exposure.
        start_cy=None,  # double: CentringY axis position at the beginning of the exposure.
        number_of_lines=5,  # int: number of frames on the vertical range.
        frames_per_line=5,  # int: number of frames on the horizontal range.
        exposure_time=1.2,  # double: exposure time (sec) to control shutter command. +1, based on the exaples given
        invert_direction=True,  # boolean: true to enable passes in the reverse direction.
        use_centring_table=True,  # boolean: true to use the centring table to do the pitch movements.
        use_fast_mesh_scans=True,  # boolean: true to use the fast raster scan if available (power PMAC).
    ):

        command = "startRasterScanEx"
        if start_omega is None:
            start_omega = self.omega.val()
        if start_y is None:
            start_y = self.y.val()
        if start_z is None:
            start_z = self.z.val()
        if start_cx is None:
            start_cx = self.cx.val()
        if start_cy is None:
            start_cy = self.cy.val()
        # List of scan parameters values, "/t" separated. The axes start values define the beginning
        # of the exposure, that is when all the axes have a steady speed and when the shutter/detector
        # are triggered.
        # The axes stop values are for the end of detector exposure and define the position at the
        # beginning of the deceleration.
        # Inputs names: "omega_range", "line_range", "total_uturn_range", "start_omega", "start_y",
        # "start_z", "start_cx", "start_cy", "number_of_lines", "frames_per_lines", "exposure_time",
        # "invert_direction", "use_centring_table", "use_fast_mesh_scans"
        param_list = [
            omega_range,
            line_range,
            total_uturn_range,
            start_omega,
            start_y,
            start_z,
            start_cx,
            start_cy,
            number_of_lines,
            frames_per_line,
            exposure_time,
            invert_direction,
            use_centring_table,
            use_fast_mesh_scans,
        ]
        return self.exporter.cmd(command, param_list)


class MD2ApertureDevice(Device):
    # this device needs additional signals for "CurrentApertureDiameterIndex" and "ApertureDiameters"
    current_index = Cpt(
        EpicsSignal, "CurrentApertureDiameterIndex", name="current_index"
    )
    diameters = Cpt(EpicsSignalRO, "ApertureDiameters", name="diameters")

    def get_diameter_list(self):
        # must format list for GUI
        # also, can't currently get from PV
        return self.diameters.get()

    def set_diameter(self, diameter):
        if diameter in self.get_diameter_list():
            self.current_index.put(self.get_diameter_list().index(diameter))


class ShutterDevice(Device):
    control = Cpt(
        EpicsSignal, "{MD2}:FastShutterIsOpen", name="control"
    )  # PV to send control signal
    pos_opn = Cpt(EpicsSignalRO, "{Gon:1-Sht}Pos:Opn-I", name="pos_opn")
    pos_cls = Cpt(EpicsSignalRO, "{Gon:1-Sht}Pos:Cls-I", name="pos_cls")

    def is_open(self):
        return self.control.get() == 1  # self.pos_opn.get()

    def open_shutter(self):
        self.control.set(
            1
        )  # self.pos_opn.get()) iocs are down, so just setting it to 1

    def close_shutter(self):
        self.control.set(0)  # self.pos_cls.get())


class CameraDevice(Device):
    # MD2 camera has the following attributes:
    # CoaxCamScaleX
    # CoaxCamScaleY
    # CoaxialCameraZoomValue
    scale_x = Cpt(EpicsSignalRO, "CoaxCamScaleX", name="scale_x")
    scale_y = Cpt(EpicsSignalRO, "CoaxCamScaleY", name="scale_y")
    zoom = Cpt(EpicsSignal, "CoaxialCameraZoomValue", name="zoom")
