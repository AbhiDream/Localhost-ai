# Import necessary libraries
import numpy as np

def calculate_lmtd(Q, deltaT, deltaT_in, deltaT_out):
    """
    Calculate the Log Mean Temperature Difference (LMTD) for a heat exchanger.
    
    Parameters:
    - Q: Heat transfer rate (W)
    - deltaT: Temperature difference between the hot and cold fluids (°C)
    - deltaT_in: Temperature difference between the hot fluid and the heat exchanger (°C)
    - deltaT_out: Temperature difference between the cold fluid and the heat exchanger (°C)
    
    Returns:
    - LMTD: Log Mean Temperature Difference (°C)
    """
    lmtd = np.log((deltaT_in + deltaT_out) / (deltaT_in - deltaT_out)) * (deltaT / np.log(deltaT_in / deltaT_out))
    return lmtd

# Sample data
Q = 1000  # Heat transfer rate (W)
deltaT = 10  # Temperature difference between hot and cold fluids (°C)
deltaT_in = 5  # Temperature difference between hot fluid and heat exchanger (°C)
deltaT_out = 15  # Temperature difference between cold fluid and heat exchanger (°C)

# Calculate LMTD
lmtd = calculate_lmtd(Q, deltaT, deltaT_in, deltaT_out)

# Print the result
print(f"The calculated LMTD is: {lmtd:.2f} °C")