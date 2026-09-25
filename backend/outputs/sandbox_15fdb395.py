import math

# Function to calculate friction head loss using the Darcy-Weisbach equation
def calculate_friction_head_loss(f, L, D, v):
    return f * (L / D) * (v ** 2 / (2 * 9.81))

# Function to calculate the friction factor based on the Reynolds number
def calculate_friction_factor(Re):
    if Re < 2300:
        f = 0.079
    elif Re < 4000:
        f = 0.021
    elif Re < 10000:
        f = 0.013
    elif Re < 20000:
        f = 0.008
    else:
        f = 0.003
    return f

# Function to perform first aid for caustic soda
def caustic_soda_first_aid(contact):
    if contact:
        print("Contact with caustic soda is highly corrosive. Immediate action is required.")
        print("1. Immediately flush eyes or skin with plenty of water for at least 30 minutes.")
        print("2. Remove contaminated clothing.")
        print("3. Seek medical attention.")
    else:
        print("No contact with caustic soda detected. No action required.")

# Main function to run the calculator
def main():
    # Example usage of the Darcy-Weisbach equation
    L = 100  # Length of the pipe in meters
    D = 0.05  # Inside diameter of the pipe in meters
    v = 1.5  # Velocity of the fluid in meters per second
    Re = v * D / 9.81  # Reynolds number
    f = calculate_friction_factor(Re)
    hf = calculate_friction_head_loss(f, L, D, v)
    print(f"Friction head loss (hf) = {hf:.2f} meters")

    # Example usage of first aid for caustic soda
    contact = True  # Set to True if contact is detected
    caustic_soda_first_aid(contact)

# Run the main function
if __name__ == "__main__":
    main()