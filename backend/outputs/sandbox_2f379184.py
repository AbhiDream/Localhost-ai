import math

def perform_calculation():
    while True:
        try:
            # Get user input for the first number
            num1 = float(input("Enter the first number: "))
            
            # Get user input for the operation
            operation = input("Enter the operation (+, -, *, /): ")
            
            # Get user input for the second number
            num2 = float(input("Enter the second number: "))
            
            # Perform the calculation based on the operation
            if operation == '+':
                result = num1 + num2
            elif operation == '-':
                result = num1 - num2
            elif operation == '*':
                result = num1 * num2
            elif operation == '/':
                if num2 != 0:
                    result = num1 / num2
                else:
                    print("Error: Division by zero.")
                    continue
            else:
                print("Error: Invalid operation.")
                continue
            
            # Display the result
            print(f"The result of {num1} {operation} {num2} is {result}")
        
        except ValueError:
            print("Error: Please enter valid numbers.")
        
        # Ask the user if they want to perform another calculation
        repeat = input("Do you want to perform another calculation? (yes/no): ")
        if repeat.lower() != 'yes':
            break

# Run the calculator
perform_calculation()