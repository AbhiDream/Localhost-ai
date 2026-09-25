def lmtd_parallel_flow(h1, h2, deltaT1, deltaT2, deltaT3):
    """
    Calculate the Log Mean Temperature Difference (LMTD) for a parallel flow heat exchanger.

    :param h1: Heat transfer coefficient for the first fluid (W/m^2K)
    :param h2: Heat transfer coefficient for the second fluid (W/m^2K)
    :param deltaT1: Temperature difference between the hot fluid and the heat exchanger (K)
    :param deltaT2: Temperature difference between the cold fluid and the heat exchanger (K)
    :param deltaT3: Temperature difference between the hot and cold fluids (K)
    :return: LMTD (K)
    """
    bi = (h1 * deltaT1) / (h2 * deltaT2)
    if bi < 0.2:
        lmtd = (deltaT1 - deltaT2) / (log(deltaT1 / deltaT2))
    elif bi < 0.6:
        lmtd = (deltaT1 + deltaT2) / 2
    else:
        lmtd = (deltaT3 - deltaT2) / (log(deltaT3 / deltaT2))
    return lmtd

def main():
    # Example values
    h1 = 100  # Heat transfer coefficient for the first fluid (W/m^2K)
    h2 = 200  # Heat transfer coefficient for the second fluid (W/m^2K)
    deltaT1 = 30  # Temperature difference between the hot fluid and the heat exchanger (K)
    deltaT2 = 10  # Temperature difference between the cold fluid and the heat exchanger (K)
    deltaT3 = 20  # Temperature difference between the hot and cold fluids (K)

    # Calculate LMTD
    lmtd = lmtd_parallel_flow(h1, h2, deltaT1, deltaT2, deltaT3)
    print(f"LMTD for parallel flow heat exchanger: {lmtd:.2f} K")

if __name__ == "__main__":
    main()