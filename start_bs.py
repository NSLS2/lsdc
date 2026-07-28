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
from mxbluesky import BeamlineDevices
from tiled.client import from_uri
from bluesky_tiled_plugins import TiledWriter
from bluesky_tiled_plugins.writing.tiled_writer import RunNormalizer
from bluesky_tiled_plugins.writing.consolidators import CONSOLIDATOR_REGISTRY, HDF5Consolidator
import matplotlib.pyplot as plt
from bluesky.run_engine import RunEngine
from bluesky.log import config_bluesky_logging
from bluesky.callbacks import *
from mxbluesky.devices import BeamlineDevices

# setup RedisJsonDict
uri = f"info.{os.environ['BEAMLINE_ID']}.nsls2.bnl.gov"
# Provide an endstation prefix, if needed, with a trailing "-"
new_md = RedisJSONDict(redis.Redis(uri, protocol=2),prefix="lsdc-")

plt.ion()

class EigerMXConsolidator(HDF5Consolidator):

    supported_mimetypes = {"application/x-hdf5;type=eiger"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.assets[0].parameter = "master"

    def validate(self, fix_errors=False) -> list[str]:
        raise NotImplementedError("Validation of Eiger MX resources should be handled in the adapter, not the consolidator.")


CONSOLIDATOR_REGISTRY.update(
    {
         "application/x-hdf5;type=eiger": EigerMXConsolidator,
    },
)

RE = RunEngine(context_managers=[])
beamline = os.environ["BEAMLINE_ID"]
tiled_client = from_profile(beamline)[f"/{beamline}/migration"]
tiled_key = os.environ[f"TILED_BLUESKY_WRITING_API_KEY_{beamline.upper()}"]
tiled_client = from_uri("https://tiled.nsls2.bnl.gov", api_key=tiled_key)[f"{beamline}/migration"]

tw = TiledWriter(
    tiled_client,
    normalizer=RunNormalizer,
    spec_to_mimetype={
        "AD_EIGER_MX":        "application/x-hdf5;type=eiger",
        "AD_EIGER_MX_OMEGA":  "application/x-hdf5",
        "AD_EIGER_MX_RASTER": "application/x-hdf5;type=eiger",
    }
)

# from databroker import Broker
# db = Broker.named(beamline)
RE.md = new_md

# RE.subscribe(db.insert)
RE.subscribe(tw)

config_bluesky_logging()

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
                                   TopAlignerFast, TopAlignerSlow, GoniometerStack, Dewar, RobotArm, SmartMagnet)
    from mxbluesky.devices.auto_recovery import PYZHomer
    from mxbluesky.devices.cryostream import CryoStream
    from mxbluesky.plans.auto_recovery import home_pins_plan
    from mxtools.vector_program import VectorProgram
    from mxtools.flyer import MXFlyer
    from mxtools.raster_flyer import MXRasterFlyer
    from embl_robot import EMBLRobot

    beamline_devices = BeamlineDevices.from_beamline("amx")

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
    cs1000 = CryoStream("XF:17IDB-ES:AMX{CS:1}", name="cs1000", atol=0.1)
    smart_magnet = SmartMagnet("XF:17IDB-ES:AMX", name="smart_magnet")
    force_torque_sensor = EpicsSignal("XF:17IDB-ES:AMX{FTS:1}Read-Cmd.SCAN")

elif beamline == "fmx":
    from mxbluesky.devices import (WorkPositions, TwoClickLowMag, LoopDetector, MountPositions, 
                                   TopAlignerFast, TopAlignerSlow, GoniometerStack, Dewar, RobotArm, SmartMagnet)
    from mxtools.vector_program import VectorProgram
    from mxbluesky.devices.auto_recovery import PYZHomer
    from mxbluesky.devices.cryostream import CryoStream
    from mxbluesky.plans.auto_recovery import home_pins_plan
    from mxtools.vector_program import VectorProgram
    from mxtools.flyer import MXFlyer
    from mxtools.raster_flyer import MXRasterFlyer
    from embl_robot import EMBLRobot
    import setenergy_lsdc

    beamline_devices = BeamlineDevices.from_beamline("fmx")

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
    cs1000 = CryoStream("XF:17IDC-ES:FMX{CS:1}", name="cs1000", atol=0.1)
    smart_magnet = SmartMagnet("XF:17IDC-ES:FMX", name="smart_magnet")
    force_torque_sensor = EpicsSignal("XF:17IDC-ES:FMX{FTS:1}Read-Cmd.SCAN")
else:
    raise Exception(f"Invalid beamline name provided: {beamline}")

if beamline in ("amx", "fmx"):
    set_eiger_defaults(eiger)
