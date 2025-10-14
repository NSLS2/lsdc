print(f"Loading {__file__}")

from enum import IntEnum

from ophyd import (Device, Component as Cpt, FormattedComponent as FC,
                   Signal)
from ophyd import (EpicsSignal, EpicsSignalRO, DeviceStatus)
from ophyd.utils import set_and_wait
from bluesky.plans import fly
import pandas as pd

import uuid
import time
import datetime as dt
import os


def _get_configuration_attrs(cls, *, signal_class=Signal):
    return [sig_name for sig_name in cls.component_names
            if issubclass(getattr(cls, sig_name).cls, signal_class)]


class ZebraInputEdge(IntEnum):
    FALLING = 1
    RISING = 0


class ZebraAddresses(IntEnum):
    DISCONNECT = 0
    IN1_TTL = 1
    IN1_NIM = 2
    IN1_LVDS = 3
    IN2_TTL = 4
    IN2_NIM = 5
    IN2_LVDS = 6
    IN3_TTL = 7
    IN3_OC = 8
    IN3_LVDS = 9
    IN4_TTL = 10
    IN4_CMP = 11
    IN4_PECL = 12
    IN5_ENCA = 13
    IN5_ENCB = 14
    IN5_ENCZ = 15
    IN5_CONN = 16
    IN6_ENCA = 17
    IN6_ENCB = 18
    IN6_ENCZ = 19
    IN6_CONN = 20
    IN7_ENCA = 21
    IN7_ENCB = 22
    IN7_ENCZ = 23
    IN7_CONN = 24
    IN8_ENCA = 25
    IN8_ENCB = 26
    IN8_ENCZ = 27
    IN8_CONN = 28
    PC_ARM = 29
    PC_GATE = 30
    PC_PULSE = 31
    AND1 = 32
    AND2 = 33
    AND3 = 34
    AND4 = 35
    OR1 = 36
    OR2 = 37
    OR3 = 38
    OR4 = 39
    GATE1 = 40
    GATE2 = 41
    GATE3 = 42
    GATE4 = 43
    DIV1_OUTD = 44
    DIV2_OUTD = 45
    DIV3_OUTD = 46
    DIV4_OUTD = 47
    DIV1_OUTN = 48
    DIV2_OUTN = 49
    DIV3_OUTN = 50
    DIV4_OUTN = 51
    PULSE1 = 52
    PULSE2 = 53
    PULSE3 = 54
    PULSE4 = 55
    QUAD_OUTA = 56
    QUAD_OUTB = 57
    CLOCK_1KHZ = 58
    CLOCK_1MHZ = 59
    SOFT_IN1 = 60
    SOFT_IN2 = 61
    SOFT_IN3 = 62
    SOFT_IN4 = 63


class ZebraSignalWithRBV(EpicsSignal):
    # An EPICS signal that uses the Zebra convention of 'pvname' being the
    # setpoint and 'pvname:RBV' being the read-back

    def __init__(self, prefix, **kwargs):
        super().__init__(prefix + ':RBV', write_pv=prefix, **kwargs)


class ZebraPulse(Device):
    width = Cpt(ZebraSignalWithRBV, 'WID')
    input_addr = Cpt(ZebraSignalWithRBV, 'INP')
    input_str = Cpt(EpicsSignalRO, 'INP:STR', string=True)
    input_status = Cpt(EpicsSignalRO, 'INP:STA')
    delay = Cpt(ZebraSignalWithRBV, 'DLY')
    delay_sync = Cpt(EpicsSignal, 'DLY:SYNC')
    time_units = Cpt(ZebraSignalWithRBV, 'PRE', string=True)
    output = Cpt(EpicsSignal, 'OUT')

    input_edge = FC(EpicsSignal,
                    '{self._zebra_prefix}POLARITY:{self._edge_addr}')

    _edge_addrs = {1: 'BC',
                   2: 'BD',
                   3: 'BE',
                   4: 'BF',
                   }

    def __init__(self, prefix, *, index=None, parent=None,
                 configuration_attrs=None, read_attrs=None, **kwargs):
        if read_attrs is None:
            read_attrs = ['input_status', 'output']
        if configuration_attrs is None:
            configuration_attrs = _get_configuration_attrs(self.__class__, signal_class=ZebraSignalWithRBV) + ['input_edge']

        zebra = parent
        self.index = index
        self._zebra_prefix = zebra.prefix
        self._edge_addr = self._edge_addrs[index]

        super().__init__(prefix, configuration_attrs=configuration_attrs,
                         read_attrs=read_attrs, parent=parent, **kwargs)


class ZebraOutputBase(Device):
    '''The base of all zebra outputs (1~8)

        Front outputs
        # TTL  LVDS  NIM  PECL  OC  ENC
        1  o    o     o
        2  o    o     o
        3  o    o               o
        4  o          o    o

        Rear outputs
        # TTL  LVDS  NIM  PECL  OC  ENC
        5                            o
        6                            o
        7                            o
        8                            o

    '''
    def __init__(self, prefix, *, index=None, read_attrs=None,
                 configuration_attrs=None, **kwargs):
        self.index = index

        if read_attrs is None:
            read_attrs = []
        if configuration_attrs is None:
            configuration_attrs = _get_configuration_attrs(self.__class__)

        super().__init__(prefix, read_attrs=read_attrs,
                         configuration_attrs=configuration_attrs, **kwargs)


class ZebraOutputType(Device):
    '''Shared by all output types (ttl, lvds, nim, pecl, out)'''
    addr = Cpt(ZebraSignalWithRBV, '')
    status = Cpt(EpicsSignalRO, ':STA')
    string = Cpt(EpicsSignalRO, ':STR', string=True)
    sync = Cpt(EpicsSignal, ':SYNC')
    write_output = Cpt(EpicsSignal, ':SET')

    def __init__(self, prefix, *, read_attrs=None, configuration_attrs=None,
                 **kwargs):
        if read_attrs is None:
            read_attrs = ['status']
        if configuration_attrs is None:
            configuration_attrs = ['addr']

        super().__init__(prefix, read_attrs=read_attrs,
                         configuration_attrs=configuration_attrs, **kwargs)


class ZebraFrontOutput12(ZebraOutputBase):
    ttl = Cpt(ZebraOutputType, 'TTL')
    lvds = Cpt(ZebraOutputType, 'LVDS')
    nim = Cpt(ZebraOutputType, 'NIM')

    def __init__(self, prefix, *, read_attrs=None, configuration_attrs=None,
                 **kwargs):
        if read_attrs is None:
            read_attrs = []
        if configuration_attrs is None:
            configuration_attrs = _get_configuration_attrs(self.__class__, signal_class=ZebraOutputType)

        super().__init__(prefix, read_attrs=read_attrs,
                         configuration_attrs=configuration_attrs, **kwargs)


class ZebraFrontOutput3(ZebraOutputBase):
    ttl = Cpt(ZebraOutputType, 'TTL')
    lvds = Cpt(ZebraOutputType, 'LVDS')
    open_collector = Cpt(ZebraOutputType, 'OC')

    def __init__(self, prefix, *, read_attrs=None, configuration_attrs=None,
                 **kwargs):
        if read_attrs is None:
            read_attrs = []
        if configuration_attrs is None:
            configuration_attrs = _get_configuration_attrs(self.__class__, signal_class=ZebraOutputType)

        super().__init__(prefix, read_attrs=read_attrs,
                         configuration_attrs=configuration_attrs, **kwargs)


class ZebraFrontOutput4(ZebraOutputBase):
    ttl = Cpt(ZebraOutputType, 'TTL')
    nim = Cpt(ZebraOutputType, 'NIM')
    pecl = Cpt(ZebraOutputType, 'PECL')

    def __init__(self, prefix, *, read_attrs=None, configuration_attrs=None,
                 **kwargs):
        if read_attrs is None:
            read_attrs = []
        if configuration_attrs is None:
            configuration_attrs = _get_configuration_attrs(self.__class__, signal_class=ZebraOutputType)

        super().__init__(prefix, read_attrs=read_attrs,
                         configuration_attrs=configuration_attrs, **kwargs)


class ZebraRearOutput(ZebraOutputBase):
    enca = Cpt(ZebraOutputType, 'ENCA')
    encb = Cpt(ZebraOutputType, 'ENCB')
    encz = Cpt(ZebraOutputType, 'ENCZ')
    conn = Cpt(ZebraOutputType, 'CONN')

    def __init__(self, prefix, *, read_attrs=None, configuration_attrs=None,
                 **kwargs):
        if read_attrs is None:
            read_attrs = []
        if configuration_attrs is None:
            configuration_attrs = _get_configuration_attrs(self.__class__, signal_class=ZebraOutputType)

        super().__init__(prefix, read_attrs=read_attrs,
                         configuration_attrs=configuration_attrs, **kwargs)


class ZebraEncoder(Device):
    motor_pos = FC(EpicsSignalRO, '{self._zebra_prefix}M{self.index}:RBV')
    zebra_pos = FC(EpicsSignal, '{self._zebra_prefix}POS{self.index}_SET')
    encoder_res = FC(EpicsSignal, '{self._zebra_prefix}M{self.index}:MRES')
    encoder_off = FC(EpicsSignal, '{self._zebra_prefix}M{self.index}:OFF')
    _copy_pos_signal = FC(EpicsSignal, '{self._zebra_prefix}M{self.index}:SETPOS.PROC')

    def __init__(self, prefix, *, index=None, parent=None,
                 configuration_attrs=None, read_attrs=None, **kwargs):
        if read_attrs is None:
            read_attrs = []
        if configuration_attrs is None:
            configuration_attrs = ['encoder_res', 'encoder_off']

        self.index = index
        self._zebra_prefix = parent.prefix

        super().__init__(prefix, read_attrs=read_attrs,
                         configuration_attrs=configuration_attrs,
                         parent=parent, **kwargs)

    def copy_position(self):
        self._copy_pos_signal.put(1, wait=True)


class ZebraGateInput(Device):
    addr = Cpt(ZebraSignalWithRBV, '')
    string = Cpt(EpicsSignalRO, ':STR', string=True)
    status = Cpt(EpicsSignalRO, ':STA')
    sync = Cpt(EpicsSignal, ':SYNC')
    write_input = Cpt(EpicsSignal, ':SET')

    # Input edge index depends on the gate number (these are set in __init__)
    edge = FC(EpicsSignal,
              '{self._zebra_prefix}POLARITY:B{self._input_edge_idx}')

    def __init__(self, prefix, *, index=None, parent=None,
                 configuration_attrs=None, read_attrs=None, **kwargs):
        if read_attrs is None:
            read_attrs = ['status']
        if configuration_attrs is None:
            configuration_attrs = ['addr', 'edge']

        gate = parent
        zebra = gate.parent

        self.index = index
        self._zebra_prefix = zebra.prefix
        self._input_edge_idx = gate._input_edge_idx[self.index]

        super().__init__(prefix, read_attrs=read_attrs,
                         configuration_attrs=configuration_attrs,
                         parent=parent, **kwargs)


class ZebraGate(Device):
    input1 = Cpt(ZebraGateInput, 'INP1', index=1)
    input2 = Cpt(ZebraGateInput, 'INP2', index=2)
    output = Cpt(EpicsSignal, 'OUT')

    def __init__(self, prefix, *, index=None, read_attrs=None,
                 configuration_attrs=None, **kwargs):
        self.index = index
        self._input_edge_idx = {1: index - 1,
                                2: 4 + index - 1
                                }

        if read_attrs is None:
            read_attrs = ['output']
        if configuration_attrs is None:
            configuration_attrs = ['input1', 'input2']

        super().__init__(prefix, configuration_attrs=configuration_attrs,
                         read_attrs=read_attrs, **kwargs)

    def set_input_edges(self, edge1, edge2):
        set_and_wait(self.input1.edge, int(edge1))
        set_and_wait(self.input2.edge, int(edge2))


class ZebraPositionCaptureDeviceBase(Device):
    source = Cpt(ZebraSignalWithRBV, 'SEL', put_complete=True)
    input_addr = Cpt(ZebraSignalWithRBV, 'INP')
    input_str = Cpt(EpicsSignalRO, 'INP:STR', string=True)
    input_status = Cpt(EpicsSignalRO, 'INP:STA', auto_monitor=True)
    output = Cpt(EpicsSignalRO, 'OUT', auto_monitor=True)

    def __init__(self, prefix, *, configuration_attrs=None, read_attrs=None,
                 **kwargs):

        if read_attrs is None:
            read_attrs = []
        read_attrs += ['input_status', 'output']

        if configuration_attrs is None:
            configuration_attrs = []

        super().__init__(prefix, configuration_attrs=configuration_attrs,
                         read_attrs=read_attrs, **kwargs)


class ZebraPositionCaptureArm(ZebraPositionCaptureDeviceBase):

    class ZebraArmSignalWithRBV(EpicsSignal):
        def __init__(self, prefix, **kwargs):
            super().__init__(prefix + 'ARM_OUT', write_pv=prefix+'ARM', **kwargs)

    class ZebraDisarmSignalWithRBV(EpicsSignal):
        def __init__(self, prefix, **kwargs):
            super().__init__(prefix + 'ARM_OUT', write_pv=prefix+'DISARM', **kwargs)

    arm = FC(ZebraArmSignalWithRBV, '{self._parent_prefix}')
    disarm = FC(ZebraDisarmSignalWithRBV, '{self._parent_prefix}')

    def __init__(self, prefix, *, parent=None,
                 configuration_attrs=None, read_attrs=None, **kwargs):

        self._parent_prefix = parent.prefix

        super().__init__(prefix, read_attrs=read_attrs,
                         configuration_attrs=configuration_attrs,
                         parent=parent, **kwargs)


class ZebraPositionCaptureGate(ZebraPositionCaptureDeviceBase):
    num_gates = Cpt(EpicsSignal, 'NGATE')
    start = Cpt(EpicsSignal, 'START')
    width = Cpt(EpicsSignal, 'WID')
    step = Cpt(EpicsSignal, 'STEP')

    def __init__(self, prefix, *, configuration_attrs=None, read_attrs=None,
                 **kwargs):

        if read_attrs is None:
            read_attrs = []
        if configuration_attrs is None:
            configuration_attrs = _get_configuration_attrs(self.__class__, signal_class=EpicsSignal)

        super().__init__(prefix, configuration_attrs=configuration_attrs,
                         read_attrs=read_attrs, **kwargs)


class ZebraPositionCapturePulse(ZebraPositionCaptureDeviceBase):
    max_pulses = Cpt(EpicsSignal, 'MAX')
    start = Cpt(EpicsSignal, 'START')
    width = Cpt(EpicsSignal, 'WID')
    step = Cpt(EpicsSignal, 'STEP')
    delay = Cpt(EpicsSignal, 'DLY')

    def __init__(self, prefix, *, configuration_attrs=None, read_attrs=None,
                 **kwargs):

        if read_attrs is None:
            read_attrs = []
        if configuration_attrs is None:
            configuration_attrs = _get_configuration_attrs(self.__class__, signal_class=EpicsSignal)

        super().__init__(prefix, configuration_attrs=configuration_attrs,
                         read_attrs=read_attrs, **kwargs)


class ZebraPositionCaptureData(Device):
    num_captured = Cpt(EpicsSignalRO, 'NUM_CAP')
    num_downloaded = Cpt(EpicsSignalRO, 'NUM_DOWN')

    time = Cpt(EpicsSignalRO, 'TIME')

    enc1 = Cpt(EpicsSignalRO, 'ENC1')
    enc2 = Cpt(EpicsSignalRO, 'ENC2')
    enc3 = Cpt(EpicsSignalRO, 'ENC3')
    enc4 = Cpt(EpicsSignalRO, 'ENC4')

    sys1 = Cpt(EpicsSignalRO, 'SYS1')
    sys2 = Cpt(EpicsSignalRO, 'SYS2')

    div1 = Cpt(EpicsSignalRO, 'DIV1')
    div2 = Cpt(EpicsSignalRO, 'DIV2')
    div3 = Cpt(EpicsSignalRO, 'DIV3')
    div4 = Cpt(EpicsSignalRO, 'DIV4')

    def __init__(self, prefix, *, configuration_attrs=None, read_attrs=None,
                 **kwargs):

        if read_attrs is None:
            read_attrs = _get_configuration_attrs(self.__class__, signal_class=EpicsSignalRO)

        super().__init__(prefix, configuration_attrs=configuration_attrs,
                         read_attrs=read_attrs, **kwargs)


class ZebraPositionCapture(Device):
    source = Cpt(ZebraSignalWithRBV, 'ENC')
    direction = Cpt(ZebraSignalWithRBV, 'DIR')
    time_units = Cpt(ZebraSignalWithRBV, 'TSPRE')

    arm = Cpt(ZebraPositionCaptureArm, 'ARM_')
    gate = Cpt(ZebraPositionCaptureGate, 'GATE_')
    pulse = Cpt(ZebraPositionCapturePulse, 'PULSE_')

    capture_enc1 = Cpt(EpicsSignal, 'BIT_CAP:B0')
    capture_enc2 = Cpt(EpicsSignal, 'BIT_CAP:B1')
    capture_enc3 = Cpt(EpicsSignal, 'BIT_CAP:B2')
    capture_enc4 = Cpt(EpicsSignal, 'BIT_CAP:B3')

    capture_sys1 = Cpt(EpicsSignal, 'BIT_CAP:B4')
    capture_sys2 = Cpt(EpicsSignal, 'BIT_CAP:B5')

    capture_div1 = Cpt(EpicsSignal, 'BIT_CAP:B6')
    capture_div2 = Cpt(EpicsSignal, 'BIT_CAP:B7')
    capture_div3 = Cpt(EpicsSignal, 'BIT_CAP:B8')
    capture_div4 = Cpt(EpicsSignal, 'BIT_CAP:B9')

    data = Cpt(ZebraPositionCaptureData, '')

    def __init__(self, prefix, *, configuration_attrs=None, read_attrs=None,
                 **kwargs):

        if read_attrs is None:
            read_attrs = ['data']
        if configuration_attrs is None:
            configuration_attrs = (
                ['source', 'direction', 'time_units',
                 'arm', 'gate', 'pulse'] +
                [f'capture_enc{i}' for i in range(1,5)] +
                [f'capture_sys{i}' for i in range(1,3)] +
                [f'capture_div{i}' for i in range(1,5)]
            )

        super().__init__(prefix, configuration_attrs=configuration_attrs,
                         read_attrs=read_attrs, **kwargs)


class ZebraBase(Device):
    soft_input1 = Cpt(EpicsSignal, 'SOFT_IN:B0')
    soft_input2 = Cpt(EpicsSignal, 'SOFT_IN:B1')
    soft_input3 = Cpt(EpicsSignal, 'SOFT_IN:B2')
    soft_input4 = Cpt(EpicsSignal, 'SOFT_IN:B3')

    pulse1 = Cpt(ZebraPulse, 'PULSE1_', index=1)
    pulse2 = Cpt(ZebraPulse, 'PULSE2_', index=2)
    pulse3 = Cpt(ZebraPulse, 'PULSE3_', index=3)
    pulse4 = Cpt(ZebraPulse, 'PULSE4_', index=4)

    output1 = Cpt(ZebraFrontOutput12, 'OUT1_', index=1)
    output2 = Cpt(ZebraFrontOutput12, 'OUT2_', index=2)
    output3 = Cpt(ZebraFrontOutput3, 'OUT3_', index=3)
    output4 = Cpt(ZebraFrontOutput4, 'OUT4_', index=4)

    output5 = Cpt(ZebraRearOutput, 'OUT5_', index=5)
    output6 = Cpt(ZebraRearOutput, 'OUT6_', index=6)
    output7 = Cpt(ZebraRearOutput, 'OUT7_', index=7)
    output8 = Cpt(ZebraRearOutput, 'OUT8_', index=8)

    gate1 = Cpt(ZebraGate, 'GATE1_', index=1)
    gate2 = Cpt(ZebraGate, 'GATE2_', index=2)
    gate3 = Cpt(ZebraGate, 'GATE3_', index=3)
    gate4 = Cpt(ZebraGate, 'GATE4_', index=4)

    encoder1 = Cpt(ZebraEncoder, '', index=1)
    encoder2 = Cpt(ZebraEncoder, '', index=2)
    encoder3 = Cpt(ZebraEncoder, '', index=3)
    encoder4 = Cpt(ZebraEncoder, '', index=4)

    pos_capt = Cpt(ZebraPositionCapture, 'PC_')
    download_status = Cpt(EpicsSignalRO, 'ARRAY_ACQ')
    reset = Cpt(EpicsSignal, 'SYS_RESET.PROC')

    addresses = ZebraAddresses

    def __init__(self, prefix, *, configuration_attrs=None, read_attrs=None,
                 **kwargs):
        if read_attrs is None:
            read_attrs = []
        if configuration_attrs is None:
            configuration_attrs = (
                [f'soft_input{i}' for i in range(1,5)] +
                [f'pulse{i}' for i in range(1,5)] +
                [f'output{i}' for i in range(1,9)] +
                [f'gate{i}' for i in range(1,5)] +
                [f'encoder{i}' for i in range(1,5)] +
                ['pos_capt']
            )

        super().__init__(prefix, configuration_attrs=configuration_attrs,
                         read_attrs=read_attrs, **kwargs)

        self.pulse = dict(self._get_indexed_devices(ZebraPulse))
        self.output = dict(self._get_indexed_devices(ZebraOutputBase))
        self.gate = dict(self._get_indexed_devices(ZebraGate))
        self.encoder = dict(self._get_indexed_devices(ZebraEncoder))

    def _get_indexed_devices(self, cls):
        for attr in self._sub_devices:
            dev = getattr(self, attr)
            if isinstance(dev, cls):
                yield dev.index, dev

    def trigger(self):
        # Re-implement this to trigger as desired in bluesky
        status = DeviceStatus(self)
        status._finished()
        return status


class Zebra(ZebraBase):

    def __init__(self, prefix, *args, **kwargs):
        self._collection_ts = None
        self._disarmed_status = None
        self._dl_status = None
        super().__init__(prefix, *args, **kwargs)

    def setup(self, master, arm_source, gate_start, gate_width, gate_step, num_gates,
              direction, pulse_width, pulse_step, capt_delay, max_pulses,
              collect=[True, True, True, True]):

        # arm_source is either 0 (soft) or 1 (external)
        # direction is either 0 (positive) or 1 (negative)
        # gate_* parameters in motor units
        # pulse_*, capt_delay parameters in ms
        # collect represents which of the four encoders to collect data from

        # Sanity checks
        if master not in range(4):
            raise ValueError(f"Invalid master positioner '{master}', must be between 0 and 3")

        if arm_source not in (0, 1):
            raise ValueError('arm_source must be either 0 (soft) or 1 (external)')

        if direction not in (0, 1):
            raise ValueError('direction must be either 0 (positive) or 1 (negative)')

        if gate_width > gate_step:
            raise ValueError('gate_width must be smaller than gate_step')

        if pulse_width > pulse_step:
            raise ValueError('pulse_width must be smaller than pulse_step')

        # Reset Zebra state
        self.reset.put(1, wait=True)
        time.sleep(0.1)

        pc = self.pos_capt

        pc.arm.source.put(arm_source, wait=True)

        pc.time_units.put("ms", wait=True)
        pc.gate.source.put("Position", wait=True)
        pc.pulse.source.put("Time", wait=True)

        # Setup which encoders to capture
        for encoder, do_capture in zip((pc.capture_enc1, pc.capture_enc2, pc.capture_enc3, pc.capture_enc4), collect):
            encoder.put(int(do_capture), wait=True)

        # Configure Position Capture
        pc.source.put(master, wait=True)
        pc.direction.put(direction, wait=True)

        # Configure Position Capture Gate
        pc.gate.start.put(gate_start, wait=True)
        pc.gate.width.put(gate_width, wait=True)
        pc.gate.step.put(gate_step, wait=True)
        pc.gate.num_gates.put(num_gates, wait=True)

        # Configure Position Capture Pulses
        pc.pulse.start.put(0, wait=True)
        pc.pulse.step.put(pulse_step, wait=True)
        pc.pulse.width.put(pulse_width, wait=True)
        pc.pulse.delay.put(capt_delay, wait=True)
        pc.pulse.max_pulses.put(max_pulses, wait=True)

        # Synchronize encoders (do it last)
        for encoder in self.encoder.values():
            encoder.copy_position()

    def kickoff(self):
        armed_status = DeviceStatus(self)
        self._disarmed_status = disarmed_status = DeviceStatus(self)

        pc = self.pos_capt
        external = bool(pc.arm.source.get()) # Using external trigger?

        if external:
            armed_signal = pc.arm.input_status
        else:
            armed_signal = pc.arm.output

        disarmed_signal = self.download_status

        self._collection_ts = time.time()

        def armed_status_cb(value, old_value, obj, **kwargs):
            if int(old_value) == 0 and int(value) == 1:
                armed_status._finished()
                obj.clear_sub(armed_status_cb)

        def disarmed_status_cb(value, old_value, obj, **kwargs):
            if int(old_value) == 1 and int(value) == 0:
                disarmed_status._finished()
                obj.clear_sub(disarmed_status_cb)

        armed_signal.subscribe(armed_status_cb, run=False)
        disarmed_signal.subscribe(disarmed_status_cb, run=False)

        # Arm it if not External
        if not external:
            self.pos_capt.arm.arm.put(1)

        return armed_status

    def complete(self):
        return self._disarmed_status

    def collect(self):
        pc = self.pos_capt

        # Array of timestamps
        ts = pc.data.time.get() + self._collection_ts

        # Arrays of captured positions
        data = {
            f'enc{i}': getattr(pc.data, f'enc{i}').get()
                for i in range(1,5)
                if getattr(pc, f'capture_enc{i}').get()
        }

        for i, timestamp in enumerate(ts):
            yield {
                'data': { k: v[i] for k, v in data.items() },
                'timestamps': { k: timestamp for k in data.keys() },
                'time' : timestamp
            }

    def describe_collect(self):
        return {
            'primary': {
                f'enc{i}': {
                    'source': 'PV:' + getattr(self.pos_capt.data, f'enc{i}').pvname,
                    'shape': [],
                    'dtype': 'number'
                } for i in range(1, 5) if getattr(self.pos_capt, f'capture_enc{i}').get()
            }
        }

class ZebraMXOr(Zebra):
    or3 = Cpt(EpicsSignal, "OR3_ENA:B3")
    or3loc = Cpt(EpicsSignal, "OR3_INP4")
    armsel = Cpt(EpicsSignal, "PC_ARM_SEL")