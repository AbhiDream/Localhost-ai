def calculator():
    # Example values for demonstration
    num1 = 10
    num2 = 5
    operation = '+'

    # Function to perform basic arithmetic operations
    def perform_operation(a, b, op):
        if op == '+':
            return a + b
        elif op == '-':
            return a - b
        elif op == '*':
            return a * b
        elif op == '/':
            if b != 0:
                return a / b
            else:
                return "Error: Division by zero"
        else:
            return "Error: Invalid operation"

    # Display the current values and operation
    print(f"Current values: {num1}, {num2}")
    print(f"Current operation: {num1} {operation} {num2}")

    # Perform the operation
    result = perform_operation(num1, num2, operation)

    # Display the result
    print(f"Result: {result}")

    # Ask user if they want to perform another operation
    while True:
        choice = input("Do you want to perform another operation? (yes/no): ").strip().lower()
        if choice == 'yes':
            # Ask for new values and operation
            num1 = float(input("Enter the first number: "))
            num2 = float(input("Enter the second number: "))
            operation = input("Enter the operation (+, -, *, /): ")
            # Perform the new operation and display the result
            result = perform_operation(num1, num2, operation)
            print(f"Result: {result}")
        elif choice == 'no':
            print("Exiting calculator. Goodbye!")
            break
        else:
            print("Invalid choice. Please enter 'yes' or 'no'.")

# Run the calculator function
calculator()