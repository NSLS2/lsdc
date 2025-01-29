from mxbluesky.devices.auto_recovery import PYZHomer
from mxbluesky.devices.generic import GoniometerStack
from bluesky import plans as bp, plan_stubs as bps
from bluesky.preprocessors import reset_positions_decorator
from ophyd.status import StatusTimeoutError
from ophyd.signal import EpicsSignal
from functools import wraps

def home_pins_plan(govmon: EpicsSignal, goniomon: EpicsSignal, pyz_homer: PYZHomer, gonio: GoniometerStack):
    @reset_positions_decorator([govmon, goniomon])
    def home_pins_inner():

        yield from bps.mv(
            govmon, 0,
            goniomon, 0,
            settle_time=1,
        )

        yield from bps.mv(
            pyz_homer.kill_py, 1,
            pyz_homer.kill_pz, 1,
            settle_time=1,
        )

        yield from bps.mv(gonio.o, 90)

        try:
            yield from bp.count([pyz_homer], 1)

        except StatusTimeoutError as e:
            print(f'Caught {e} during pinYZ home attempt, retrying')

            # kill 2x
            yield from bps.mv(
                pyz_homer.kill_py, 1,
                pyz_homer.kill_pz, 1,
                settle_time=1,
            )
            yield from bps.mv(
                pyz_homer.kill_py, 1,
                pyz_homer.kill_pz, 1,
                settle_time=1,
            )
            yield from bp.count([pyz_homer, gonio.o], 1)

        yield from bps.mv(gonio.o, 0)

    #def get_home_pins_plan():
    #    return home_pins_inner()

    #return get_home_pins_plan
    return home_pins_inner
