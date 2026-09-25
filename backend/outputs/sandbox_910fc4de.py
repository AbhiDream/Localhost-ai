# Import necessary libraries
import numpy as np

def calculate_lmtd(T_in, T_out, delta_t, delta_x):
    """
    Calculate the Log Mean Temperature Difference (LMTD) for a heat exchanger.
    
    Parameters:
    - T_in: Temperature of the fluid entering the heat exchanger (in Celsius)
    - T_out: Temperature of the fluid leaving the heat exchanger (in Celsius)
    - delta_t: Temperature difference between the hot and cold fluids (in Celsius)
    - delta_x: Distance between the hot and cold fluids (in meters)
    
    Returns:
    - LMTD: Log Mean Temperature Difference (in Celsius)
    """
    LMTD = (delta_t / np.log(delta_t / delta_x))
    return LMTD

# Sample values
T_in = 30  # Temperature of the fluid entering the heat exchanger (Celsius)
T_out = 10  # Temperature of the fluid leaving the heat exchanger (Celsius)
delta_t = 20  # Temperature difference between the hot and cold fluids (Celsius)
delta_x = 10  # Distance between the hot and cold fluids (meters)

# Calculate LMTD
lmtd = calculate_lmtd(T_in, T_out, delta_t, delta_x)

# Print the result
print(f"The calculated LMTD is: {lmtd:.2f} Celsius")