import math

def calculate_LMTD(Th_in, Tc_out, config_correction_factor=1.0):
    """
    Calculate the Log Mean Temperature Difference (LMTD) for a heat exchanger.
    
    Parameters:
    - Th_in: Temperature at the hot fluid inlet (in Kelvin)
    - Tc_out: Temperature at the cold fluid outlet (in Kelvin)
    - config_correction_factor: Configuration correction factor (default is 1.0 for pure counter-current flow)
    
    Returns:
    - LMTD: Log Mean Temperature Difference (in Kelvin)
    """
    dT1 = Th_in - Tc_out
    LMTD = dT1 / math.log(dT1 / dT2)
    return LMTD * config_correction_factor

# Example usage
Th_in = 300  # Hot fluid inlet temperature in Kelvin
Tc_out = 200  # Cold fluid outlet temperature in Kelvin
config_correction_factor = 1.0  # Pure counter-current flow

LMTD = calculate_LMTD(Th_in, Tc_out, config_correction_factor)
print(f"LMTD: {LMTD} K")