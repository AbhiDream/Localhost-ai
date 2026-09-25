import math

def calculate_lmtd(Th_in, Tc_out, flow_direction='counter_current'):
    """
    Calculate the Log Mean Temperature Difference (LMTD) for heat exchanger.

    Parameters:
    - Th_in: Temperature at hot fluid inlet (K)
    - Tc_out: Temperature at cold fluid outlet (K)
    - flow_direction: 'counter_current' or 'co_current'

    Returns:
    - LMTD: Log Mean Temperature Difference (K)
    """
    if flow_direction == 'counter_current':
        dT1 = Th_in - Tc_out
        dT2 = Tc_out - Th_in
    elif flow_direction == 'co_current':
        dT1 = Th_in - Tc_in
        dT2 = Th_out - Tc_out
    else:
        raise ValueError("Invalid flow direction. Use 'counter_current' or 'co_current'.")

    lmtd = (dT1 - dT2) / math.log(dT1 / dT2)
    return lmtd

# Example usage:
Th_in = 300  # Temperature at hot fluid inlet (K)
Tc_out = 250  # Temperature at cold fluid outlet (K)
lmtd = calculate_lmtd(Th_in, Tc_out, flow_direction='counter_current')
print(f"LMTD for counter-current flow: {lmtd:.2f} K")