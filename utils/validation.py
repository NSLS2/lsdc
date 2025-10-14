from pathlib import Path
import h5py


def validate_master_HDF5_file(filename):
    """
    Validate master HDF5 by checking if data files exist and can be read
    """
    path = Path(filename)
    if not path.exists():
        return False
    try:
        if "master" in path.stem and path.suffix == ".h5":
            with h5py.File(path) as f:
                for key in f["entry"]["data"].keys():
                    f["entry"]["data"][key]
            return True
        else:
            return False
    except KeyError:
        return False
