# Import necessary libraries
import numpy as np

def calculate_lmtd(temperature_in, temperature_out, delta_t, delta_t_avg):
    """
    Calculate the Log Mean Temperature Difference (LMTD) for a heat exchanger.
    
    Parameters:
    - temperature_in: Input temperature of the fluid (in Celsius)
    - temperature_out: Output temperature of the fluid (in Celsius)
    - delta_t: Temperature difference between the inlet and outlet of the fluid (in Celsius)
    - delta_t_avg: Average temperature difference between the inlet and outlet of the fluid (in Celsius)
    
    Returns:
    - LMTD: Log Mean Temperature Difference (in Celsius)
    """
    lmtd = np.log((temperature_in - temperature_out) / delta_t_avg) / np.log(delta_t / delta_t_avg)
    return lmtd

# Sample data
temperature_in = 100  # Celsius
temperature_out = 50   # Celsius
delta_t = 50          # Celsius
delta_t_avg = 30      # Celsius

# Calculate LMTD
lmtd_result = calculate_lmtd(temperature_in, temperature_out, delta_t, delta_t_avg)

# Output the result
print(f"The Log Mean Temperature Difference (LMTD) is: {lmtd_result:.2f} Celsius")