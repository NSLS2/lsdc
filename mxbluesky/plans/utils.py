
from bluesky.utils import FailedStatus
import bluesky.plan_stubs as bps

def retry_move(func):
    def wrapper(*args, **kwargs):
        for j in range(2):
            try:
                yield from func(*args, **kwargs)
                break
            except FailedStatus:
                if j == 0:
                    print(f"{args[0].name} is stuck, retrying...")
                    yield from bps.sleep(0.2)
                else:
                    raise RuntimeError(
                        f"{args[0].name} is really stuck!")
    return wrapper

@retry_move
def mvr_with_retry(*args, **kwargs):
    yield from bps.mvr(*args, **kwargs)


@retry_move
def mv_with_retry(*args, **kwargs):
    yield from bps.mv(*args, **kwargs)