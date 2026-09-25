import math

def calculate_lmtd_counter_current(Th_in, Tc_out, delta_T1):
    """
    Calculate the Log Mean Temperature Difference (LMTD) for counter-current flow.

    Parameters:
    Th_in (float): Temperature at the hot fluid inlet (in Celsius).
    Tc_out (float): Temperature at the cold fluid outlet (in Celsius).
    delta_T1 (float): Temperature difference at the hot fluid inlet (in Celsius).

    Returns:
    float: The LMTD value.
    """
    LMTD = (delta_T1 - (Tc_out - Th_in)) / math.log(delta_T1 / (Tc_out - Th_in))
    return LMTD

def calculate_lmtd_co_current(Th_in, Tc_out, delta_T1, delta_T2):
    """
    Calculate the Log Mean Temperature Difference (LMTD) for co-current flow.

    Parameters:
    Th_in (float): Temperature at the hot fluid inlet (in Celsius).
    Tc_out (float): Temperature at the cold fluid outlet (in Celsius).
    delta_T1 (float): Temperature difference at the hot fluid inlet (in Celsius).
    delta_T2 (float): Temperature difference at the cold fluid outlet (in Celsius).

    Returns:
    float: The LMTD value.
    """
    LMTD = (delta_T1 - delta_T2) / math.log(delta_T1 / delta_T2)
    return LMTD

# Example usage
Th_in = 100  # Temperature at hot fluid inlet in Celsius
Tc_out = 50   # Temperature at cold fluid outlet in Celsius
delta_T1 = 50  # Temperature difference at hot fluid inlet in Celsius

# Calculate LMTD for counter-current flow
lmtd_counter_current = calculate_lmtd_counter_current(Th_in, Tc_out, delta_T1)
print(f"LMTD for counter-current flow: {lmtd_counter_current} K")

# Calculate LMTD for co-current flow
delta_T2 = 30  # Temperature difference at cold fluid outlet in Celsius
lmtd_co_current = calculate_lmtd_co_current(Th_in, Tc_out, delta_T1, delta_T2)
print(f"LMTD for co-current flow: {lmtd_co_current} K")