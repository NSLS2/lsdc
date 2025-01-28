import sys
import logging
from pathlib import Path
from networkx import DiGraph, bfs_tree
import os
import getpass
import tempfile

logger = logging.getLogger()
class bcolors:
    """Class to add colors to output text"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'



def healthcheck(name:str='', 
                remediation: str='',
                fatal=False,
                depends=None):
    """Decorator added to functions that checks the health of the system, ideally before
    running the LSDC code
    """
    def dec(f):
        f.name = name
        if not hasattr(f, remediation):
            f.remediation = remediation
        f.fatal = fatal
        f.passed = True
        f.depends = depends if depends is not None else [start]
        return f
    return dec

# Add check functions with the above decorator here...
@healthcheck(name='start', depends=())
def start():
    return True

# GUI checks
@healthcheck(
    name='import daq_utils',
    remediation='', # Dynamic remediation defined in function
    fatal=True
)
def check_daq_utils():
    try:
        import daq_utils
        return True
    except Exception as e:
        check_daq_utils.remediation = f'Error importing daq_utils: {e}'
        return False

@healthcheck(
    name='working directory',
    remediation='', # Dynamic remediation defined in function
    fatal=True
)
def check_working_directory():
    import daq_utils
    import os
    working_dir = Path.cwd()
    home_dir = Path.home()
    if home_dir in working_dir.parents or home_dir == working_dir:
        check_working_directory.remediation = f'Please start LSDC in {daq_utils.beamline} data directory, not home directory'
        return False
    if daq_utils.beamline not in working_dir.parts: 
        # Hacky way to check if amx or fmx is in path. Unless server can tell GUI where its running?
        check_working_directory.remediation = f'Please start LSDC in {daq_utils.beamline} data directory. Current directory: {working_dir}'
        return False
    if Path(daq_utils.getBlConfig("visitDirectory")).resolve() != working_dir:
        check_working_directory.remediation = ("Working directory mismatch. Please start LSDC GUI in the same folder as the server is running.")

        return False
    return True


@healthcheck(
    name='database lib',
    remediation='Please check if mongo database and servers are running',
    fatal=False
)
def check_db():
    import db_lib
    return True


def handle_fail(check):
    """Function to handle a failed check
    """
    print(f'{bcolors.FAIL}Fail{bcolors.ENDC}')
    print(f'{bcolors.WARNING}{bcolors.BOLD}{check.remediation}{bcolors.ENDC}')
    check.passed = False
    logger.error(f'Check {check.name} failed')
    if check.fatal:
        print("End checks")
        print(u'\u2500' * 20)
        print('Fatal error, exiting...')
        os._exit(1)

# Server checks
@healthcheck(name="check service user", remediation="LSDC server not being started by a LSDC service user account, aborting!")
def check_service_user() -> bool:
    if not getpass.getuser().startswith("lsdc-"):
        return False
    print(f"continuing as we are using a service user: {getpass.getuser()}")
    return True

def has_write_permission(directory):
    try:
        testfile = tempfile.TemporaryFile(dir = directory)
        testfile.close()
    except OSError as e:
        if e.errno == 13: # Permission denied
            return False
        raise
    return True

@healthcheck(name="server working directory", remediation="", fatal=True)
def check_curr_visit_dir() -> bool:
    import daq_utils
    # Check if current visit dir is valid 
    visit_dir_env_var = "CURRENT_VISIT_DIR"
    if visit_dir_env_var not in os.environ:
        check_curr_visit_dir.remediation = (
            f"{visit_dir_env_var} environment variable not found"
        )
        return False
    if os.environ[visit_dir_env_var] == "":
        check_curr_visit_dir.remediation = f"{visit_dir_env_var} is empty"
        return False
    current_visit_dir = Path(os.environ[visit_dir_env_var])
    if not current_visit_dir.exists():
        check_curr_visit_dir.remediation = (
            f"{visit_dir_env_var} = {current_visit_dir} does not exist"
        )
        return False
    
    # Check if current visit dir is one of the dirs defined in BASE_DATA_DIRS
    base_dir_env_var = f"BASE_DATA_DIRS_{daq_utils.beamline.upper()}"
    if base_dir_env_var not in os.environ:
        check_curr_visit_dir.remediation = f"{base_dir_env_var} evironment variable not found"
        return False
    # Splitting on : if there are multiple base dirs
    base_dirs = [Path(p) for p in os.environ[base_dir_env_var].split(":")]
    pass_dir_found = False
    for i, part in enumerate(reversed(current_visit_dir.parts)):
        if 'pass-' in part:
            pass_dir_found = True
            if current_visit_dir.parents[i] not in base_dirs:
                check_curr_visit_dir.remediation = f"{current_visit_dir.parents[i]} not found in {base_dirs}"
                return False
            else:
                break
    if not pass_dir_found:
        check_curr_visit_dir.remediation = f"Pass folder not found in {current_visit_dir}"
        return False
    
    # Check if current visit dir is writable
    if not has_write_permission(current_visit_dir):
        check_curr_visit_dir.remediation = f"Server does not have write permission to {current_visit_dir}"
        return False

    return True

@healthcheck(name="check environment variables", remediation="", fatal=True)
def check_env_variables() -> bool:
    env_vars = ["STAFF_GROUP", "NSLS2_API_URL"]
    missing_vars = [var for var in env_vars if var not in os.environ]
    if missing_vars:
        check_env_variables.remediation = f"Environment variable(s) not found: {','.join(missing_vars)}"
        return False
    return True

@healthcheck(name="existence of environment file", remediation="", fatal=True)
def check_env_file() -> bool:
    import daq_utils

    env_path = Path(f"/nsls2/software/mx/current_visit_lsdc_{daq_utils.beamline}")
    if not env_path.exists():
        check_env_file.remediation = f"Environment file not found at {env_path}"
        return False
    return True


def perform_checks():
    """Call this function to contruct a DAG where each node is evaluated using
    breadth first search. DAGs allow certain tests to be run only after passing
    specific tests. For example
    """
    check_functions = [check_daq_utils, check_working_directory, check_db, check_env_variables]
    run_checks(check_functions)


def perform_server_checks():
    check_functions = [check_service_user, check_env_file, check_curr_visit_dir]
    run_checks(check_functions)


def run_checks(check_functions):
    checks = DiGraph()
    for c in check_functions:
        for d in c.depends:
            checks.add_edge(d, c)
    print("\u2500" * 20)
    print("Begin checks")
    for check in bfs_tree(checks, start):
        try:
            if all([parent.passed for parent in checks.predecessors(check)]):
                print(f"Checking {check.name}...", end="\t")
                if check():
                    print(f"{bcolors.OKGREEN}Success{bcolors.ENDC}")
                else:
                    handle_fail(check)
        except Exception as e:
            print(f"Exception: {e}")
            logger.error(f"Exception during checks {e}")
            handle_fail(check)
    print("End checks")
    print("\u2500" * 20)
