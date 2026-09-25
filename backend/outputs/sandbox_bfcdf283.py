def lmtd(h1, h2, deltaT, deltaT1, deltaT2):
    """
    Calculate the Log Mean Temperature Difference (LMTD) for a heat exchanger.

    Args:
    h1 (float): Heat transfer coefficient at the inlet of the heat exchanger.
    h2 (float): Heat transfer coefficient at the outlet of the heat exchanger.
    deltaT (float): Temperature difference between the hot and cold fluids at the inlet.
    deltaT1 (float): Temperature difference between the hot and cold fluids at the outlet.
    deltaT2 (float): Temperature difference between the hot and cold fluids at the outlet.

    Returns:
    float: The calculated LMTD.
    """
    # Ensure deltaT1 and deltaT2 are positive
    if deltaT1 <= 0 or deltaT2 <= 0:
        raise ValueError("DeltaT1 and DeltaT2 must be positive.")

    # Calculate the LMTD
    lmtd_value = (deltaT1 + deltaT2) / 2 - (deltaT1 * deltaT2) / (deltaT1 + deltaT2)
    
    return lmtd_value

# Example usage
h1 = 100.0  # Heat transfer coefficient at the inlet (W/m^2-K)
h2 = 80.0   # Heat transfer coefficient at the outlet (W/m^2-K)
deltaT = 50.0 # Temperature difference at the inlet (K)
deltaT1 = 30.0 # Temperature difference at the outlet (K)
deltaT2 = 20.0 # Temperature difference at the outlet (K)

lmtd_result = lmtd(h1, h2, deltaT, deltaT1, deltaT2)
print(f"The calculated LMTD is: {lmtd_result} K")