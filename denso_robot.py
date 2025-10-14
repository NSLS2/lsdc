from daq_utils import getBlConfig
from config_params import MOUNT_SUCCESSFUL, MOUNT_STEP_SUCCESSFUL, MOUNT_FAILURE,\
                          UNMOUNT_SUCCESSFUL, UNMOUNT_STEP_SUCCESSFUL, UNMOUNT_FAILURE
import gov_lib
import traceback
import logging
logger = logging.getLogger(__name__)

def get_denso_puck_pin(puck_number, pin_number):
    return (puck_number+1, pin_number+1)

class OphydRobot:
    def __init__(self, robot):
        self.robot = robot

    def parkRobot(self):
        try:
            self.robot.parkRobot()
        except Exception as e:
            logger.error(f'Failed to park robot: {e}')

    def warmupGripper(self):
        try:
            logger.info('drying gripper')
            self.robot.dryGripper()
        except Exception as e:
            logger.error(f'Failed to dry gripper: {e}')

    def control_type(self):
        return "Bluesky"

    def preMount(self, gov_robot, puck_pos: int, pin_pos: int, samp_id: str, **kwargs):
        try:
            status = gov_lib.setGovRobot(gov_robot, 'SE')
            kwargs['govStatus'] = status
        except Exception as e:
            logger.error(f'Exception while in preMount step: {e}')
            return MOUNT_FAILURE
        return MOUNT_STEP_SUCCESSFUL, kwargs

    def mount(self, gov_robot, puck_pos: int, pin_pos: int, samp_id: str, **kwargs):
        if getBlConfig('robot_online'):
            try:
                denso_puck_pos, denso_pin_pos = get_denso_puck_pin(puck_pos, pin_pos)
                logger.info(f'Mounting: {denso_puck_pos} {denso_pin_pos}')
                yield from self.robot.mount(denso_puck_pos, denso_pin_pos)
                logger.info(f"Done Mounting")
            except Exception as e:
                logger.error(f'Exception during mount step: {e}: traceback: {traceback.format_exc()}')
                return MOUNT_FAILURE
        else:
            denso_puck_pos, denso_pin_pos = get_denso_puck_pin(puck_pos, pin_pos)
            logger.info(f'robot offline - mount not being attempted for puck:{denso_puck_pos} pin:{denso_pin_pos} (staff: puck and pin names correspond to those on CSS)')
        return MOUNT_STEP_SUCCESSFUL

    def postMount(self, gov_robot, puck_pos: int, pin_pos: int, samp_id: str, **kwargs):
        try:
            gov_lib.setGovRobot(gov_robot, 'SA')
        except Exception as e:
            logger.error(f'Exception while in postMount step: {e}')
            return MOUNT_FAILURE
        return MOUNT_SUCCESSFUL

    def preUnmount(self, gov_robot, puck_pos: int, pin_pos: int, samp_id: str):
        denso_puck_pos, denso_pin_pos = get_denso_puck_pin(puck_pos, pin_pos)
        logger.info(f"preparing to unmount {denso_puck_pos} {denso_pin_pos} {samp_id}")
        try:
            gov_lib.setGovRobot(gov_robot, "SE")
        except Exception as e:
            logger.error(f'Exception while in preUnmount step: {e}')
            return UNMOUNT_FAILURE
        return UNMOUNT_STEP_SUCCESSFUL

    def unmount(self, gov_robot, puck_pos: int, pin_pos: int, samp_id: str):
        if getBlConfig('robot_online'):
            denso_puck_pos, denso_pin_pos = get_denso_puck_pin(puck_pos, pin_pos)
            try:
                logger.info(f'dismount {denso_puck_pos} {denso_pin_pos}')
                yield from self.robot.dismount(denso_puck_pos, denso_pin_pos)
            except Exception as e:
                logger.error(f'Exception while unmounting sample: {e}')
                return UNMOUNT_FAILURE
        else:
            denso_puck_pos, denso_pin_pos = get_denso_puck_pin(puck_pos, pin_pos)
            logger.info(f'robot offline - unmount not being attempted for puck:{denso_puck_pos} pin:{denso_pin_pos} (staff: puck and pin names correspond to those on CSS)')

        return UNMOUNT_SUCCESSFUL

    def finish(self):
        ...

    def multiSampleGripper(self):
        return True

    def check_sample_mounted(self, mount, puck_pos, pin_pos):  # is the correct sample present/absent as expected during a mount/unmount?
        if getBlConfig('robot_online'):
            if mount:
                check_occupied = 1
            else:
                check_occupied = 0
            puck_pos+=1 # these two are to correct an off-by-one issue caused by-
            pin_pos+=1 # the denso robot being 0-indexed
            actual_spindle_occupied = int(self.robot.spindle_occupied_sts.get())
            actual_puck_num = int(self.robot.puck_num_sel.get())
            actual_sample_num = int(self.robot.sample_num_sel.get())
            if actual_spindle_occupied == check_occupied and \
               actual_puck_num == puck_pos and \
               actual_sample_num == pin_pos:  # make sure puck number and sample number coming from robot and LSDC are zero- or one-indexed as necessary
                logger.info('mount/unmount successful!')
                if mount:
                    return MOUNT_STEP_SUCCESSFUL
                else:
                    return UNMOUNT_STEP_SUCCESSFUL
            else:
                logger.error(f'Failure during mount/unmount. Spindle_occupied: expected: {check_occupied} actual: {actual_spindle_occupied}. Puck num: expected: {puck_pos} actual: {actual_puck_num} Sample num: expected {pin_pos} actual: {actual_sample_num}')
                if mount:
                    return MOUNT_FAILURE
                else:
                    return UNMOUNT_FAILURE
        else:
            return MOUNT_STEP_SUCCESSFUL  # always successful if robot is not online
