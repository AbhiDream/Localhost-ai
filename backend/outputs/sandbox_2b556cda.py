# Import necessary libraries
import numpy as np

# Define the function to calculate heat duty
def calculate_heat_duty(Ti1, To1, Ti2, To2, Q):
    # Calculate the LMTD
    LMTD = (To1 - Ti2) / np.log((To1 - Ti2) / (To2 - Ti1))
    
    # Calculate the heat duty
    Q = LMTD * (Ti1 - Ti2)
    
    return Q

# Sample values
Ti1 = 120  # Inlet temperature of hot fluid (°C)
To1 = 65   # Outlet temperature of hot fluid (°C)
Ti2 = 30   # Inlet temperature of cold fluid (°C)
To2 = 50   # Outlet temperature of cold fluid (°C)
Q = 5000  # Flow rate (kg/hr)

# Calculate the heat duty
heat_duty = calculate_heat_duty(Ti1, To1, Ti2, To2, Q)

# Print the result
print(f"The heat duty for the shell and tube heat exchanger is {heat_duty} kJ/hr.")