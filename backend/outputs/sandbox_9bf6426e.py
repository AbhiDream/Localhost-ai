import math

def calculate_lmtd(ha, hb, deltaT, D, k, nu):
    """
    Calculate the Log Mean Temperature Difference (LMTD) for a heat exchanger.

    Parameters:
    ha (float): Heat transfer coefficient on the hot side.
    hb (float): Heat transfer coefficient on the cold side.
    deltaT (float): Temperature difference between the hot and cold fluids.
    D (float): Diameter of the heat exchanger tube.
    k (float): Thermal conductivity of the heat exchanger material.
    nu (float): Viscosity of the fluid.

    Returns:
    float: The calculated LMTD.
    """
    # Calculate the Biot number
    Bi = (k * D) / (nu * deltaT)

    # Determine the appropriate LMTD calculation method
    if Bi < 0.01:
        # LMTD for large Biot number
        lmtd = (deltaT / 2) * math.log((ha / hb) + 1)
    elif Bi < 1:
        # LMTD for moderate Biot number
        lmtd = (deltaT / 2) * math.log((ha / hb) + 1) * (1 + (0.5 * Bi))
    else:
        # LMTD for small Biot number
        lmtd = (deltaT / 2) * math.log((ha / hb) + 1) * (1 + (0.5 * Bi) + (0.083 * Bi**2))

    return lmtd

# Sample values
ha = 100  # Heat transfer coefficient on the hot side (W/m^2K)
hb = 50   # Heat transfer coefficient on the cold side (W/m^2K)
deltaT = 20  # Temperature difference (K)
D = 0.01  # Diameter of the heat exchanger tube (m)
k = 0.5   # Thermal conductivity of the heat exchanger material (W/mK)
nu = 1e-5  # Viscosity of the fluid (Pa*s)

# Calculate LMTD
lmtd = calculate_lmtd(ha, hb, deltaT, D, k, nu)

# Output the result
print(f"The calculated LMTD is: {lmtd:.2f} K")