import numpy as np

def lmtd_calculation(T1, T2, h, deltaT):
    """
    Calculate the Log Mean Temperature Difference (LMTD) for a heat exchanger.

    Parameters:
    - T1: Initial temperature of the fluid (in Celsius)
    - T2: Final temperature of the fluid (in Celsius)
    - h: Heat transfer coefficient (in W/m^2K)
    - deltaT: Temperature difference across the heat exchanger (in Celsius)

    Returns:
    - LMTD: Log Mean Temperature Difference (in Celsius)
    """
    # Calculate the LMTD using the formula
    lmtd = (np.log(T2 - deltaT) - np.log(T1 + deltaT)) / np.log(deltaT / (T2 - T1))
    return lmtd

# Sample values
T1 = 25  # Initial temperature in Celsius
T2 = 100  # Final temperature in Celsius
h = 1000  # Heat transfer coefficient in W/m^2K
deltaT = 20  # Temperature difference in Celsius

# Calculate LMTD
lmtd = lmtd_calculation(T1, T2, h, deltaT)

# Output the result
print(f"The Log Mean Temperature Difference (LMTD) is: {lmtd:.2f} degrees Celsius")