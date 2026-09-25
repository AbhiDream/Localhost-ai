def calculate_lmtd(h1, h2, delta_t1, delta_t2):
    """
    Calculate the Log Mean Temperature Difference (LMTD) for a counter-flow heat exchanger.

    Parameters:
    h1 (float): Heat transfer coefficient for the first fluid.
    h2 (float): Heat transfer coefficient for the second fluid.
    delta_t1 (float): Temperature difference between the hot and cold fluids in the first fluid.
    delta_t2 (float): Temperature difference between the hot and cold fluids in the second fluid.

    Returns:
    float: The LMTD.
    """
    if delta_t1 == 0 or delta_t2 == 0:
        raise ValueError("Temperature differences cannot be zero.")
    
    lmtd = (delta_t1 - delta_t2) / (math.log(delta_t1 / delta_t2))
    return lmtd

def main():
    # Example input values
    h1 = float(input("Enter the heat transfer coefficient for the first fluid (h1): "))
    h2 = float(input("Enter the heat transfer coefficient for the second fluid (h2): "))
    delta_t1 = float(input("Enter the temperature difference between the hot and cold fluids in the first fluid (delta_t1): "))
    delta_t2 = float(input("Enter the temperature difference between the hot and cold fluids in the second fluid (delta_t2): "))

    try:
        lmtd = calculate_lmtd(h1, h2, delta_t1, delta_t2)
        print(f"The LMTD is: {lmtd:.2f}")
    except ValueError as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()