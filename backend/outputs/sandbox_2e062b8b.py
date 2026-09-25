# Import necessary libraries
import numpy as np

def calculate_lmtd(T_in, T_out, deltaT, deltaT_avg):
    """
    Calculate the Log Mean Temperature Difference (LMTD) for a heat exchanger.

    Parameters:
    T_in (float): Inlet temperature of the fluid [K]
    T_out (float): Outlet temperature of the fluid [K]
    deltaT (float): Temperature difference between the hot and cold fluids [K]
    deltaT_avg (float): Average temperature difference between the hot and cold fluids [K]

    Returns:
    float: Log Mean Temperature Difference [K]
    """
    # Calculate LMTD
    lmtd = np.log((T_in - T_out) / deltaT_avg) / np.log(deltaT / deltaT_avg)
    return lmtd

# Sample values
T_in = 300  # [K]
T_out = 250  # [K]
deltaT = 50  # [K]
deltaT_avg = 30  # [K]

# Calculate LMTD
lmtd = calculate_lmtd(T_in, T_out, deltaT, deltaT_avg)

# Print the result
print(f"The Log Mean Temperature Difference (LMTD) is: {lmtd} [K]")