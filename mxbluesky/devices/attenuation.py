"""Attenuation device — BCU blade attenuation + FMX RI attenuator + FMX CRL lenses.

All attenuation PVs share the ``C-OP:FMX`` (FMX) or ``B-OP:AMX`` (AMX)
prefix.  RI and CRL signals exist only on FMX; they remain disconnected
on AMX.

Instantiation::

    atten = Attenuation("XF:17IDC-OP:FMX", name="attenuation")  # FMX
    atten = Attenuation("XF:17IDB-OP:AMX", name="attenuation")  # AMX
"""

from ophyd import Component as Cpt, Device, EpicsSignal, EpicsSignalRO


class Attenuation(Device):
    """BCU transmission attenuation, RI attenuator (FMX), and CRL lenses (FMX)."""

    # --- BCU blade transmission (both beamlines) ---
    transmission_rbv  = Cpt(EpicsSignalRO, "{Attn:BCU}Trans-I")           # transmissionRBV
    transmission_set  = Cpt(EpicsSignal,   "{Attn:BCU}Trans-SP")           # transmissionSet
    transmission_go   = Cpt(EpicsSignal,   "{Attn:BCU}Cmd:Set-Cmd.PROC")  # transmissionGo
    transmission_done = Cpt(EpicsSignalRO, "{Attn:BCU}attenDone")          # transmissionDone

    # --- individual BCU blade in/out commands (FMX only; 12 blades) ---
    atten_01_out = Cpt(EpicsSignal, "{Attn:01}Cmd:Out-Cmd")   # Atten01-0
    atten_02_out = Cpt(EpicsSignal, "{Attn:02}Cmd:Out-Cmd")
    atten_03_out = Cpt(EpicsSignal, "{Attn:03}Cmd:Out-Cmd")
    atten_04_out = Cpt(EpicsSignal, "{Attn:04}Cmd:Out-Cmd")
    atten_05_out = Cpt(EpicsSignal, "{Attn:05}Cmd:Out-Cmd")
    atten_06_out = Cpt(EpicsSignal, "{Attn:06}Cmd:Out-Cmd")
    atten_07_out = Cpt(EpicsSignal, "{Attn:07}Cmd:Out-Cmd")
    atten_08_out = Cpt(EpicsSignal, "{Attn:08}Cmd:Out-Cmd")
    atten_09_out = Cpt(EpicsSignal, "{Attn:09}Cmd:Out-Cmd")
    atten_10_out = Cpt(EpicsSignal, "{Attn:10}Cmd:Out-Cmd")
    atten_11_out = Cpt(EpicsSignal, "{Attn:11}Cmd:Out-Cmd")
    atten_12_out = Cpt(EpicsSignal, "{Attn:12}Cmd:Out-Cmd")  # Atten12-0

    atten_01_in  = Cpt(EpicsSignal, "{Attn:01}Cmd:In-Cmd")   # Atten01-1
    atten_02_in  = Cpt(EpicsSignal, "{Attn:02}Cmd:In-Cmd")
    atten_03_in  = Cpt(EpicsSignal, "{Attn:03}Cmd:In-Cmd")
    atten_04_in  = Cpt(EpicsSignal, "{Attn:04}Cmd:In-Cmd")
    atten_05_in  = Cpt(EpicsSignal, "{Attn:05}Cmd:In-Cmd")
    atten_06_in  = Cpt(EpicsSignal, "{Attn:06}Cmd:In-Cmd")
    atten_07_in  = Cpt(EpicsSignal, "{Attn:07}Cmd:In-Cmd")
    atten_08_in  = Cpt(EpicsSignal, "{Attn:08}Cmd:In-Cmd")
    atten_09_in  = Cpt(EpicsSignal, "{Attn:09}Cmd:In-Cmd")
    atten_10_in  = Cpt(EpicsSignal, "{Attn:10}Cmd:In-Cmd")
    atten_11_in  = Cpt(EpicsSignal, "{Attn:11}Cmd:In-Cmd")
    atten_12_in  = Cpt(EpicsSignal, "{Attn:12}Cmd:In-Cmd")  # Atten12-1

    # --- RI attenuator (FMX only) ---
    ri_energy_sp  = Cpt(EpicsSignal, "{Attn:RI}Energy-SP")        # RIattenEnergySP
    ri_trans_sp   = Cpt(EpicsSignal, "{Attn:RI}Trans-SP")         # RI_Atten_SP
    ri_set        = Cpt(EpicsSignal, "{Attn:RI}Cmd:Set-Cmd.PROC") # RI_Atten_SET

    # --- CRL lenses (FMX only) ---
    crl_vs_in    = Cpt(EpicsSignal, "{CRL:02}Cmd:In-Cmd")   # CRL_VS_IN
    crl_vs_out   = Cpt(EpicsSignal, "{CRL:02}Cmd:Out-Cmd")  # CRL_VS_OUT
    crl_v2a_in   = Cpt(EpicsSignal, "{CRL:04}Cmd:In-Cmd")   # CRL_V2A_IN
    crl_v2a_out  = Cpt(EpicsSignal, "{CRL:04}Cmd:Out-Cmd")
    crl_v1a_in   = Cpt(EpicsSignal, "{CRL:08}Cmd:In-Cmd")   # CRL_V1A_IN
    crl_v1a_out  = Cpt(EpicsSignal, "{CRL:08}Cmd:Out-Cmd")
    crl_v1b_in   = Cpt(EpicsSignal, "{CRL:06}Cmd:In-Cmd")   # CRL_V1B_IN
    crl_v1b_out  = Cpt(EpicsSignal, "{CRL:06}Cmd:Out-Cmd")
    crl_h4a_in   = Cpt(EpicsSignal, "{CRL:03}Cmd:In-Cmd")   # CRL_H4A_IN
    crl_h4a_out  = Cpt(EpicsSignal, "{CRL:03}Cmd:Out-Cmd")
    crl_h2a_in   = Cpt(EpicsSignal, "{CRL:05}Cmd:In-Cmd")   # CRL_H2A_IN
    crl_h2a_out  = Cpt(EpicsSignal, "{CRL:05}Cmd:Out-Cmd")
    crl_h1a_in   = Cpt(EpicsSignal, "{CRL:07}Cmd:In-Cmd")   # CRL_H1A_IN
    crl_h1a_out  = Cpt(EpicsSignal, "{CRL:07}Cmd:Out-Cmd")
    crl_h1b_in   = Cpt(EpicsSignal, "{CRL:09}Cmd:In-Cmd")   # CRL_H1B_IN
    crl_h1b_out  = Cpt(EpicsSignal, "{CRL:09}Cmd:Out-Cmd")
