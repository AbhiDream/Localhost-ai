def calculator():
    while True:
        print("\nWelcome to the Calculator!")
        print("Select operation:")
        print("1. Add")
        print("2. Subtract")
        print("3. Multiply")
        print("4. Divide")
        print("5. Exit")

        # Predefined choice for demonstration purposes
        choice = '1'  # You can change this to any valid choice (1, 2, 3, 4, or 5)

        if choice == '5':
            print("Exiting the calculator. Goodbye!")
            break

        if choice in ['1', '2', '3', '4']:
            num1 = float(input("Enter first number: "))
            num2 = float(input("Enter second number: "))

            if choice == '1':
                result = num1 + num2
                print(f"Result: {num1} + {num2} = {result}")

            elif choice == '2':
                result = num1 - num2
                print(f"Result: {num1} - {num2} = {result}")

            elif choice == '3':
                result = num1 * num2
                print(f"Result: {num1} * {num2} = {result}")

            elif choice == '4':
                if num2 != 0:
                    result = num1 / num2
                    print(f"Result: {num1} / {num2} = {result}")
                else:
                    print("Error! Division by zero is not allowed.")
        else:
            print("Invalid input. Please enter a valid choice.")

if __name__ == "__main__":
    calculator()