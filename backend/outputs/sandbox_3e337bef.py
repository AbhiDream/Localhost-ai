def calculate_lmtd(heating_surface_area, delta_t_1, delta_t_2, delta_t_3):
    # Calculate the LMTD for counter-flow
    lmtd_counter_flow = (delta_t_1 - delta_t_2) / (log(delta_t_1 / delta_t_2) / log(2))

    # Calculate the LMTD for parallel-flow
    lmtd_parallel_flow = (delta_t_1 - delta_t_3) / (log(delta_t_1 / delta_t_3) / log(2))

    # Calculate the LMTD for counter-flow with forced convection
    lmtd_counter_flow_with_forced_convection = (delta_t_1 - delta_t_2) / (log(delta_t_1 / delta_t_2) / log(2))

    return lmtd_counter_flow, lmtd_parallel_flow, lmtd_counter_flow_with_forced_convection

def main():
    # Example values for demonstration
    heating_surface_area = 100  # in square meters
    delta_t_1 = 100  # in degrees Celsius
    delta_t_2 = 50  # in degrees Celsius
    delta_t_3 = 75  # in degrees Celsius

    # Calculate LMTD
    lmtd_counter_flow, lmtd_parallel_flow, lmtd_counter_flow_with_forced_convection = calculate_lmtd(
        heating_surface_area, delta_t_1, delta_t_2, delta_t_3
    )

    # Print results
    print(f"LMTD for counter-flow: {lmtd_counter_flow:.2f} degrees Celsius")
    print(f"LMTD for parallel-flow: {lmtd_parallel_flow:.2f} degrees Celsius")
    print(f"LMTD for counter-flow with forced convection: {lmtd_counter_flow_with_forced_convection:.2f} degrees Celsius")

if __name__ == "__main__":
    main()