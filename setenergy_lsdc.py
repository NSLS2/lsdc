from ophyd import (SingleTrigger, ProsilicaDetector,
                   ImagePlugin, TIFFPlugin, StatsPlugin, ROIPlugin, DetectorBase, HDF5Plugin,
                   TransformPlugin, ProcessPlugin, AreaDetector)

from ophyd import Component as Cpt
from ophyd import Device
from ophyd import EpicsSignal, EpicsSignalRO
from ophyd import EpicsMotor
from ophyd import PVPositioner, PVPositionerPC
import bluesky.plan_stubs as bps
import bluesky.plans as bp
import bluesky.preprocessors as bpp
import epics
import numpy as np
import pandas as pd
import socket
import time
import gov_lib
import daq_lib
from start_bs import db, gov_robot, govs
import logging


logger = logging.getLogger()
flux_df = None
# Machine ==========================================================

beam_current = EpicsSignal('SR:OPS-BI{DCCT:1}I:Real-I')

class InsertionDevice(Device):
    gap = Cpt(EpicsMotor, '-Ax:Gap}-Mtr',
              kind='hinted', name='')
    brake = Cpt(EpicsSignal, '}BrakesDisengaged-Sts',
                write_pv='}BrakesDisengaged-SP',
                kind='omitted', add_prefix=('read_pv', 'write_pv', 'suffix'))

    def set(self, *args, **kwargs):
        self.brake.set(1).wait(5)
        return self.gap.set(*args, **kwargs)

    def stop(self, *, success=False):
        return self.gap.stop(success=success)

ivu_gap = InsertionDevice('SR:C17-ID:G1{IVU21:2', name='ivu')

# Photon Local Feedback, sector 17 orbit angle correction onto FMX XBPM1
class PhotonLocalFeedback(Device):
    x_enable = Cpt(EpicsSignal, 'X-FdbkEnabled')
    y_enable = Cpt(EpicsSignal, 'Y-FdbkEnabled')

photon_local_feedback_c17 = PhotonLocalFeedback('SR:APHLA:LBAgent{BUMP:C17-R7X2}', name='photon_local_feedback')


# Motors ============================================================

class YMotor(Device):
    y = Cpt(EpicsMotor, '-Ax:Y}Mtr', labels=['fmx'])

class XYMotor(Device):
    x = Cpt(EpicsMotor, '-Ax:X}Mtr', labels=['fmx'])
    y = Cpt(EpicsMotor, '-Ax:Y}Mtr', labels=['fmx'])

class XYZMotor(XYMotor):
    z = Cpt(EpicsMotor, '-Ax:Z}Mtr', labels=['fmx'])

### 2DO: XZXYMotor -> XZMotor
class XZXYMotor(Device):
    x = Cpt(EpicsMotor, '-Ax:X}Mtr', labels=['fmx'])
    z = Cpt(EpicsMotor, '-Ax:Z}Mtr', labels=['fmx'])

class Slits(Device):
    b = Cpt(EpicsMotor, '-Ax:B}Mtr', labels=['fmx'])
    i = Cpt(EpicsMotor, '-Ax:I}Mtr', labels=['fmx'])
    o = Cpt(EpicsMotor, '-Ax:O}Mtr', labels=['fmx'])
    t = Cpt(EpicsMotor, '-Ax:T}Mtr', labels=['fmx'])
    x_ctr = Cpt(EpicsMotor, '-Ax:XCtr}Mtr', labels=['fmx'])
    x_gap = Cpt(EpicsMotor, '-Ax:XGap}Mtr', labels=['fmx'])
    y_ctr = Cpt(EpicsMotor, '-Ax:YCtr}Mtr', labels=['fmx'])
    y_gap = Cpt(EpicsMotor, '-Ax:YGap}Mtr', labels=['fmx'])

class DCM(Device):
    b = Cpt(EpicsMotor, '-Ax:B}Mtr', labels=['fmx'])
    g = Cpt(EpicsMotor, '-Ax:G}Mtr', labels=['fmx'])
    p = Cpt(EpicsMotor, '-Ax:P}Mtr', labels=['fmx'])
    r = Cpt(EpicsMotor, '-Ax:R}Mtr', labels=['fmx'])
    e = Cpt(EpicsMotor, '-Ax:E}Mtr', labels=['fmx'])
#    w = Cpt(EpicsMotor, '-Ax:W}Mtr', labels=['fmx'])

class XYPitchMotor(XYMotor):
    pitch = Cpt(EpicsMotor, '-Ax:P}Mtr')
    config = Cpt(EpicsSignal, '-PS}:FORMAT')
    status_monitor = Cpt(EpicsSignal, "-PS}:UNIT_STATUS_MON.A")


class KBMirror(Device):
    hp = Cpt(EpicsMotor, ':KBH-Ax:P}Mtr')
    hr = Cpt(EpicsMotor, ':KBH-Ax:R}Mtr')
    hx = Cpt(EpicsMotor, ':KBH-Ax:X}Mtr')
    hy = Cpt(EpicsMotor, ':KBH-Ax:Y}Mtr')
    vp = Cpt(EpicsMotor, ':KBV-Ax:P}Mtr')
    vx = Cpt(EpicsMotor, ':KBV-Ax:X}Mtr')
    vy = Cpt(EpicsMotor, ':KBV-Ax:Y}Mtr')
    config = Cpt(EpicsSignal, ':KB-PS}:FORMAT')
    status_monitor = Cpt(EpicsSignal, ":KB-PS}:UNIT_STATUS_MON.A")


class Cover(Device):
    close = Cpt(EpicsSignal, 'Cmd:Cls-Cmd')
    open = Cpt(EpicsSignal, 'Cmd:Opn-Cmd')
    status = Cpt(EpicsSignalRO, 'Pos-Sts') # status: 0 (Not Open), 1 (Open)

class Shutter(Device):
    close = Cpt(EpicsSignal, 'Cmd:Cls-Cmd.PROC')
    open = Cpt(EpicsSignal, 'Cmd:Opn-Cmd.PROC')
    status = Cpt(EpicsSignalRO, 'Pos-Sts') # status: 0 (Open), 1 (Closed), 2 (Undefined)
    
class GoniometerStack(Device):
	gx = Cpt(EpicsMotor, '-Ax:GX}Mtr', labels=['fmx'])
	gy = Cpt(EpicsMotor, '-Ax:GY}Mtr', labels=['fmx'])
	gz = Cpt(EpicsMotor, '-Ax:GZ}Mtr', labels=['fmx'])
	o  = Cpt(EpicsMotor, '-Ax:O}Mtr', labels=['fmx'])
	py = Cpt(EpicsMotor, '-Ax:PY}Mtr', labels=['fmx'])
	pz = Cpt(EpicsMotor, '-Ax:PZ}Mtr', labels=['fmx'])

class PitchHold(Device):
    pitch_control = Cpt(EpicsSignal, "}pitch_control")
    mono_scan_freq = Cpt(EpicsSignal, ":mono}pitch-SCAN")
    mono_max_tries = Cpt(EpicsSignal, ":mono}pitch-NUM")
    mono_deadband = Cpt(EpicsSignal, ":mono}pitch-DB")
    mono_target = Cpt(EpicsSignal, ":mono}pitch-SP") # Should be set to hdcm.p
    bragg_control = Cpt(EpicsSignal, "}bragg_control")
    bpm1_mon = Cpt(EpicsSignal, "}bpm1mon")
    set_kb_config = Cpt(EpicsSignal, "}kb_bimorph")
    set_hfm_config = Cpt(EpicsSignal, "}hfm_bimorph")

    def save_settings(self):
        self.settings = {}
        self.settings['pitch_control'] = self.pitch_control.get()
        self.settings['bragg_control'] = self.bragg_control.get()
        self.settings['bpm1_mon'] = self.bpm1_mon.get()
    
    def restore_settings(self):
        self.pitch_control.put(self.settings['pitch_control'])
        self.bragg_control.put(self.settings['bragg_control'])
        self.bpm1_mon.put(self.settings['bpm1_mon'])


step_volts = EpicsSignal("XF:17IDA-BI:FMX{Best:1}:TwkCh1.INPA")
pitch_hold = PitchHold("XF:17ID:FMX{Karen", name="pitch_hold")

## Horizontal Double Crystal Monochromator (FMX)
hdcm = DCM('XF:17IDA-OP:FMX{Mono:DCM', name='hdcm')

# Vertical Double Crystal Monochromator (AMX)
dcm_amx = DCM('XF:17IDA-OP:AMX{Mono:DCM', name='dcm_amx')


## Horizontal Focusing Mirror - XYPitchMotor
hfm = XYPitchMotor('XF:17IDA-OP:FMX{Mir:HFM', name='hfm')

## KB Mirror
kbm = KBMirror('XF:17IDC-OP:FMX{Mir', name='kbm')


## 17-ID-A FOE shutter
shutter_foe = Shutter('XF:17ID-PPS:FAMX{Sh:FE}', name='shutter_foe',
                 read_attrs=['status'])

## 17-ID-C experimental hutch shutter
shutter_hutch_c = Shutter('XF:17IDA-PPS:FMX{PSh}', name='shutter_hutch_c',
                 read_attrs=['status'])

## FMX BCU shutter
shutter_bcu = Shutter('XF:17IDC-ES:FMX{Gon:1-Sht}', name='shutter_bcu',
                 read_attrs=['status'])

## Eiger16M detector cover
cover_detector = Cover('XF:17IDC-ES:FMX{Det:FMX-Cover}', name='cover_detector',
                 read_attrs=['status'])

## Slits Motions
slits1 = Slits('XF:17IDA-OP:FMX{Slt:1', name='slits1', labels=['fmx'])

## Light
light = YMotor('XF:17IDC-ES:FMX{Light:1', name='lightY')

## Temporary: Disable motor alarm until end switch is fixed
from ophyd.utils.epics_pvs import AlarmSeverity
light.y.tolerated_alarm = AlarmSeverity.MAJOR

## Goniometer Stack
gonio = GoniometerStack('XF:17IDC-ES:FMX{Gon:1', name='gonio')

# Detectors ===================================================================================

keithley = EpicsSignalRO('XF:17IDC-BI:FMX{Keith:1}readFloat', name='keithley')

class StandardProsilica(SingleTrigger, ProsilicaDetector):
    image = Cpt(ImagePlugin, 'image1:')
    roi1 = Cpt(ROIPlugin, 'ROI1:')
    roi2 = Cpt(ROIPlugin, 'ROI2:')
    roi3 = Cpt(ROIPlugin, 'ROI3:')
    roi4 = Cpt(ROIPlugin, 'ROI4:')
    trans1 = Cpt(TransformPlugin, 'Trans1:')
    proc1 = Cpt(ProcessPlugin, 'Proc1:')
    stats1 = Cpt(StatsPlugin, 'Stats1:')
    stats2 = Cpt(StatsPlugin, 'Stats2:')
    stats3 = Cpt(StatsPlugin, 'Stats3:')
    stats4 = Cpt(StatsPlugin, 'Stats4:')
    stats5 = Cpt(StatsPlugin, 'Stats5:')
    tiff = Cpt(TIFFPlugin, 'TIFF1:')

cam_7 = StandardProsilica('XF:17IDC-ES:FMX{Cam:7}', name='cam_7')
cam_8 = StandardProsilica('XF:17IDC-ES:FMX{Cam:8}', name='cam_8')

all_standard_pros = [cam_7, cam_8]

for camera in all_standard_pros:
    camera.read_attrs = ['stats1', 'stats2', 'stats3', 'stats4', 'stats5']
    camera.stats1.read_attrs = ['total', 'centroid']
    camera.stats2.read_attrs = ['total', 'centroid']
    camera.stats3.read_attrs = ['total', 'centroid']
    camera.stats4.read_attrs = ['total', 'centroid', 'sigma_x', 'sigma_y']
    camera.stats5.read_attrs = ['total', 'centroid']
    camera.stats4.centroid.read_attrs = ['x', 'y']
    camera.tiff.read_attrs = []

# BPM =======================================================================================

class Bpm(Device):
    x = Cpt(EpicsSignalRO, 'PosX:MeanValue_RBV')
    y = Cpt(EpicsSignalRO, 'PosY:MeanValue_RBV')
    a = Cpt(EpicsSignalRO, 'Current1:MeanValue_RBV')
    b = Cpt(EpicsSignalRO, 'Current2:MeanValue_RBV')
    c = Cpt(EpicsSignalRO, 'Current3:MeanValue_RBV')
    d = Cpt(EpicsSignalRO, 'Current4:MeanValue_RBV')
    sum_x = Cpt(EpicsSignalRO, 'SumX:MeanValue_RBV')
    sum_y = Cpt(EpicsSignalRO, 'SumY:MeanValue_RBV')
    sum_all = Cpt(EpicsSignalRO, 'SumAll:MeanValue_RBV')

bpm1 = Bpm('XF:17IDA-BI:FMX{BPM:1}', name='bpm1')

bpm1.sum_all.kind = 'hinted'

bpm1_sum_all_precision = EpicsSignal('XF:17IDA-BI:FMX{BPM:1}SumAll:MeanValue_RBV.PREC')
bpm1_sum_all_precision.put(10)

class Xbpm(Device):
    x = Cpt(EpicsSignalRO, 'Pos:X-I')
    y = Cpt(EpicsSignalRO, 'Pos:Y-I')
    a = Cpt(EpicsSignalRO, 'Ampl:ACurrAvg-I')
    b = Cpt(EpicsSignalRO, 'Ampl:BCurrAvg-I')
    c = Cpt(EpicsSignalRO, 'Ampl:CCurrAvg-I')
    d = Cpt(EpicsSignalRO, 'Ampl:DCurrAvg-I')
    total = Cpt(EpicsSignalRO, 'Ampl:CurrTotal-I')

xbpm2 = Xbpm('SR:C17-BI{XBPM:2}', name='xbpm2')

# Attenuators, CRL =========================================================================

class Transmission(Device):
    energy = Cpt(EpicsSignal, 'Energy-SP') # PV only used for debugging. Attenuator uses Bragg axis energy
    transmission = Cpt(EpicsSignal, 'Trans-SP')
    set_trans = Cpt(EpicsSignal, 'Cmd:Set-Cmd.PROC')

## Dummy Attenuator - for read/write_lut() and XF:17ID-ES:FMX{Misc-LUT:atten}X-Wfm/Y-Wfm
class AttenuatorLUT(Device):
    done = Cpt(EpicsSignalRO, '}attenDone')

class AttenuatorBCU(Device):
    a1 = Cpt(EpicsMotor, '-Ax:1}Mtr', labels=['fmx'])
    a2 = Cpt(EpicsMotor, '-Ax:2}Mtr', labels=['fmx'])
    a3 = Cpt(EpicsMotor, '-Ax:3}Mtr', labels=['fmx'])
    a4 = Cpt(EpicsMotor, '-Ax:4}Mtr', labels=['fmx'])
    done = Cpt(EpicsSignalRO, '}attenDone')

## BCU Transmission
trans_bcu = Transmission('XF:17IDC-OP:FMX{Attn:BCU}', name='trans_bcu',
                         read_attrs=['transmission'])
## RI Transmission
trans_ri = Transmission('XF:17IDC-OP:FMX{Attn:RI}', name='trans_ri',
                        read_attrs=['transmission'])

## Dummy Attenuator - for read/write_lut() and XF:17ID-ES:FMX{Misc-LUT:atten}X-Wfm/Y-Wfm
atten = AttenuatorLUT('XF:17IDC-OP:FMX{Attn:BCU', name='atten',
                          read_attrs=['done'])

## BCU Attenuator
atten_bcu = AttenuatorBCU('XF:17IDC-OP:FMX{Attn:BCU', name='atten_bcu',
                          read_attrs=['done', 'a1', 'a2', 'a3', 'a4'],
                          labels=['fmx'])

# KB mirror pitch tweak voltages
vkb_piezo_tweak = EpicsSignal('XF:17IDC-BI:FMX{Best:2}:PreDAC0:OutCh1')
hkb_piezo_tweak = EpicsSignal('XF:17IDC-BI:FMX{Best:2}:PreDAC0:OutCh2')

# Utility =================================================================================

class BeamlineCalibrations(Device):
    LoMagCal = Cpt(EpicsSignal, 'LoMagCal}')
    HiMagCal = Cpt(EpicsSignal, 'HiMagCal}')

BL_calibration = BeamlineCalibrations('XF:17ID-ES:FMX{Misc-',
                                      name='BL_calibration',
                                      read_attrs=['LoMagCal', 'HiMagCal'])

def blStrGet():
    """
    Return beamline string
    
    blStr: 'AMX' or 'FMX'
    
    Beamline is determined by querying hostname
    """
    hostStr = socket.gethostname()
    if hostStr.startswith('xf17id2'):
        blStr = 'FMX'
    elif hostStr.startswith('xf17id1'):
        blStr = 'AMX'
    else: 
        print('Error - this code must be executed on one of the -ca1 machines')
        blStr = -1
        
    return blStr


# Plans to set beamline energy =======================================================================

## Helper functions for set_energy and alignment

def find_peak(det, mot, start, stop, steps):
    print(f"Scanning {mot.name} vs {det.name}...")

    uid = yield from bp.relative_scan([det], mot, start, stop, steps)

    sp = '_gap_user_setpoint' if mot is ivu_gap else '_user_setpoint'
    output = '_sum_all' if det is bpm1 else ''
    data = np.array(db[uid].table()[[det.name+output, mot.name+sp]])[1:]

    peak_idx = np.argmax(data[:, 0])
    peak_x = data[peak_idx, 1]
    peak_y = data[peak_idx, 0]

    if mot is ivu_gap:
        m = mot.gap
    else:
        m = mot
    print(f"Found peak for {m.name} at {peak_x} {m.egu} [BPM reading {peak_y}]")
    return peak_x, peak_y

## Lookup tables, Last good positions


LUT_fmt = "XF:17ID-ES:FMX{{Misc-LUT:{}}}{}-Wfm"
LGP_fmt = "XF:17ID-ES:FMX{{Misc-LGP:{}}}Pos-SP"

LUT_valid = (ivu_gap.gap, hdcm.g, hdcm.r, hdcm.p, hfm.y, hfm.x, hfm.pitch, kbm.hy, kbm.vx, atten)
LGP_valid = (kbm.hp, kbm.hx, kbm.vp, kbm.vy)

LUT_valid_names = [m.name for m in LUT_valid] + ['ivu_gap_off']
LGP_valid_names = [m.name for m in LGP_valid]

def get_energy():
    """
    Returns the current photon energy in eV derived from the DCM Bragg angle
    """ 
    
    blStr = blStrGet()
    if blStr == -1: return -1
    
    if blStr == 'AMX':
        energy = dcm_amx.e.user_readback.get()
    elif blStr == 'FMX':
        energy = hdcm.e.user_readback.get()
    
    return energy

def read_lut(name):
    """
    Reads the LookUp table values for a specific motor
    """
    if name not in LUT_valid_names:
        raise ValueError('name must be one of {}'.format(LUT_valid_names))

    x, y = [epics.caget(LUT_fmt.format(name, axis)) for axis in 'XY']
    return pd.DataFrame({'Energy':x, 'Position': y})


def write_lut(name, energy, position):
    """
    Writes to the LookUp table for a specific motor
    """
    if name not in LUT_valid_names:
        raise ValueError('name must be one of {}'.format(LUT_valid_names))

    if len(energy) != len(position):
        raise ValueError('energy and position must have the same number of points')

    epics.caput(LUT_fmt.format(name, 'X'), energy)
    epics.caput(LUT_fmt.format(name, 'Y'), position)


def read_lgp(name):
    """
    Reads the Last Good Position value for a specific motor
    """
    if name not in LGP_valid_names:
        raise ValueError('name must be one of {}'.format(LGP_valid_names))

    return epics.caget(LGP_fmt.format(name))

def write_lgp(name, position):
    """
    Writes to the Last Good Position value for a specific motor
    """
    if name not in LGP_valid_names:
        raise ValueError('name must be one of {}'.format(LGP_valid_names))

    return epics.caput(LGP_fmt.format(name), position)


    
def setE_motors_FMX(energy):
    """
    Sets undulator, hdcm, HFM and KB settings for a certain energy from a lookup table

    energy: Photon energy [eV]

    Lookup tables and variables are set in a settings notebook:
    settings/set_energy setup FMX.ipynb

    Examples:
    setE_motors_FMX(12660)
    """
    
    # (FMX specific)
    LUT = {m: [epics.caget(LUT_fmt.format(m.name, axis))
           for axis in 'XY']
           for m in (ivu_gap.gap, hdcm.g, hdcm.r, hdcm.p, hfm.y, hfm.x, hfm.pitch, kbm.hy, kbm.vx)}

    LUT_offset = [epics.caget(LUT_fmt.format('ivu_gap_off', axis)) for axis in 'XY']

    LGP = {m: epics.caget(LGP_fmt.format(m.name))
           for m in (kbm.hp, kbm.hx, kbm.vp, kbm.vy)}

    prev_hfm_config  = hfm.config.get()
    prev_kb_config = kbm.config.get()

    label = "highE"
    # Remove CRLs if going to energy < 9 keV (FMX specific)
    if energy < 10000:
        # set_beamsize('V0','H0')
        label = "lowE"
    
    if prev_hfm_config != f"HFM_{label}":
        yield from bps.abs_set(hfm.config, f"HFM_{label}")
        yield from bps.abs_set(pitch_hold.set_hfm_config, 1, wait=True)
    
    if prev_kb_config != f"KB_{label}":
        yield from bps.abs_set(kbm.config, f"KB_{label}")
        yield from bps.abs_set(pitch_hold.set_kb_config, 1, wait=True)
    
    logger.info("Waiting for 60 seconds for ramping")
    time.sleep(60)

    #while int(kbm.status_monitor.get()) & 2 ** 30 != 1 and int(hfm.status_monitor.get()) & 2 ** 30 != 1:
    #    logger.info("Waiting for ramping to complete... ")
    #    time.sleep(1)
        

    
    # Lookup Table
    def lut(motor):
        if motor is ivu_gap:
            return motor, np.interp(energy, *LUT[motor.gap])
        else:
            return motor, np.interp(energy, *LUT[motor])
    
    # Last Good Position
    def lgp(motor):
        return motor, LGP[motor]
    
    # (FMX specific)
    yield from bps.mv(
        *lut(ivu_gap),   # Set IVU Gap interpolated position
        hdcm.e, energy,  # Set Bragg Energy pseudomotor
        *lut(hdcm.g),    # Set DCM Gap interpolated position
        *lut(hdcm.r),    # Set DCM Roll interpolated position # MF 20180331
        *lut(hdcm.p),    # Set Pitch interpolated position

        # Set HFM from interpolated positions
        *lut(hfm.x),
        *lut(hfm.y),
        *lut(hfm.pitch),

        # Set KB from interpolated positions
        *lut(kbm.vx),
        *lut(kbm.hy),

        # Set KB from known good setpoints
        *lgp(kbm.vy), *lgp(kbm.vp),
        *lgp(kbm.hx), *lgp(kbm.hp)
    )    
    
    
def dcm_rock(dcm_p_range=0.03, dcm_p_points=51, logging=True, altDetector=False):
    """
    Scan DCM crystal 2 pitch to maximize flux on BPM1
    dcm_rock() runs both with the AMX DCM_AMX and the FMX hdcm

    Parameters
    ----------
    
    Optional arguments:
    dcm_p_range: DCM rocking curve range [mrad]. Default 0.03 mrad
    dcm_p_points: DCM rocking curve points. Default 51
    altDetector: If True, uses alternate detector, BPM1 at AMX and Keithley at FMX

    Examples
    --------
    
    RE(dcm_rock())
    RE(dcm_rock(altDetector = True))
    RE(dcm_rock(dcm_p_range=0.035, dcm_p_points=71))
    """
    blStr = blStrGet()
    if blStr == -1: return -1
    
    if blStr == 'AMX':
        rock_mot = dcm_amx.p
        rock_det = bpm1 if altDetector is True else keithley
    elif blStr == 'FMX':
        rock_mot = hdcm.p
        rock_det = keithley if altDetector is True else bpm1
    
    energy = get_energy()
        
    LUT = {m: [epics.caget(LUT_fmt.format(m.name, axis))
           for axis in 'XY']
           for m in (rock_mot, )}

    # Lookup Table
    def lut(motor):
        return motor, np.interp(energy, *LUT[motor])

    yield from bps.mv(
        *lut(rock_mot)    # Set Pitch interpolated position
    )

    # Decorate find_peaks to play along with our plot and plot the peak location
    def find_peak_inner(detector, motor, start, stop, num):
        if detector == bpm1:
            det_name = detector.name+'_sum_all'
        else:
            det_name = detector.name
        mot_name = motor.name+'_user_setpoint'
        
        # 2DO: Comment out when used within LSDC
        def inner():
            peak_x, peak_y = yield from find_peak(detector, motor, start, stop, num)
            return peak_x, peak_y
        return inner()

    # Scan DCM Pitch
    peak_x, peak_y = yield from find_peak_inner(rock_det, rock_mot, -dcm_p_range, dcm_p_range, dcm_p_points)
    yield from bps.mv(rock_mot, peak_x)
    
    # (FMX specific)
    if logging:
        print('Energy = {:.1f} eV'.format(energy))       
        print('hdcm cr2 pitch = {:.3f} mrad'.format(rock_mot.user_readback.get()))
        if rock_det == bpm1:
            print('BPM1 sum = {:.4g} A'.format(bpm1.sum_all.get()))
        elif  rock_det == keithley:
            time.sleep(2.0)  # Range switching is slow
            print('Keithley current = {:.4g} A'.format(keithley.get()))
        
    

    
def ivu_gap_scan(start, end, steps, detector=bpm1, goToPeak=True):
    """
    Scans the IVU21 gap against a detector, and moves the gap to the peak plus a
    energy dependent look-up table set offset

    Parameters
    ----------
    
    start: float
        The starting position (um) of the VU21 undulator gap scan
    
    end: float
        The end position (um) of the VU21 undulator gap scan
        
    steps: int
        Number of steps in the scan
    
    detector: ophyd detector
        The ophyd detector for the scan. Default is bpm1. Only setup up for the quad BPMs right now
    
    goToPeak: boolean
        If True, go to the peak plus energy-tabulated offset. If False, go back to pre-scan value.
    
    Examples
    --------
    
    RE(ivu_gap_scan(7350, 7600, 70))
    RE(ivu_gap_scan(7350, 7600, 70, goToPeak=False))
    RE(ivu_gap_scan(7350, 7600, 70, detector=bpm1))
    """
        
    energy = get_energy()
    
    motor=ivu_gap
    if start-1 < motor.gap.low_limit:
        start = motor.gap.low_limit + 1
        print('start violates lowest limit, set to %.1f' % start + ' um')
    
    LUT_offset = [epics.caget(LUT_fmt.format('ivu_gap_off', axis)) for axis in 'XY']
    
    # Decorate find_peaks to play along with our plot and plot the peak location
    def find_peak_inner(detector, motor, start, stop, num):
        det_name = detector.name+'_sum_all'
        mot_name = motor.gap.name+'_user_setpoint' if motor is ivu_gap else motor.name+'_user_setpoint'

        # Prevent going below the lower limit or above the high limit
        if motor is ivu_gap:
            step_size = (stop - start) / (num - 1)
            while motor.gap.user_setpoint.get() + start < motor.gap.low_limit:
                start += 5*step_size
                stop += 5*step_size

            while motor.gap.user_setpoint.get() + stop > motor.gap.high_limit:
                start -= 5*step_size
                stop -= 5*step_size

        # 2DO: Comment out when used within LSDC
        def inner():
            peak_x, peak_y = yield from find_peak(detector, motor, start, stop, num)
            return peak_x, peak_y
        return inner()
    
    # Remember pre-scan value
    gapPreStart=motor.gap.user_readback.get()
    
    # Move to start
    yield from bps.mv(motor, start)
    
    # Scan IVU Gap
    peak_x, peak_y = yield from find_peak_inner(detector, ivu_gap, 0, (end-start), steps)
    
    # Go to peak
    if goToPeak==True:
        peakoffset_x = (peak_x + np.interp(energy, *LUT_offset))
        yield from bps.mv(ivu_gap, peakoffset_x)
        print('Gap set to peak + tabulated offset: %.1f' % peakoffset_x + ' um')
    else:
        yield from bps.mv(ivu_gap, gapPreStart)
        print('Gap set to pre-scan value: %.1f' % gapPreStart + ' um')
    
    
def setELsdc(energy,
             dcm_p_range=0.03, dcm_p_points=51, altDetector=False,
             ivuGapStartOff=70, ivuGapEndOff=70, ivuGapSteps=31,
             transSet='All', beamCenterAlign=True, slit1Set=True):
    """
    Automated photon energy change. Master function calling four subroutines:
    * setE_motors_FMX():    Set photon delivery system motor positions for a chosen energy
    * dcm_rock():           Go to peak of monochromator rocking curve
    * ivu_gap_scan():       Go to peak of undulator gap
    * beam_center_align():  Set LSDC crosshair to beam center
                            Move rotation axis to beam heightS
                            Set governor Gonio Y Work position
    
    Requirements
    ------------
    Governor in state SA
    FOE and hutch photon shutter open
    
    
    Parameters
    ----------
    
    energy: Photon energy [eV]
    
    dcm_p_range: Scan range of DCM Crystal 2 Pitch [mrad], default = 0.03
    dcm_p_points: Number of scan points of SCM rocking curve, default = 51
    altDetector: Rocking curve to use alternate detector between BPM1 and endstation diode, default = False
    
    ivuGapStartOff: IVU gap scan start offset from tabulated position [um], default = 70
    ivuGapEndOff: IVU gap scan end offset from tabulated position [um], default = 70
    ivuGapSteps: IVU gap scan steps, default = 31
    
    transSet: FMX only: Set to 'RI' if there is a problem with the BCU attenuator.
              FMX only: Set to 'BCU' if there is a problem with the RI attenuator.
              Set to 'None' if there are problems with all = attenuators.
              Operator then has to choose a flux by hand that will not saturate scinti
              default = 'All'
    
    beamCenterAlign: Set to False to skip beam_center_align() step (like the old set_energy() routine)
                     Default True
    
    slit1Set: Set to False to skip setting Slit 1 Gap values
                     Default True
    
    Examples
    --------
    
    RE(setE(7110))
    RE(setE(10000, transSet='None'))
    RE(setE(12660, transSet='RI'))
    RE(setE(20000, ivuGapStartOff=100, ivuGapEndOff=150, ivuGapSteps=91))
    RE(setE(9000, beamCenterAlign=False))
    RE(setE(12660, beamCenterAlign=False, slit1Set=False))
    """

    desired_states  = ("SA", "AB")
    if not gov_robot.state.get() in desired_states:
        print(f'Governor state not in one of {desired_states}, exiting')
        return -1

    # Store initial Slit 1 gap positions
    if slit1Set:
        slits1XGapOrg = slits1.x_gap.user_readback.get()
        slits1YGapOrg = slits1.y_gap.user_readback.get()
    
    yield from deactivate_pitch_hold()

    print('Setting FMX motor positions')
    try:
        yield from setE_motors_FMX(energy)
    except:
        print('setE_motors_FMX() failed')
        raise
    else:
        print('setE_motors_FMX() successful')
        time.sleep(1)
    
    # Check for pre-conditions for dcm_rock() and ivu_gap_scan()
    if shutter_foe.status.get():
        print('FOE shutter closed. Has to be open for this to work. Exiting')
        return -1
        
    # DCM rocking curve
    print('Rocking monochromator')
    yield from dcm_rock(dcm_p_range=dcm_p_range, dcm_p_points=dcm_p_points, altDetector=altDetector)
    time.sleep(1)
    
    # Undulator gap scan
    print('Scanning undulator gap')
    start = ivu_gap.gap.user_readback.get() - ivuGapStartOff
    end = ivu_gap.gap.user_readback.get() + ivuGapEndOff
    try:
        yield from ivu_gap_scan(start, end, ivuGapSteps, goToPeak=True)
    except:
        print('ivu_gap_scan() failed')
        raise
    else:
        print('ivu_gap_scan() successful')
        time.sleep(1)
    

    # Hold pitch
    yield from activate_pitch_hold()
    
    # Align LSDC microscope center to beam center
    if beamCenterAlign:
        # Check for pre-conditions for beam_center_align()
        if shutter_hutch_c.status.get():
            message = 'Experiment hutch shutter closed. Has to be open for this to work. Stopping'
            logging.error(message)
            daq_lib.gui_message(message)
            return -1
        
        print('Aligning beam center')
        yield from beam_center_align(transSet=transSet)
    
    # Restore initial Slit 1 gap positions
    if slit1Set:
        yield from bps.mv(slits1.x_gap, slits1XGapOrg)  # Move Slit 1 X to original position
        yield from bps.mv(slits1.y_gap, slits1YGapOrg)  # Move Slit 1 Y to original position

    yield from fmx_reference(transSet=transSet)
    daq_lib.gui_message(f"Set energy to {energy} complete")
    

# Alignment ===========================================================================================

## Plans to align beam and goniometer for LSDC

def centroid_avg(stats):
    """
    Read centroid X and Y 10x and return mean of centroids.
    
    stats : stats method of ophyd camera object to use, e.g. cam_8.stats4
    
    Examples
    --------
    centroid_avg(cam_8.stats4)
    centroidY = centroid_avg(cam_8.stats4)[1]
    """
    
    centroidXArr = np.zeros(10)
    centroidYArr = np.zeros(10)
    for i in range(0, 10):
        centroidXArr[i] = stats.centroid.x.get()
        centroidYArr[i] = stats.centroid.y.get()
        # print('Centroid X = {:.6g} px'.format(centroidXArr[i]), ', Centroid Y = {:.6g} px'.format(centroidYArr[i]))
        time.sleep(0.2)
    CentroidX = centroidXArr.mean()
    CentroidY = centroidYArr.mean()
    print('Mean centroid X = {:.6g} px'.format(CentroidX))
    print('Mean centroid Y = {:.6g} px'.format(CentroidY))

    return CentroidX, CentroidY


def detectorCoverClose():
    """
    Closes the Detector Cover
    """
    yield from bps.mv(cover_detector.close, 1)
    
    while cover_detector.status.get() == 1:
        #print(cover_detector.status.get())
        time.sleep(0.5)
    
    return

def detectorCoverOpen():
    """
    Opens the Detector Cover
    """
    yield from bps.mv(cover_detector.open, 1)
    
    while cover_detector.status.get() != 1:
        #print(cover_detector.status.get())
        time.sleep(0.5)
    
    return


def trans_set(transmission, trans = trans_bcu):
    """
    Sets the Attenuator transmission
    """
    
    e_dcm = get_energy()
    if e_dcm < 5000 or e_dcm > 30000:
        print('Monochromator energy out of range. Must be within 5000 - 30000 eV. Exiting.')
        return
    
    yield from bps.mv(trans.energy, e_dcm) # This energy PV is only used for debugging
    yield from bps.mv(trans.transmission, transmission)
    yield from bps.mv(trans.set_trans, 1)
    
    if trans == trans_bcu:
        while atten_bcu.done.get() != 1:
            time.sleep(0.5)
    
    print('Attenuator = ' + trans.name + ', Transmission set to %.3f' % trans.transmission.get())
    return


def trans_get(trans = trans_bcu):
    """
    Returns the Attenuator transmission
    """
    
    transmission = trans.transmission.get()
    
    print('Attenuator = ' + trans.name + ', Transmission = %.3f' % transmission)
    return transmission


def transDefaultGet(energy):
    """
    Returns the default transmission to avoid saturation of the scintillator
    
    energy: X-ray energy [eV]
    
    The look up table is set in settings/set_energy setup FMX.ipynb
    """
    
    # This reads from:
    # XF:17ID-ES:FMX{Misc-LUT:atten}X-Wfm
    # XF:17ID-ES:FMX{Misc-LUT:atten}Y-Wfm
    # 
    # atten is a dummy motor just for this purpose.
    # To be replaced by trans_bcu and corresponding new PVs
    
    transLUT = read_lut('atten')
    transDefault = np.interp(energy,transLUT['Energy'],transLUT['Position'])
    
    return transDefault
    
    
# Beam align functions

def beam_center_align(transSet='All'):
    """
    Corrects alignment of goniometer and LSDC center point after a beam drift
    
    Requirements
    ------------
    * No sample mounted. Goniometer will be moved inboard out of sample position
    * Governor in SA state
    
    Parameters
    ----------
    transSet: FMX only: Set to 'RI' if there is a problem with the BCU attenuator.
              FMX only: Set to 'BCU' if there is a problem with the RI attenuator.
              Set to 'None' if there are problems with all attenuators.
              Operator then has to choose a flux by hand that will not saturate scinti
              default = 'All'
              
    Examples
    --------
    RE(beam_center_align())
    RE(beam_center_align(transSet='None'))
    RE(beam_center_align(transSet='RI'))
    """
    # TODO:
    #  * Consider running with BCU attenuators only
    #  * Check for Vis screen actuators out
    #  * Check for C-hutch shutter open
    #  * Check for ROI2 exceeding camera border.
    #    Check how this affects the ROI centering move, and whether we can correct for that
    
    # Which beamline?
    blStr = blStrGet()
    if blStr == -1: return -1

    if blStr == 'FMX':
        if transSet not in ['All', 'None', 'BCU', 'RI']:
            print('transSet must be one of: All, None, BCU, RI')
            return -1
    else:
        if transSet not in ['All', 'None']:
            print('transSet must be one of: All, None')
            return -1
       
    desired_states = ("SA", "AB")
    if not gov_robot.state.get() in desired_states:
        print(f'Governor state not in one of {desired_states}, exiting.')
        return -1
    
    # Check for beam after DCM: BPM1 total current
    if bpm1.sum_all.get() < 1e-7:
        print('Intensity after DCM low. BPM1 total current <1e-7 A.',
              'Check FOE shutter, and rocking curve, then repeat.',
              'Exiting.')
        return -1
        
    print('Closing detector cover')
    detectorCoverClose()
    
    # Transition to Governor state AB (Auto-align Beam)
    gov_lib.setGovRobot(gov_robot, 'AB')
    
    # Set beam transmission that avoids scintillator saturation
    # Default values are defined in settings as lookup table
    if transSet != 'None':
        transDefault = transDefaultGet( get_energy() )
        if blStr == 'FMX':
            if transSet in ['All', 'BCU']:
                transOrgBCU = trans_get(trans=trans_bcu)
            if transSet in ['All', 'RI']:
                transOrgRI = trans_get(trans=trans_ri)
                yield from trans_set(transDefault, trans=trans_ri)
            if transSet == 'BCU':
                yield from trans_set(transDefault, trans=trans_bcu)
            if transSet == 'All':
                yield from trans_set(1, trans=trans_bcu)
        else:
            transOrgBCU = trans_get(trans=trans_bcu)
            yield from trans_set(transDefault, trans=trans_bcu)
            
    # Retract backlight
    yield from bps.mv(light.y,govs.gov.Robot.dev.li.target_Out.get())
    print('Light Y Out')
    
    # TODO: use "yield from bps.mv(...)" instead of .put(...) below.

    # ROI1 centroid plugin does not work
    # Copy ROI1 geometry to ROI4 and use ROI4 centroid plugin
    cam_8.roi4.min_xyz.min_x.put(cam_8.roi1.min_xyz.min_x.get())
    cam_8.roi4.min_xyz.min_y.put(cam_8.roi1.min_xyz.min_y.get())
    cam_8.roi4.size.x.put(cam_8.roi1.size.x.get())
    cam_8.roi4.size.y.put(cam_8.roi1.size.y.get())
    
    yield from bps.mv(shutter_bcu.open, 1)
    print('BCU Shutter Open')
    time.sleep(1)
    
    # Check for focused beam on scinti. Do nothing if stats 4 max intensity < 20 counts
    # TODO: Verify 20 counts threshold for more settings
    if cam_8.stats4.max_value.get() < 20:
        print('Max intensity < 20 counts.',
              'Check beam intensity and focus on scinti, then repeat.',
              'No changes made.')
    else:
        # Camera calibration [um/px]
        hiMagCal = BL_calibration.HiMagCal.get()
        loMagCal = BL_calibration.LoMagCal.get()
        
        # Read centroids
        beamHiMagCentroid = centroid_avg(cam_8.stats4)
        beamHiMagCentroidX = beamHiMagCentroid[0]
        beamHiMagCentroidY = beamHiMagCentroid[1]
        time.sleep(1)
        
        # Get beam shift on Hi Mag
        # Assume the LSDC centering crosshair is in the center of the FOV
        # This works as long as cam_8 ROI1 does not hit the edge of the cam_8 image
        beamHiMagDiffX = beamHiMagCentroidX - (cam_8.roi4.size.x.get()/2)
        beamHiMagDiffY = beamHiMagCentroidY - (cam_8.roi4.size.y.get()/2)
        
        # Do nothing if we see a too large shift
        if beamHiMagDiffX>100 or beamHiMagDiffY>100:
            print('Beam centroid change > 100 px detected.',
                  'No changes made. Manual beam center correction needed.')
            beamHiMagDiffX=0
            beamHiMagDiffY=0
        
        
        # Correct Mag 4 (cam_8 ROI1)
        # Adjust cam_8 ROI1 min_y, LSDC uses this for the Mag4 FOV.
        cam_8.roi1.min_xyz.min_x.put(cam_8.roi1.min_xyz.min_x.get() + beamHiMagDiffX)
        cam_8.roi1.min_xyz.min_y.put(cam_8.roi1.min_xyz.min_y.get() + beamHiMagDiffY)
        
        # Correct Mag 3 (cam_8 ROI2)
        # This works as long as cam_8 ROI2 does not hit the edge of the cam_8 image
        cam_8.roi2.min_xyz.min_x.put(cam_8.roi2.min_xyz.min_x.get() + beamHiMagDiffX)
        cam_8.roi2.min_xyz.min_y.put(cam_8.roi2.min_xyz.min_y.get() + beamHiMagDiffY)
        
        # Get beam shift on Lo Mag from Hi Mag shift and calibration factor ratio
        beamLoMagDiffX = beamHiMagDiffX * hiMagCal/loMagCal
        beamLoMagDiffY = beamHiMagDiffY * hiMagCal/loMagCal
        
        # Correct Mag 1 (cam_7 ROI2)
        cam_7.roi2.min_xyz.min_x.put(cam_7.roi2.min_xyz.min_x.get() + beamLoMagDiffX)
        cam_7.roi2.min_xyz.min_y.put(cam_7.roi2.min_xyz.min_y.get() + beamLoMagDiffY)
        
        # Correct Mag 2 (cam_7 ROI3)
        cam_7.roi3.min_xyz.min_x.put(cam_7.roi3.min_xyz.min_x.get() + beamLoMagDiffX)
        cam_7.roi3.min_xyz.min_y.put(cam_7.roi3.min_xyz.min_y.get() + beamLoMagDiffY)
        
        time.sleep(3)
        
        # Adjust Gonio Y so rotation axis is again aligned to beam
        gonioYDiff = beamHiMagDiffY * hiMagCal
        posGyOld = govs.gov.Robot.dev.gy.target_Work.get()
        posGyNew = posGyOld + gonioYDiff
        yield from bps.mv(gonio.gy, posGyNew)   # Move Gonio Y to new position
        govs.gov.Robot.dev.gy.target_Work.set(posGyNew) # Set Governor Gonio Y Work position to new value
        print('Gonio Y difference = %.3f' % gonioYDiff)
            
    yield from bps.mv(shutter_bcu.close, 1)
    print('BCU Shutter Closed')
    
    # Transition to Governor state SA (Sample Alignment)
    gov_lib.setGovRobot(gov_robot, 'SA')
    
    # Set previous beam transmission
    if transSet != 'None':
        if blStr == 'FMX':
            if transSet in ['All', 'RI']:
                yield from trans_set(transOrgRI, trans=trans_ri)
            if transSet in ['All', 'BCU']:
                yield from trans_set(transOrgBCU, trans=trans_bcu)
        else:
            yield from trans_set(transOrgBCU, trans=trans_bcu)

def get_fluxKeithley():
    """
    Returns Keithley diode current derived flux.
    """
    
    keithFlux = epics.caget('XF:17IDA-OP:FMX{Mono:DCM-dflux}')
    
    return keithFlux


def set_fluxBeam(flux):
    """
    Sets the flux reference field.
    
    flux: Beamline flux at sample position for transmisison T = 1.  [ph/s]
    """
    
    error = epics.caput('XF:17IDA-OP:FMX{Mono:DCM-dflux-M}', flux)
    
    return error


def slit1_flux_reference(flux_df,slit1Gap):
    """
    Sets Slit 1 X gap and Slit 1 Y gap to a specified position,
    and returns flux reference values to a provided pandas DataFrame.
    
    Supporting function for fmx_flux_reference()
    
    Parameters
    ----------
    
    slit1Gap: float
        Gap value for Slit 1 X and Y [um]
    
    flux_df: pandas DataFrame with fields:
        Slit 1 X gap [um]
        Slit 1 Y gap [um]
        Keithley current [A]
        Keithley flux [ph/s]
        BPM1 sum [A]
        BPM4 sum [A]
        
    """
    yield from bps.mv(slits1.x_gap, slit1Gap, slits1.y_gap, slit1Gap, wait=True)
    time.sleep(2.0) # wait so the slits are definitely done moving and the Keithley reading is stable
    
    flux_df.at[slit1Gap, 'Slit 1 X gap [um]'] = slit1Gap
    flux_df.at[slit1Gap, 'Slit 1 Y gap [um]'] = slit1Gap
    flux_df.at[slit1Gap, 'Keithley current [A]'] = keithley.get()
    flux_df.at[slit1Gap, 'Keithley flux [ph/s]'] = get_fluxKeithley()
    flux_df.at[slit1Gap, 'BPM1 sum [A]'] = bpm1.sum_all.get()
    # TEMP FIX: flux_df.at[slit1Gap, 'BPM4 sum [A]'] = bpm4.sum_all.get()
    flux_df.at[slit1Gap, 'BPM4 sum [A]'] = 0

def fmx_flux_reference(slit1GapList = [2000, 1000, 600, 400], slit1GapDefault = 1000, transSet='All'):
    """
    Sets Slit 1 X gap and Slit 1 Y gap to a list of settings,
    and returns flux reference values in a pandas DataFrame.
    
    Parameters
    ----------
    
    slit1GapList: float (default=[2000, 1000, 600, 400])
        A list of gap values [um] for Slit 1 X and Y
    slit1GapDefault: Gap value [um] to set as default after getting references
        Default slit1GapDefault = 1000
    
    Returns
    -------
    
    flux_df: pandas DataFrame with fields
        Slit 1 X gap [um]
        Slit 1 Y gap [um]
        Keithley current [A]
        Keithley flux [ph/s]
        BPM1 sum [A]
        BPM4 sum [A]
        
    Examples
    --------
    fmx_flux_reference()
    flux_df=fmx_flux_reference()
    flux_df
    fmx_flux_reference(slit1GapList = [2000, 1500, 1000])
    fmx_flux_reference(slit1GapList = [2000, 1500, 1000], slit1GapDefault = 600)
        
    """
    
    # Store current transmission, then set full transmission
    if transSet != 'None':
        if transSet in ['All', 'BCU']:
            transOrgBCU = trans_get(trans=trans_bcu)
        if transSet in ['All', 'RI']:
            transOrgRI = trans_get(trans=trans_ri)
            yield from trans_set(1.0, trans=trans_ri)
        if transSet == 'BCU':
            yield from trans_set(1.0, trans=trans_bcu)
        if transSet == 'All':
            yield from trans_set(1.0, trans=trans_bcu)
            
    msgStr = "Energy = " + "%.1f" % get_energy() + " eV"
    print(msgStr)
    logger.info(msgStr)
    
    global flux_df
    flux_df = pd.DataFrame(columns=['Slit 1 X gap [um]',
                                    'Slit 1 Y gap [um]',
                                    'Keithley current [A]',
                                    'Keithley flux [ph/s]',
                                    'BPM1 sum [A]',
                                    'BPM4 sum [A]',
                                   ])
    
    # Put in diode
    yield from bps.mv(light.y,
                      govs.gov.Robot.dev.li.target_Diode.get())
    

    # Open BCU shutter
    yield from bps.mv(shutter_bcu.open, 1)
    time.sleep(1)
    
    for slit1Gap in slit1GapList:
        yield from slit1_flux_reference(flux_df,slit1Gap)
    
    # Move back to default slit width
    # TODO: save reference before and return to 
    yield from bps.mv(slits1.x_gap, slit1GapDefault, slits1.y_gap, slit1GapDefault, wait=True)
    time.sleep(2.0) # wait so the slits are definitely done moving and the Keithley reading is stable

    vFlux = get_fluxKeithley()
    set_fluxBeam(vFlux)
    msgStr = "Reference flux for Slit 1 gap = " + "%d" % slit1GapDefault + " um for T=1 set to " + "%.1e" % vFlux + " ph/s"
    print(msgStr)
    logger.info(msgStr)
    
   
    # Close shutter
    yield from bps.mv(shutter_bcu.close, 1)
    
    # Retract diode
    yield from bps.mv(light.y,
                      govs.gov.Robot.dev.li.target_In.get())

    # Set previous beam transmission
    if transSet != 'None':
        if transSet in ['All', 'RI']:
            yield from trans_set(transOrgRI, trans=trans_ri)
        if transSet in ['All', 'BCU']:
            yield from trans_set(transOrgBCU, trans=trans_bcu)


def deactivate_pitch_hold():
    pitch_hold.save_settings()
    yield from bps.abs_set(pitch_hold.bragg_control, 0, wait=True)
    yield from bps.abs_set(pitch_hold.bpm1_mon, 0, wait=True)
    yield from bps.abs_set(pitch_hold.pitch_control, 0, wait=True)

def activate_pitch_hold():
    yield from bps.abs_set(step_volts, "0.01", wait=True)
    yield from bps.abs_set(pitch_hold.mono_scan_freq, 1, wait=True)
    yield from bps.abs_set(pitch_hold.mono_max_tries, 100, wait=True)
    yield from bps.abs_set(pitch_hold.mono_deadband, 0.0003, wait=True)
    yield from bps.abs_set(pitch_hold.mono_target, hdcm.p.user_readback.get(), wait=True)

    # Reactivate pitch control
    pitch_hold.restore_settings()

def fmx_reference(slit1GapDefault = 1000, transSet='All'):
    """
    Calls fmx_flux_reference, then fmx_beamline_reference.
    setE will do the same after the beam alignment.
   
    Parameters
    ----------
    transSet: FMX only: Set to 'RI' if there is a problem with the BCU attenuator.
              FMX only: Set to 'BCU' if there is a problem with the RI attenuator.
              Set to 'None' if there are problems with all attenuators.
              Operator then has to choose a flux by hand that will not saturate scinti
              default = 'All'
              
    Examples
    --------
    fmx_reference()
        
    """
    if not gov_robot.state.get() == "SA":
        print('Not in Governor state SA, exiting')
        return
    
    # Transition to Governor state BL
    gov_lib.setGovRobot(gov_robot, 'BL')
    
    yield from fmx_flux_reference(slit1GapDefault = slit1GapDefault, transSet = transSet)
    
    # Transition to Governor state SA
    gov_lib.setGovRobot(gov_robot, 'SA')
    
    log_fmx_beamline_reference()
    


def log_fmx_beamline_reference():
    """
    Prints reference values and appends to the FMX log file
    
   
    Examples
    --------
    fmx_beamline_reference()
        
    """
    global flux_df
    messages = [
        f"Energy = {get_energy():.2f} eV",
        f"Beam current = {beam_current.get():.2f} mA",
        f"IVU gap = {ivu_gap.gap.user_readback.get():.1f} um",
        f"XBPM2 posX = {xbpm2.x.get():.2f} um",
        f"XBPM2 posY = {xbpm2.y.get():.2f} um",
        f"XBPM2 total current = {xbpm2.total.get():.2f} uA",
        f"HDCM pitch = {hdcm.p.user_readback.get():.4f} mrad", 
        f"HDCM roll = {hdcm.r.user_readback.get():.4f} mrad", 
        f"BPM1 posX = {bpm1.x.get():.2f}", 
        f"BPM1 posY = {bpm1.y.get():.2f}",
        f"BPM1 total current = {bpm1.sum_all.get():.3f} A",
        f"HFM pitch = {hfm.pitch.user_readback.get():.4f} mrad", 
        f"VKB tweak voltage = {vkb_piezo_tweak.get():.3f} V", 
        f"VKB pitch = {kbm.vp.user_readback.get():.4f} urad", 
        f"HKB tweak voltage = {hkb_piezo_tweak.get():.3f} V", 
        f"HKB pitch = {kbm.hp.user_readback.get():.4f} urad", 
        f"Gonio X = {gonio.gx.user_readback.get():.1f} um", 
        f"Gonio Y = {gonio.gy.user_readback.get():.1f} um", 
        f"Gonio Z = {gonio.gz.user_readback.get():.1f} um",
   ]
    for message in messages:
        print(message)
        logger.info(message)
    if flux_df is not None:
        logger.info(f"Flux dataframe {flux_df.to_string()}")
