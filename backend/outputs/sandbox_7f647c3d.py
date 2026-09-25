import math

def calculator():
    print("Welcome to the Multi-Operation Calculator!")
    print("Available operations: +, -, *, /, **, sqrt")
    print("Enter 'exit' to quit the calculator.")

    while True:
        # Get user input
        expression = input("Enter an expression (e.g., 3 + 5 * 2): ")

        # Check if the user wants to exit
        if expression.lower() == 'exit':
            print("Thank you for using the calculator. Goodbye!")
            break

        try:
            # Evaluate the expression using eval()
            result = eval(expression)
            print(f"Result: {result}")

        except ZeroDivisionError:
            print("Error: Division by zero is not allowed.")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    calculator()