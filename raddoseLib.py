# RD3D_calc Raddose3D interface
import subprocess
import numpy as np
from numpy.lib import recfunctions as rfn  # needs to be imported separately
from shutil import copyfile
import fileinput
import sys
import os.path
import os
import logging

logger = logging.getLogger(__name__)

# 12/19 - See Martin about this code!


def replaceLines(filename, replacementStrings):
    lines = []
    with open(filename, "r") as f:
        for line in f.readlines():
            for text_to_search, replacement_text in replacementStrings.items():
                if text_to_search in line:
                    line = replacement_text
                    break
            lines.append(line)

    with open(filename, "w") as f:
        f.writelines(lines)


def run_rd3d(inputFileName):
    prc = subprocess.Popen(
        [
            "java",
            "-jar",
            os.environ["CONFIGDIR"] + "/raddose3d.jar",
            "-i",
            inputFileName,
            "-p",
            f"rd3d/rd3d_{os.getpid()}_",
        ],
        stdout=subprocess.PIPE,
        universal_newlines=True,
    )
    out = prc.communicate()[0]
    return out


def rd3d_calc(
    flux=3.5e12,
    energy=12.66,
    beamType="GAUSSIAN",
    fwhmX=2,
    fwhmY=1,
    collimationX=10,
    collimationY=10,
    wedge=0,
    exposureTime=1,
    translatePerDegX=0,
    translatePerDegY=0,
    translatePerDegZ=0,
    startOffsetX=0,
    startOffsetY=0,
    startOffsetZ=0,
    dimX=20,
    dimY=20,
    dimZ=20,
    pixelsPerMicron=2,
    angularResolution=2,
    templateFileName=os.environ["CONFIGDIR"] + "/rd3d_input_template.txt",
    verbose=True,
):
    """
    RADDOSE3D dose estimate

    This version calculates dose values for an average protein crystal.
    The estimates need to be adjusted proportionally for a crystal if it is more/less sensitive.

    All paramaters listed below can be set. If they are not set explicitly, RADDOSE3D will use
    the listed default value.

    A complete manual with explanations is available at
    https://github.com/GarmanGroup/RADDOSE-3D/blob/master/doc/user-guide.pdf

    Photon flux [ph/s]: flux=3.5e12
    Photon energy [keV]: energy=12.66,
    Beamtype (GAUSSIAN | TOPHAT): beamType='GAUSSIAN'
    Vertical beamsize FHWM [um]: fwhmX=1
    Horizontal beamsize FHWM [um]: fwhmY=2
    Vertical collimation (for TOPHAT beams this is the size) [um]: collimationX=10
    Horizontal collimation (for TOPHAT beams this is the size) [um]: collimationY=10
    Omega range [deg]: wedge=0
    Exposure time for the complete wedge [s]: exposureTime=1
    Translation per degree V [um]: translatePerDegX=0
    Translation per degree H [um]: translatePerDegY=0
    Translation along beam per degree [um]: translatePerDegZ=0
    Crystal position offset V [um]: startOffsetX=0
    Crystal position offset H [um]: startOffsetY=0
    Crystal position offset along beam [um]: startOffsetZ=0
    Crystal dimension V [um]: dimX=20
    Crystal dimension H [um]: dimY=20
    Crystal dimension along beam [um]: dimZ=20
    Pixels per micron: pixelsPerMicron=2
    Angular resolution: angularResolution=2
    Template file (in 'rd3d' subdir of active notebook): templateFileName = 'rd3d_input_template.txt'

    Return value is a structured numpy array. You can use it for follow-up calculations
    of the results returned by RADDOSE3D in "output-Summary.csv". Call the return variable
    to find the field names.

    Examples:
    rd3d_out = rd3d_calc(flux=1.35e12, exposuretime=0.01, dimx=1, dimy=1, dimz=1)
    rd3d_calc(flux=1e12, energy=12.7, fwhmX=3, fwhmY=5, collimationX=9, collimationY=15, wedge=180,
           exposureTime=8, translatePerDegX=0, translatePerDegY=0.27, startOffsetY=-25,
           dimX=3, dimY=80, dimZ=3, pixelsPerMicron=0.5, angularResolution=2, verbose=False)

    Setup:
    * rd3d_input_template.txt and raddose.jar in subdir rd3d/
    * PDB file 2vb1.pdb in notebook dir
    2vb1.pdb
    rd3d/raddose.jar
    rd3d/rd3d_input_template.txt

    Todo:
    * Cannot call PDB file in subdir or active dir, i.e. only 'PDB 2vb1.pdb' works in rd3d_input_template.txt
    * run_rd3d() with subdir option
      * Is the subdir really worth it? Use 'raddose' prefix instead? (Tentative: yes)
      * If subdir: Clean code (run_rd3d()), subdir name as option, description in help text
        (how if it's an option?)
    * Keep template file as option? Then it should be in same dir as PDB file (notebook dir)
    * Protein option PDB (on xf17id1 cannot reach PDB URL) or JJDUMMY (how to cite?)
    """

    rd3d_dir = "rd3d"
    inputFileName = f"rd3d_{os.getpid()}_input.txt"
    outputFileName = f"rd3d_{os.getpid()}_Summary.csv"

    templateFilePath = os.path.join(rd3d_dir, templateFileName)
    inputFilePath = os.path.join(rd3d_dir, inputFileName)
    outputFilePath = os.path.join(rd3d_dir, outputFileName)

    copyfile(templateFilePath, inputFilePath)

    replacementStrings = {
        "FLUX": f"FLUX {flux:.2e}\n",
        "ENERGY": f"ENERGY {energy:.2f}\n",
        "TYPE GAUSSIAN": f"TYPE {beamType}\n",
        "FWHM": f"FWHM {fwhmX:.1f} {fwhmY:.1f}\n",
        "COLLIMATION": f"COLLIMATION RECTANGULAR {collimationX:.1f} {collimationY:.1f}\n",
        "WEDGE": f"WEDGE 0 {wedge:0.1f}\n",
        "EXPOSURETIME": f"EXPOSURETIME {exposureTime:0.3f}\n",
        "TRANSLATEPERDEGREE": f"TRANSLATEPERDEGREE {translatePerDegX:0.4f} {translatePerDegY:0.4f} {translatePerDegZ:0.4f}\n",
        "DIMENSION": f"DIMENSION {dimX:0.1f} {dimY:0.1f} {dimZ:0.1f}\n",
        "PIXELSPERMICRON": f"PIXELSPERMICRON {pixelsPerMicron:0.1f}\n",
        "ANGULARRESOLUTION": f"ANGULARRESOLUTION {angularResolution:0.1f}\n",
        "STARTOFFSET": f"STARTOFFSET {startOffsetX} {startOffsetY} {startOffsetZ}\n",
    }

    replaceLines(inputFilePath, replacementStrings)

    out = run_rd3d(inputFilePath)
    if verbose:
        logger.info(out)

    rd3d_out = np.genfromtxt(outputFilePath, delimiter=",", names=True)
    logger.info("\n=== rd3d_calc summary ===")
    # append_fields has issues with 1d arrays, use reshape() and [] to make len() work on size 1 array:
    # https://stackoverflow.com/questions/53137822/adding-a-field-to-a-structured-numpy-array-4
    rd3d_out = rd3d_out.reshape(1)
    logger.info("Diffraction weighted dose = " + "%.3f" % rd3d_out["DWD"] + " MGy")
    logger.info("Max dose = " + "%.3f" % rd3d_out["Max_Dose"] + " MGy")
    if rd3d_out["DWD"]:
        t2gl = (
            exposureTime * 30 / rd3d_out["DWD"]
        )  # Time to Garman limit based on diffraction weighted dose
    else:
        t2gl = 0
    rd3d_out = rfn.append_fields(rd3d_out, "t2gl", [t2gl], usemask=False)
    logger.info("Time to Garman limit = " + "%.3f" % rd3d_out["t2gl"] + " s")

    return rd3d_out


# ## Experiment time to reach 10 MGy dose
#
# ### Inputs:
# * Flux: From flux-at-sample PV
# * Beam size: For now, set by hand, or determine from PV, or get from get_beamsize(TBD)
# * Crystal size: Match to beam size
# * Vector length: Start with assumption, LSDC vector length is along X-axis. Update could use the real projections
#
# * Exposure time = 1 s
# * Translation per degree has to match total vector length
#
# * RD3D output = AWD [MGy]
#
# ### Input from LSDC:
# * Protocol standard or vector
# * Beamsize settings
#
# ### Output:
# * Experiment time [s] to Average Diffraction Weighted Dose = 10 MGy

import epics


def fmx_expTime(
    avg_dwd=10,  # Default of 10MGy
    beamsizeV=1.0,
    beamsizeH=2.0,
    vectorL=0,
    energy=12.66,
    flux=-1,
    wedge=180,
    verbose=False,
):
    """
    RD3D output = AWD [MGy]


    Parameters
    ----------

    beamsizeV, beamsizeH: float
    Beam size (V, H) [um]. Default 1x2 (VxH). For now, set explicitly.

    vectorL: float
    Vector length [um]: Default 0 um. Make assumption that the vector is completely oriented
    along X-axis.

    energy: float
    Photon energy [keV]. Default 12.66 keV

    wedge: float
    Crystal rotation for complete experiment [deg]. Start at 0, end at wedge

    flux: float
    Flux at sample position [ph/s]. By default this value is copied from the beamline's
    flux-at-sample PV. Can also be set explicitly.

    verbose: boolean
    True: Print out RADDOSE3D output. Default False


    Internal parameters
    -------------------

    Crystal size XYZ: Match to beam size perpendicular to (XZ), and to vector length along the
    rotation axis (Y)


    Returns
    -------

    Experiment time [s] to Average Diffraction Weighted Dose = 10 MGy


    Todo
    ----

    * Beamsize: Read from a beamsize PV, or get from a get_beamsize() function
      - Check CRL settings
      - Check BCU attenuator
      - If V1H1 then 10x10 (dep on E)
        - If V0H0 then
          - If BCU-Attn-T < 1.0 then 3x5
          - If BCU-Attn-T = 1.0 then 1x2
    * Vector length: Use the real projections
    """

    # Beam size [um]
    fwhmX = beamsizeV
    fwhmY = beamsizeH
    collimationX = 3 * beamsizeV
    collimationY = 3 * beamsizeH

    # Set explicitly or use current flux
    if flux == -1:
        # Current flux [ph/s]: From flux-at-sample PV
        fluxSample = epics.caget("XF:17IDA-OP:FMX{Mono:DCM-dflux-MA}")
        logger.info("Flux at sample = {:.4g} ph/s".format(fluxSample))
    else:
        fluxSample = flux

    # Crystal size [um]: Match to beam size in V, longer than vector in H
    # XYZ as defined by Raddose3D
    dimX = beamsizeV  # Crystal dimension V [um]
    dimY = vectorL + beamsizeH  # Crystal dimension H [um]
    dimZ = dimX  # Crystal dimension along beam [um]

    # Start offset for horizontal vector to stay within crystal [um]
    startOffsetY = -vectorL / 2

    # Exposure time [s]
    exposureTime = 1.0

    # Avoid division by zero when calculating translatePerDegY
    if wedge == 0:
        wedge = 1e-3

    # Vector length [um]: Assume LSDC vector length is along X-axis (Raddose3D Y).
    # Translation per degree has to match total vector length
    translatePerDegY = vectorL / wedge

    try:
        rd3d_out = rd3d_calc(
            flux=fluxSample,
            energy=energy,
            fwhmX=fwhmX,
            fwhmY=fwhmY,
            collimationX=collimationX,
            collimationY=collimationY,
            wedge=wedge,
            exposureTime=exposureTime,
            translatePerDegY=translatePerDegY,
            startOffsetY=startOffsetY,
            pixelsPerMicron=5,
            angularResolution=1,
            dimX=dimX,
            dimY=dimY,
            dimZ=dimZ,
            verbose=verbose,
        )

        logger.info("\n=== fmx_expTime summary ===")
        dose1s = float(rd3d_out["DWD"].item())  # .item() to convert 1d array to scalar
        logger.info(
            "Average Diffraction Weighted Dose for 1s exposure = {:f} MGy".format(
                dose1s
            )
        )
    except Exception as e:
        logger.error(f"Exception in rd3d calc: {e}")
        dose1s = 0.0

    if dose1s > 0:
        expTimeMGy = (
            avg_dwd / dose1s
        )  # Experiment time to reach an average DWD (avg_dwd)
    else:
        expTimeMGy = 0.0
    logger.info(
        f"Experiment time to reach an average diffraction weighted dose of {avg_dwd} MGy = {expTimeMGy} s"
    )

    return expTimeMGy
