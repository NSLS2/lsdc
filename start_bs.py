#!/opt/conda_envs/lsdc-server-2023-2-latest/bin/ipython -i
# import asyncio
from ophyd import *
from ophyd.mca import (Mercury1, SoftDXPTrigger)
from ophyd import Device, EpicsMotor, EpicsSignal, EpicsSignalRO
from mxtools.zebra import Zebra
from mxtools.eiger import EigerSingleTriggerV26, set_eiger_defaults
import os
from mxtools.governor import _make_governors
from ophyd.signal import EpicsSignalBase
EpicsSignalBase.set_defaults(timeout=10, connection_timeout=10)  # new style
import redis
from redis_json_dict import RedisJSONDict

# setup RedisJsonDict
uri = f"info.{os.environ['BEAMLINE_ID']}.nsls2.bnl.gov"
# Provide an endstation prefix, if needed, with a trailing "-"
new_md = RedisJSONDict(redis.Redis(uri),prefix="lsdc-")

import matplotlib.pyplot as plt
plt.ion()

import bluesky.plans as bp

from bluesky.run_engine import RunEngine
RE = RunEngine()
beamline = os.environ["BEAMLINE_ID"]
from nslsii import configure_kafka_publisher
configure_kafka_publisher(RE, beamline)
from databroker import Broker
db = Broker.named(beamline)
RE.md = new_md

RE.subscribe(db.insert)

from bluesky.log import config_bluesky_logging
config_bluesky_logging()

from bluesky.callbacks import *
abort = RE.abort
resume = RE.resume
stop = RE.stop


from ophyd import (SingleTrigger, ProsilicaDetector,
                   ImagePlugin, StatsPlugin, ROIPlugin)

from ophyd import Component as Cpt

class ABBIXMercury(Mercury1, SoftDXPTrigger):
    pass


class VerticalDCM(Device):
    b = Cpt(EpicsMotor, '-Ax:B}Mtr')
    g = Cpt(EpicsMotor, '-Ax:G}Mtr')
    p = Cpt(EpicsMotor, '-Ax:P}Mtr')
    r = Cpt(EpicsMotor, '-Ax:R}Mtr')
    e = Cpt(EpicsMotor, '-Ax:E}Mtr')
    w = Cpt(EpicsMotor, '-Ax:W}Mtr')

class StandardProsilica(SingleTrigger, ProsilicaDetector):
    image = Cpt(ImagePlugin, 'image1:')
    roi1 = Cpt(ROIPlugin, 'ROI1:')
    stats1 = Cpt(StatsPlugin, 'Stats1:')
    stats5 = Cpt(StatsPlugin, 'Stats5:')

def filter_camera_data(camera):
    camera.read_attrs = ['stats1', 'stats5']
    camera.stats1.read_attrs = ['total', 'centroid']
    camera.stats5.read_attrs = ['total', 'centroid']

class SampleXYZ(Device):
    x = Cpt(EpicsMotor, ':X}Mtr')
    y = Cpt(EpicsMotor, ':Y}Mtr')
    z = Cpt(EpicsMotor, ':Z}Mtr')
    omega = Cpt(EpicsMotor, ':O}Mtr')

if (beamline=="amx"):
    from mxbluesky.devices import (WorkPositions, TwoClickLowMag, LoopDetector, MountPositions, 
                                   TopAlignerFast, TopAlignerSlow, GoniometerStack, Dewar, RobotArm)
    from mxbluesky.devices.auto_recovery import PYZHomer
    from mxbluesky.devices.cryostream import CryoStream
    from mxbluesky.plans.auto_recovery import home_pins_plan
    from mxtools.vector_program import VectorProgram
    from mxtools.flyer import MXFlyer
    from mxtools.raster_flyer import MXRasterFlyer
    from embl_robot import EMBLRobot

    mercury = ABBIXMercury('XF:17IDB-ES:AMX{Det:Mer}', name='mercury')
    mercury.read_attrs = ['mca.spectrum', 'mca.preset_live_time', 'mca.rois.roi0.count',
                                            'mca.rois.roi1.count', 'mca.rois.roi2.count', 'mca.rois.roi3.count']
    vdcm = VerticalDCM('XF:17IDA-OP:AMX{Mono:DCM', name='vdcm')
    zebra = Zebra('XF:17IDB-ES:AMX{Zeb:2}:', name='zebra')
    eiger = EigerSingleTriggerV26('XF:17IDB-ES:AMX{Det:Eig9M}', name='eiger', beamline=beamline)
    vector_program = VectorProgram('XF:17IDB-ES:AMX{Gon:1-Vec}', name='vector_program')
    flyer = MXFlyer(vector_program, zebra, eiger)
    raster_flyer = MXRasterFlyer(vector_program, zebra, eiger)
    samplexyz = SampleXYZ("XF:17IDB-ES:AMX{Gon:1-Ax", name="samplexyz")

    robot = EMBLRobot()
    govs = _make_governors("XF:17IDB-ES:AMX", name="govs")
    gov_robot = govs.gov.Robot

    back_light = EpicsSignal(read_pv="XF:17DB-ES:AMX{BL:1}Ch1Value",name="back_light")
    back_light_range = (0, 100)

    work_pos = WorkPositions("XF:17IDB-ES:AMX", name="work_pos")
    mount_pos = MountPositions("XF:17IDB-ES:AMX", name="mount_pos")
    two_click_low = TwoClickLowMag("XF:17IDB-ES:AMX{Cam:6}", name="two_click_low")
    low_mag_cam_reset_signal = EpicsSignal('XF:17IDB-CT:AMX{IOC:CAM06}:SysReset')
    top_cam_reset_signal = EpicsSignal('XF:17IDB-CT:AMX{IOC:CAM09}:SysReset')
    gonio = GoniometerStack("XF:17IDB-ES:AMX{Gon:1", name="gonio")
    loop_detector = LoopDetector(name="loop_detector")
    top_aligner_fast = TopAlignerFast(name="top_aligner_fast", gov_robot=gov_robot)
    top_aligner_slow = TopAlignerSlow(name="top_aligner_slow")
    gov_mon_signal = EpicsSignal("XF:17ID:AMX{Karen}govmon", name="govmon")
    gonio_mon_signal = EpicsSignal("XF:17ID:AMX{Karen}goniomon", name="goniomon")
    pyz_homer = PYZHomer("", name="pyz_homer")
    dewar = Dewar("XF:17IDB-ES:AMX", name="dewar")
    home_pins = home_pins_plan(gov_mon_signal, gonio_mon_signal, pyz_homer, gonio)
    robot_arm = RobotArm("XF:17IDB-ES:AMX", name="robot_arm")
    cs700 = CryoStream("XF:17ID1:CS700:", name="cs700", atol=0.1)

elif beamline == "fmx":
    from mxbluesky.devices import (WorkPositions, TwoClickLowMag, LoopDetector, MountPositions, 
                                   TopAlignerFast, TopAlignerSlow, GoniometerStack, Dewar, RobotArm)
    from mxtools.vector_program import VectorProgram
    from mxbluesky.devices.auto_recovery import PYZHomer
    from mxbluesky.devices.cryostream import CryoStream
    from mxbluesky.plans.auto_recovery import home_pins_plan
    from mxtools.vector_program import VectorProgram
    from mxtools.flyer import MXFlyer
    from mxtools.raster_flyer import MXRasterFlyer
    from embl_robot import EMBLRobot
    import setenergy_lsdc

    mercury = ABBIXMercury('XF:17IDC-ES:FMX{Det:Mer}', name='mercury')
    mercury.read_attrs = ['mca.spectrum', 'mca.preset_live_time', 'mca.rois.roi0.count',
                                            'mca.rois.roi1.count', 'mca.rois.roi2.count', 'mca.rois.roi3.count']
    vdcm = VerticalDCM('XF:17IDA-OP:FMX{Mono:DCM', name='vdcm')
    zebra = Zebra('XF:17IDC-ES:FMX{Zeb:3}:', name='zebra')
    eiger = EigerSingleTriggerV26('XF:17IDC-ES:FMX{Det:Eig16M}', name='eiger', beamline=beamline)
    vector_program = VectorProgram('XF:17IDC-ES:FMX{Gon:1-Vec}', name='vector_program')
    flyer = MXFlyer(vector_program, zebra, eiger)
    raster_flyer = MXRasterFlyer(vector_program, zebra, eiger)
    samplexyz = SampleXYZ("XF:17IDC-ES:FMX{Gon:1-Ax", name="samplexyz")

    robot = EMBLRobot()
    govs = _make_governors("XF:17IDC-ES:FMX", name="govs")
    gov_robot = govs.gov.Robot

    back_light = EpicsSignal(read_pv="XF:17DC-ES:FMX{BL:1}Ch1Value",name="back_light")
    back_light_range = (0, 100)

    work_pos = WorkPositions("XF:17IDC-ES:FMX", name="work_pos")
    mount_pos = MountPositions("XF:17IDC-ES:FMX", name="mount_pos")
    two_click_low = TwoClickLowMag("XF:17IDC-ES:FMX{Cam:7}", name="two_click_low")
    low_mag_cam_reset_signal = EpicsSignal('XF:17IDC-CT:FMX{IOC:CAM07}:SysReset')
    gonio = GoniometerStack("XF:17IDC-ES:FMX{Gon:1", name="gonio")
    loop_detector = LoopDetector(name="loop_detector")
    top_aligner_fast = TopAlignerFast(name="top_aligner_fast", gov_robot=gov_robot)
    top_aligner_slow = TopAlignerSlow(name="top_aligner_slow")
    gov_mon_signal = EpicsSignal("XF:17ID:FMX{Karen}govmon", name="govmon")
    gonio_mon_signal = EpicsSignal("XF:17ID:FMX{Karen}goniomon", name="goniomon")
    pyz_homer = PYZHomer("", name="pyz_homer")
    dewar = Dewar("XF:17IDC-ES:FMX", name="dewar")
    home_pins = home_pins_plan(gov_mon_signal, gonio_mon_signal, pyz_homer, gonio)
    robot_arm = RobotArm("XF:17IDC-ES:FMX", name="robot_arm")
    cs700 = CryoStream("XF:17ID2:CS700:", name="cs700", atol=0.1)
else:
    raise Exception(f"Invalid beamline name provided: {beamline}")

if beamline in ("amx", "fmx"):
    set_eiger_defaults(eiger)
