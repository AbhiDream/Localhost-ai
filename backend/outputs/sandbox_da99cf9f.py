# Define a function to perform addition
def add(x, y):
    return x + y

# Define a function to perform subtraction
def subtract(x, y):
    return x - y

# Define a function to perform multiplication
def multiply(x, y):
    return x * y

# Define a function to perform division
def divide(x, y):
    if y == 0:
        return "Error! Division by zero."
    return x / y

# Main calculator function
def calculator():
    print("Select operation:")
    print("1. Add")
    print("2. Subtract")
    print("3. Multiply")
    print("4. Divide")

    # User input for operation choice
    choice = input("Enter choice (1/2/3/4): ")

    # Input for two numbers
    num1 = float(input("Enter first number: "))
    num2 = float(input("Enter second number: "))

    # Perform the selected operation
    if choice == '1':
        print(f"{num1} + {num2} = {add(num1, num2)}")
    elif choice == '2':
        print(f"{num1} - {num2} = {subtract(num1, num2)}")
    elif choice == '3':
        print(f"{num1} * {num2} = {multiply(num1, num2)}")
    elif choice == '4':
        print(f"{num1} / {num2} = {divide(num1, num2)}")
    else:
        print("Invalid input")

# Run the calculator
calculator()