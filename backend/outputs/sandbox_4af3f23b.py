def calculate_lmtd(T1, T2, T3, T4):
    """
    Calculate the LMTD (Log Mean Temperature Difference) for a counter-flow heat exchanger.

    Parameters:
    T1 (float): Temperature of fluid 1 at the inlet.
    T2 (float): Temperature of fluid 2 at the inlet.
    T3 (float): Temperature of fluid 1 at the outlet.
    T4 (float): Temperature of fluid 2 at the outlet.

    Returns:
    float: The LMTD value.
    """
    delta_T1 = T1 - T3
    delta_T2 = T2 - T4
    if delta_T1 == 0 or delta_T2 == 0:
        raise ValueError("Delta T1 or Delta T2 cannot be zero.")
    
    lmtd = (delta_T1 - delta_T2) / (log(delta_T1 / delta_T2))
    return lmtd

def main():
    # Example values
    T1 = 100  # Temperature of fluid 1 at the inlet (°C)
    T2 = 50   # Temperature of fluid 2 at the inlet (°C)
    T3 = 80   # Temperature of fluid 1 at the outlet (°C)
    T4 = 30   # Temperature of fluid 2 at the outlet (°C)

    try:
        lmtd = calculate_lmtd(T1, T2, T3, T4)
        print(f"The LMTD is: {lmtd:.2f} °C")
    except ValueError as e:
        print(e)

if __name__ == "__main__":
    main()