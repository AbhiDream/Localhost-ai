import math

def calculator():
    while True:
        # Prompt the user to enter an operation
        operation = input("Enter an operation (e.g., 1 * 3 + 5677 / 45): ")
        
        try:
            # Evaluate the expression
            result = eval(operation)
            print(f"Result: {result}")
        except Exception as e:
            print(f"Error: {e}")
        
        # Ask the user if they want to continue
        if input("Do you want to perform another operation? (yes/no): ").strip().lower() != 'yes':
            break

# Run the calculator
calculator()