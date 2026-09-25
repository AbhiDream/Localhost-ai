# Import necessary libraries
import math

def calculate_lmtd(Q, deltaT, deltaT_avg):
    """
    Calculate the Log Mean Temperature Difference (LMTD) for a heat exchanger.
    
    Parameters:
    Q (float): Heat transfer rate in watts [W]
    deltaT (float): Temperature difference between hot and cold fluids at the inlet [K]
    deltaT_avg (float): Average temperature difference between hot and cold fluids [K]
    
    Returns:
    float: Log Mean Temperature Difference [K]
    """
    if deltaT_avg == 0:
        raise ValueError("Average temperature difference cannot be zero.")
    
    lmtd = math.log(deltaT / deltaT_avg) / math.log(2)
    return lmtd

# Sample data
Q = 1000  # Heat transfer rate in watts
deltaT = 20  # Temperature difference at inlet [K]
deltaT_avg = 15  # Average temperature difference [K]

# Calculate LMTD
lmtd_result = calculate_lmtd(Q, deltaT, deltaT_avg)

# Output the result
print(f"The calculated LMTD is: {lmtd_result:.2f} K")