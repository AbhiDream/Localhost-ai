def product_except_self(nums):
    n = len(nums)
    result = [1] * n  # Initialize result array with 1s
    
    # Calculate the product of all elements to the left of each element
    left_product = 1
    for i in range(n):
        result[i] = left_product
        left_product *= nums[i]
    
    # Calculate the product of all elements to the right of each element
    right_product = 1
    for i in range(n - 1, -1, -1):
        result[i] *= right_product
        right_product *= nums[i]
    
    return result

# Example usage
print(product_except_self([1, 2, 3, 4]))  # Output: [24, 12, 8, 6]
print(product_except_self([2, 3, 4]))    # Output: [12, 8, 6]
print(product_except_self([0, 1, 2, 3]))  # Output: [6, 0, 0, 0]
print(product_except_self([1, 0, 3, 0]))  # Output: [0, 0, 0, 0]
print(product_except_self([-1, 1, 0, -3, 3]))  # Output: [0, 0, 9, 0, 0]