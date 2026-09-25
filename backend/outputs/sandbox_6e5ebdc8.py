import math

def calculator():
    while True:
        # Prompt the user for input
        expression = input("Enter an expression to calculate (e.g., 1 * 3 + 5677 / 45): ")
        
        try:
            # Evaluate the expression using eval
            result = eval(expression)
            print(f"Result: {result}")
        
        except Exception as e:
            print(f"Error: {e}")
        
        # Ask the user if they want to continue
        choice = input("Do you want to perform another calculation? (yes/no): ").strip().lower()
        if choice != 'yes':
            print("Exiting the calculator. Goodbye!")
            break

# Run the calculator
calculator()